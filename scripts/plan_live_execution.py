"""Plan the daily live rebalance from the account's real balance.

The research track always speaks in weights of a 1,000 USDT reference book.
A real account does not: its equity moves with PnL, deposits and funding, and
the order sizes only make sense against that equity.  This script is the
bridge - it combines

* the latest frozen target book (``reports/derivatives_track_oos_2026``),
* the account state (live Bitget UTA API, a JSON snapshot, or ``--equity``),
* the real contract specs and last prices,

and emits the exact orders and isolated-margin adjustments for the day, in
USDT and in contract quantity.  It never trades by default; ``--notify`` sends
the plan to Telegram, and the actual orders stay manual.

Account snapshot JSON schema (``--account-file``)::

    {
      "equity": 512.34,
      "available_margin": 210.5,
      "as_of": "2026-10-09T02:00:00Z",
      "positions": [
        {"asset": "near", "symbol": "NEARUSDT", "side": "long",
         "size": 120.5, "entry_price": 3.02, "mark_price": 3.10, "margin": 192.4}
      ]
    }
"""

# ruff: noqa: E402

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys

import pandas as pd
import requests

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
for path in (PROJECT_ROOT, SRC_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from atlas20.derivatives.account import BitgetCredentials, BitgetPrivateClient  # noqa: E402
from atlas20.derivatives.execution import (  # noqa: E402
    AccountState,
    ContractSpec,
    PositionState,
    build_execution_plan,
)
from atlas20.logging_utils import ensure_dir  # noqa: E402

from scripts.send_derivatives_signal import load_latest_targets  # noqa: E402
from scripts.send_telegram_signal import _chat_ids, _read_state, send_telegram_message  # noqa: E402

TRACKED_SPEC = "PR2026-10-D-L125-V2"
DEFAULT_TARGETS_FILE = Path("reports/derivatives_track_oos_2026/oos_targets.csv")
DEFAULT_SYMBOL_MAP = Path("data/raw/bitget_derivatives/merged_oos_20261009/symbol_map.csv")
DEFAULT_STATE_FILE = Path("data/derivatives_execution_state.json")
PUBLIC_INSTRUMENTS_URL = "https://api.bitget.com/api/v3/market/instruments"
PUBLIC_TICKERS_URL = "https://api.bitget.com/api/v3/market/tickers"


def load_symbol_map(path: Path) -> dict[str, str]:
    frame = pd.read_csv(path)
    if not {"coin_id", "bitget_symbol"}.issubset(frame.columns):
        raise SystemExit(f"symbol map {path} needs coin_id and bitget_symbol columns")
    return {
        str(record["coin_id"]): str(record["bitget_symbol"]).upper()
        for record in frame.to_dict("records")
    }


def load_account_file(path: Path) -> AccountState:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    positions: dict[str, PositionState] = {}
    for record in payload.get("positions", []):
        asset = str(record["asset"])
        positions[asset] = PositionState(
            asset=asset,
            symbol=str(record.get("symbol", asset.upper())),
            side=str(record.get("side", "long")),
            size=float(record["size"]),
            entry_price=float(record["entry_price"]),
            mark_price=float(record["mark_price"]),
            margin=float(record["margin"]),
        )
    as_of = payload.get("as_of")
    return AccountState(
        equity=float(payload["equity"]),
        available_margin=float(payload["available_margin"]),
        positions=positions,
        as_of=pd.Timestamp(as_of, tz="UTC") if as_of else None,
    )


def account_state_from_bitget(client: BitgetPrivateClient, symbols_by_asset: dict[str, str]) -> AccountState:
    assets = client.account_assets()
    coin_rows = {
        str(row.get("coin", "")).upper(): row for row in assets.get("assets", []) if isinstance(row, dict)
    }
    usdt = coin_rows.get("USDT", {})
    equity = float(assets.get("usdtEquity") or assets.get("accountEquity") or 0.0)
    available = float(usdt.get("available") or 0.0)
    by_symbol = {symbol.upper(): asset for asset, symbol in symbols_by_asset.items()}
    positions: dict[str, PositionState] = {}
    for row in client.current_positions():
        symbol = str(row.get("symbol", "")).upper()
        asset = by_symbol.get(symbol)
        if asset is None:
            continue
        side = str(row.get("posSide", "long")).lower()
        positions[asset] = PositionState(
            asset=asset,
            symbol=symbol,
            side=side or "long",
            size=abs(float(row.get("total") or 0.0)),
            entry_price=float(row.get("avgPrice") or 0.0),
            mark_price=float(row.get("markPrice") or 0.0),
            margin=float(row.get("positionBalance") or 0.0),
        )
    return AccountState(equity=equity, available_margin=available, positions=positions)


def fetch_public_instruments(session: requests.Session) -> list[dict]:
    response = session.get(
        PUBLIC_INSTRUMENTS_URL, params={"category": "USDT-FUTURES"}, timeout=30
    )
    response.raise_for_status()
    return list(response.json().get("data") or [])


def fetch_public_prices(session: requests.Session) -> dict[str, float]:
    """Last price by Bitget symbol from the public UTA tickers endpoint."""

    response = session.get(PUBLIC_TICKERS_URL, params={"category": "USDT-FUTURES"}, timeout=30)
    response.raise_for_status()
    prices: dict[str, float] = {}
    for row in response.json().get("data") or []:
        if not isinstance(row, dict):
            continue
        symbol = str(row.get("symbol", "")).upper()
        price = row.get("lastPrice") or row.get("markPrice") or row.get("price")
        try:
            if symbol and price is not None:
                prices[symbol] = float(price)
        except (TypeError, ValueError):
            continue
    return prices


def specs_from_instruments(rows: list[dict], symbols_by_asset: dict[str, str]) -> dict[str, ContractSpec]:
    by_symbol = {str(row.get("symbol", "")).upper(): row for row in rows}
    specs: dict[str, ContractSpec] = {}
    for asset, symbol in symbols_by_asset.items():
        row = by_symbol.get(symbol.upper())
        if row is not None:
            specs[asset] = ContractSpec.from_bitget_instrument(row)
    return specs


def _fmt_money(value: float) -> str:
    return f"{value:,.2f}"


def format_execution_plan(
    plan,
    *,
    signal_date: pd.Timestamp,
    execution_hint: pd.Timestamp,
    spec: str = TRACKED_SPEC,
) -> str:
    lines = [
        f"Atlas20 实盘执行计划 · {spec}",
        f"信号日 {signal_date.date()}（UTC）· 建议执行 {execution_hint.strftime('%Y-%m-%d %H:%M')} UTC "
        f"/ 北京 {(execution_hint + pd.Timedelta(hours=8)).strftime('%Y-%m-%d %H:%M')}",
        f"账户权益 {_fmt_money(plan.equity)} USDT（目标名义 "
        f"{_fmt_money(plan.expected_gross_notional)}，保证金 {_fmt_money(plan.expected_margin)}，"
        f"保证金率 {plan.target_margin_ratio:.1%}）",
        "",
        "今日调仓:",
    ]
    if not plan.orders:
        lines.append("  无需调仓（已与目标一致或在最小下单量以内）")
    for order in plan.orders:
        verb = {"OPEN": "开仓", "INCREASE": "加仓", "REDUCE": "减仓", "CLOSE": "平仓"}[order.action]
        lines.append(
            f"  {verb} {order.asset.upper()}：{order.side} {order.size:.8g} 枚"
            f"（名义 {_fmt_money(order.notional)} USDT @ {order.price:.8g}"
            f"{'，reduce-only' if order.reduce_only else ''}）"
        )
    lines += ["", "保证金调整:"]
    if not plan.margin_intents:
        lines.append("  无需调整")
    for intent in plan.margin_intents:
        verb = "追加" if intent.operation == "add" else "撤出"
        lines.append(
            f"  {verb} {intent.asset.upper()} {_fmt_money(intent.amount)} USDT"
            f"（isolated · {intent.asset.upper()}USDT · {intent.pos_side}）"
        )
    if plan.warnings:
        lines += ["", "提示:"]
        lines += [f"  - {warning}" for warning in plan.warnings]
    lines += ["", "仅供手动执行；本消息不代替风控判断。"]
    return "\n".join(lines)


def _mark_plan_sent(path: Path, chat_id: str, key: str) -> None:
    state = _read_state(path)
    sent_keys = state.get("sent_keys")
    if not isinstance(sent_keys, dict):
        sent_keys = {}
    sent_keys[str(chat_id)] = key
    state["sent_keys"] = sent_keys
    state["last_sent_key"] = key
    state["sent_at"] = datetime.now(timezone.utc).isoformat()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, indent=2, sort_keys=True), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--spec", default=TRACKED_SPEC)
    parser.add_argument("--targets-file", type=Path, default=DEFAULT_TARGETS_FILE)
    parser.add_argument("--symbol-map", type=Path, default=DEFAULT_SYMBOL_MAP)
    parser.add_argument("--account-file", type=Path, default=None)
    parser.add_argument("--equity", type=float, default=None, help="manual equity for a plan without positions")
    parser.add_argument("--live", action="store_true", help="read the account from the Bitget UTA API")
    parser.add_argument("--leverage", type=float, default=2.0)
    parser.add_argument("--long-buffer", type=float, default=0.50)
    parser.add_argument("--cost-bps", type=float, default=20.0, help="for reporting only")
    parser.add_argument("--min-rebalance-usdt", type=float, default=5.0)
    parser.add_argument("--instruments-file", type=Path, default=None)
    parser.add_argument("--prices-file", type=Path, default=None)
    parser.add_argument("--json-out", type=Path, default=None)
    parser.add_argument("--notify", action="store_true", help="send the plan to Telegram")
    parser.add_argument("--state-file", type=Path, default=DEFAULT_STATE_FILE)
    parser.add_argument("--force", action="store_true", help="send even if this plan was already notified")
    args = parser.parse_args()

    symbols_by_asset = load_symbol_map(args.symbol_map)
    signal_date, execution_hint, book = load_latest_targets(args.targets_file)
    targets = {
        str(record["asset"]): float(record["target_weight"])
        for record in book.to_dict("records")
        if abs(float(record["target_weight"])) > 0.0
    }
    relevant_symbols = {
        asset: symbols_by_asset.get(asset, f"{asset.upper()}USDT") for asset in targets
    }

    session = requests.Session()
    if args.prices_file is not None:
        price_payload = json.loads(Path(args.prices_file).read_text(encoding="utf-8"))
        prices = {str(key).upper(): float(value) for key, value in price_payload.items()}
    else:
        prices = fetch_public_prices(session)

    if args.instruments_file is not None:
        payload = json.loads(Path(args.instruments_file).read_text(encoding="utf-8"))
        rows = payload.get("data", payload) if isinstance(payload, dict) else payload
    else:
        rows = fetch_public_instruments(session)
    specs = specs_from_instruments(rows, relevant_symbols)

    account: AccountState | None = None
    if args.live:
        client = BitgetPrivateClient(BitgetCredentials.from_env())
        symbols_for_account = {**symbols_by_asset, **relevant_symbols}
        account = account_state_from_bitget(client, symbols_for_account)
    elif args.account_file is not None:
        account = load_account_file(args.account_file)
    elif args.equity is not None:
        if args.equity <= 0.0:
            raise SystemExit("--equity must be positive")
        account = AccountState(equity=float(args.equity), available_margin=float(args.equity))
    else:
        raise SystemExit("provide --live, --account-file or --equity to size the plan")

    missing_prices = [
        asset for asset in targets if prices.get(relevant_symbols[asset].upper(), 0.0) <= 0.0
    ]
    if missing_prices:
        raise SystemExit(f"no usable price for: {', '.join(sorted(missing_prices))}")
    prices_by_asset = {
        asset: prices[relevant_symbols[asset].upper()] for asset in targets
    }
    for asset, position in account.positions.items():
        symbol = position.symbol.upper()
        if symbol in prices:
            prices_by_asset.setdefault(asset, prices[symbol])

    plan = build_execution_plan(
        account,
        targets,
        specs,
        prices_by_asset,
        leverage=float(args.leverage),
        long_buffer=float(args.long_buffer),
        taker_fee_rate=max(float(args.cost_bps), 0.0) / 10_000.0,
        min_rebalance_usdt=float(args.min_rebalance_usdt),
    )
    message = format_execution_plan(
        plan, signal_date=signal_date, execution_hint=execution_hint, spec=args.spec
    )
    print(message)

    if args.json_out is not None:
        output = ensure_dir(Path(args.json_out).parent)
        (output / Path(args.json_out).name).write_text(
            json.dumps(
                {
                    "spec": args.spec,
                    "signal_date": str(signal_date.date()),
                    "execution_hint": str(execution_hint),
                    "plan": plan.as_dict(),
                },
                indent=2,
                sort_keys=True,
                default=str,
            ),
            encoding="utf-8",
        )

    if args.notify:
        import os

        key = f"{args.spec}|{signal_date.date()}"
        chat_ids = _chat_ids(os.environ.get("ATLAS20_TELEGRAM_CHAT_ID"))
        if not chat_ids:
            raise SystemExit("ATLAS20_TELEGRAM_CHAT_ID is not set")
        state = _read_state(args.state_file)
        sent_keys = state.get("sent_keys") if isinstance(state.get("sent_keys"), dict) else {}
        pending = chat_ids if args.force else [cid for cid in chat_ids if sent_keys.get(cid) != key]
        if not pending:
            print(f"Already notified {key}; skipping")
            return
        token = os.environ.get("ATLAS20_TELEGRAM_BOT_TOKEN")
        if not token:
            raise SystemExit("ATLAS20_TELEGRAM_BOT_TOKEN is not set")
        api_base = os.environ.get("ATLAS20_TELEGRAM_API_BASE", "https://api.telegram.org")
        for chat_id in pending:
            send_telegram_message(message, token=token, chat_id=chat_id, api_base=api_base)
            _mark_plan_sent(args.state_file, chat_id, key)
            print(f"Notified execution plan {key} to {chat_id}")


if __name__ == "__main__":
    main()
