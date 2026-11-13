"""Plan the daily live rebalance from the account's real balance.

The research track always speaks in weights of a 1,000 USDT reference book.
A real account does not: its equity moves with PnL, deposits and funding, and
the order sizes only make sense against that equity.  This script is the
bridge - it combines

* the latest frozen LS45 target book (``reports/ls45_live_g125``),
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
from math import isfinite
from pathlib import Path
import sys
from typing import Iterable

import pandas as pd
import requests

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
for path in (PROJECT_ROOT, SRC_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from atlas20.derivatives.account import (  # noqa: E402
    BitgetCredentials,
    BitgetPrivateClient,
    UTA_CATEGORY,
)
from atlas20.derivatives.execution import (  # noqa: E402
    AccountState,
    ContractSpec,
    PositionState,
    build_execution_plan,
)
from atlas20.derivatives.http import get_json_with_retries  # noqa: E402
from atlas20.derivatives.live_chain import live_execution_hint_for_signal  # noqa: E402
from atlas20.logging_utils import atomic_write_text, ensure_dir  # noqa: E402

from scripts.send_derivatives_signal import load_latest_targets  # noqa: E402
from scripts.send_telegram_signal import _chat_ids, _read_state, send_telegram_message  # noqa: E402

TRACKED_SPEC = "PR2026-11-LS45-H5-LS23-PROFITLOCK-STRONGER21"
DEFAULT_TARGETS_FILE = Path("reports/ls45_live_g125/oos_targets.csv")
DEFAULT_MANIFEST_FILE = Path("reports/ls45_live_g125/manifest.json")
DEFAULT_SYMBOL_MAP = Path(
    "data/raw/bitget_derivatives/merged_oos_20261112/symbol_map.csv"
)
DEFAULT_STATE_FILE = Path("data/ls45_g125_plan_state.json")
PUBLIC_INSTRUMENTS_URL = "https://api.bitget.com/api/v3/market/instruments"
PUBLIC_TICKERS_URL = "https://api.bitget.com/api/v3/market/tickers"


def _finite_float(value: object, field: str) -> float:
    """Parse one required numeric venue field without a silent zero fallback."""

    if value is None or value == "":
        raise ValueError(f"{field} is missing")
    try:
        number = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field} is not numeric: {value!r}") from exc
    if not isfinite(number):
        raise ValueError(f"{field} is not finite: {value!r}")
    return number


def manifest_signal_end_date(path: Path) -> pd.Timestamp | None:
    """Return the manifest's evaluated signal date, or None when absent."""

    manifest_path = Path(path)
    if not manifest_path.is_file():
        return None
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SystemExit(f"manifest {manifest_path} could not be read: {exc}") from exc
    if not isinstance(payload, dict):
        raise SystemExit(f"manifest {manifest_path} is not a JSON object")
    raw = payload.get("signal_end_date")
    if raw in (None, ""):
        return None
    try:
        stamp = pd.Timestamp(raw)
    except (TypeError, ValueError) as exc:
        raise SystemExit(f"manifest {manifest_path} has invalid signal_end_date: {raw!r}") from exc
    if pd.isna(stamp):
        raise SystemExit(f"manifest {manifest_path} has invalid signal_end_date: {raw!r}")
    if stamp.tzinfo is None:
        stamp = stamp.tz_localize("UTC")
    else:
        stamp = stamp.tz_convert("UTC")
    return stamp.normalize()


def load_symbol_map(path: Path) -> dict[str, str]:
    """Load the live asset -> contract map, excluding unusable rows.

    A rebrand can leave two CMC ids pointing at one exchange contract
    (MATIC/POL).  A venue position only identifies the contract, so the
    reverse mapping must have exactly one canonical asset.  Prefer the row
    whose reason is ``direct`` and drop alias-only duplicates; if that still
    leaves an ambiguity, fail closed rather than silently choosing one.
    Missing contracts have an empty symbol and must never become ``"NAN"``.
    """

    frame = pd.read_csv(path)
    if not {"coin_id", "bitget_symbol"}.issubset(frame.columns):
        raise SystemExit(f"symbol map {path} needs coin_id and bitget_symbol columns")
    if "reason" not in frame.columns:
        frame["reason"] = ""

    by_symbol: dict[str, list[dict[str, object]]] = {}
    seen_coin_ids: set[str] = set()
    for record in frame.to_dict("records"):
        coin_id = str(record.get("coin_id") or "").strip()
        if not coin_id or coin_id.lower() == "nan":
            continue
        raw_symbol = record.get("bitget_symbol")
        if raw_symbol is None or pd.isna(raw_symbol):
            continue
        symbol = str(raw_symbol).strip().upper()
        if not symbol or symbol == "NAN":
            continue
        if coin_id in seen_coin_ids:
            raise SystemExit(f"symbol map {path} contains duplicate coin_id {coin_id!r}")
        seen_coin_ids.add(coin_id)
        by_symbol.setdefault(symbol, []).append(record)

    mapped: dict[str, str] = {}
    for symbol, candidates in by_symbol.items():
        direct = [
            record
            for record in candidates
            if str(record.get("reason") or "").strip().lower() == "direct"
        ]
        eligible = direct or candidates
        if len(eligible) != 1:
            ids = ", ".join(sorted(str(record.get("coin_id")) for record in eligible))
            raise SystemExit(
                f"symbol map {path} maps {symbol} ambiguously to {len(eligible)} coin ids: {ids}"
            )
        coin_id = str(eligible[0].get("coin_id") or "").strip()
        if coin_id in mapped:
            raise SystemExit(f"symbol map {path} assigns multiple symbols to coin_id {coin_id!r}")
        mapped[coin_id] = symbol
    return mapped


def symbol_to_asset_index(symbols_by_asset: dict[str, str]) -> dict[str, str]:
    """Return a fail-closed venue symbol -> model asset index."""

    index: dict[str, str] = {}
    for asset, raw_symbol in symbols_by_asset.items():
        symbol = str(raw_symbol).strip().upper()
        if not symbol:
            continue
        previous = index.get(symbol)
        if previous is not None and previous != asset:
            raise ValueError(
                f"venue symbol {symbol} maps to multiple assets: {previous}, {asset}"
            )
        index[symbol] = asset
    return index


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
    if assets.get("usdtEquity") is not None:
        equity = _finite_float(assets.get("usdtEquity"), "account usdtEquity")
    elif assets.get("accountEquity") is not None:
        equity = _finite_float(assets.get("accountEquity"), "account accountEquity")
    else:
        raise ValueError("account assets contain neither usdtEquity nor accountEquity")
    available = _finite_float(usdt.get("available"), "USDT available")
    by_symbol = symbol_to_asset_index(symbols_by_asset)
    positions: dict[str, PositionState] = {}
    unknown: set[str] = set()
    for row in client.current_positions():
        symbol = str(row.get("symbol") or "").upper()
        if not symbol:
            raise ValueError("venue position row has no symbol")
        raw_total = _finite_float(row.get("total"), f"{symbol} total")
        total = abs(raw_total)
        if total <= 0.0:
            continue
        asset = by_symbol.get(symbol)
        if asset is None:
            unknown.add(symbol or "<empty-symbol>")
            continue
        if asset in positions:
            raise RuntimeError(
                f"multiple venue positions map to asset {asset!r}; hedge-mode/duplicate rows "
                "need explicit review before planning"
            )
        reported_side = str(row.get("posSide") or "").lower()
        if reported_side not in {"", "long", "short", "net"}:
            raise ValueError(f"{symbol} posSide is invalid: {reported_side!r}")
        side = (
            "short"
            if reported_side == "short" or (reported_side in {"", "net"} and raw_total < 0.0)
            else "long"
        )
        margin_value = row.get("positionBalance")
        if margin_value is None:
            margin_value = row.get("marginSize")
        if margin_value is None:
            margin_value = row.get("isolatedMargin")
        positions[asset] = PositionState(
            asset=asset,
            symbol=symbol,
            side=side or "long",
            size=total,
            entry_price=_finite_float(row.get("avgPrice"), f"{symbol} avgPrice"),
            mark_price=_finite_float(row.get("markPrice"), f"{symbol} markPrice"),
            margin=_finite_float(margin_value, f"{symbol} positionBalance"),
        )
    if unknown:
        raise RuntimeError(
            "account has position(s) whose symbols are not in the frozen symbol map: "
            + ", ".join(sorted(unknown))
        )
    return AccountState(equity=equity, available_margin=available, positions=positions)


def _public_payload(session: requests.Session, url: str) -> dict:
    payload = get_json_with_retries(
        session,
        url,
        params={"category": "USDT-FUTURES"},
        timeout_seconds=30.0,
    )
    code = str(payload.get("code", ""))
    if code not in {"0", "00000"}:
        raise ValueError(f"Bitget {url} error {code}: {payload.get('msg', '')}")
    return payload


def fetch_public_instruments(session: requests.Session) -> list[dict]:
    payload = _public_payload(session, PUBLIC_INSTRUMENTS_URL)
    data = payload.get("data") or []
    if not isinstance(data, list):
        raise ValueError("Bitget instruments data is not a list")
    return [dict(row) for row in data if isinstance(row, dict)]


def fetch_public_prices(session: requests.Session) -> dict[str, float]:
    """Last price by Bitget symbol from the public UTA tickers endpoint."""

    payload = _public_payload(session, PUBLIC_TICKERS_URL)
    data = payload.get("data") or []
    if not isinstance(data, list):
        raise ValueError("Bitget tickers data is not a list")
    prices: dict[str, float] = {}
    for row in data:
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


def spec_symbol_universe(
    symbols_by_asset: dict[str, str], targets: Iterable[str] = ()
) -> dict[str, str]:
    """Every asset whose venue contract the planner may need, asset -> symbol.

    Specs used to be resolved from today's target set alone.  A "go to cash"
    book has no targets at all, so the held leg had no contract and
    ``build_execution_plan`` raised ``KeyError: 'near'`` on the 2026-10-13 live
    run - the position stayed open on the one signal where the exit mattered
    most.  The account can hold any asset in the symbol map, so the contract
    set has to cover the whole map, plus a symbol fallback for a target the map
    does not know yet.
    """

    universe = {str(asset): str(symbol).upper() for asset, symbol in symbols_by_asset.items()}
    for asset in targets:
        universe.setdefault(str(asset), f"{str(asset).upper()}USDT")
    return universe


def specs_from_instruments(rows: list[dict], symbols_by_asset: dict[str, str]) -> dict[str, ContractSpec]:
    """Return only complete, online perpetual specs from the venue snapshot.

    A symbol present but offline, non-perpetual or missing a required quantity
    grid must fail the live preflight instead of becoming a zero-step contract
    that appears tradeable.
    """

    by_symbol = {
        str(row.get("symbol", "")).upper(): row
        for row in rows
        if isinstance(row, dict)
    }
    specs: dict[str, ContractSpec] = {}
    for asset, symbol in symbols_by_asset.items():
        row = by_symbol.get(symbol.upper())
        if row is None:
            continue
        if str(row.get("status") or "").strip().lower() != "online":
            continue
        if str(row.get("type") or "").strip().lower() != "perpetual":
            continue
        category = str(row.get("category") or UTA_CATEGORY).strip().upper()
        if category != UTA_CATEGORY:
            continue
        spec = ContractSpec.from_bitget_instrument(row)
        if (
            spec.quantity_multiplier <= 0.0
            or spec.min_order_qty <= 0.0
            or spec.min_order_usdt <= 0.0
            or spec.price_multiplier <= 0.0
            or spec.quantity_precision is None
            or spec.price_precision is None
        ):
            continue
        specs[asset] = spec
    return specs


def target_gross_weight(targets: dict[str, float]) -> float:
    """Signed target weights summed as gross exposure."""

    return float(sum(abs(float(weight)) for weight in targets.values()))


def missing_contract_specs(
    specs: dict[str, ContractSpec],
    required_assets: Iterable[str],
) -> list[str]:
    """Required assets with no venue contract spec; live code must fail."""

    return sorted({str(asset) for asset in required_assets}.difference(specs))


def _fmt_money(value: float) -> str:
    return f"{value:,.2f}"


def format_execution_plan(
    plan,
    *,
    signal_date: pd.Timestamp,
    execution_hint: pd.Timestamp,
    research_execution_hint: pd.Timestamp | None = None,
    signal_end_date: pd.Timestamp | None = None,
    spec: str = TRACKED_SPEC,
) -> str:
    event_line = f"最新事件 {signal_date.date()}（UTC）"
    if signal_end_date is not None:
        event_line += f" · 数据评估日 {signal_end_date.date()}（UTC）"
    lines = [
        f"Atlas20 实盘执行计划 · {spec}",
        f"{event_line} · 建议执行 {execution_hint.strftime('%Y-%m-%d %H:%M')} UTC "
        f"/ 北京 {(execution_hint + pd.Timedelta(hours=8)).strftime('%Y-%m-%d %H:%M')}",
        f"账户权益 {_fmt_money(plan.equity)} USDT（目标名义 "
        f"{_fmt_money(plan.expected_gross_notional)}，保证金 {_fmt_money(plan.expected_margin)}，"
        f"保证金率 {plan.target_margin_ratio:.1%}）",
        "",
        "今日调仓:",
    ]
    if research_execution_hint is not None:
        lines.insert(
            2,
            "研究回测成交口径 "
            f"{research_execution_hint.strftime('%Y-%m-%d %H:%M')} UTC "
            f"/ 北京 {(research_execution_hint + pd.Timedelta(hours=8)).strftime('%Y-%m-%d %H:%M')}",
        )
    if not plan.orders:
        lines.append("  无需调仓（已与目标一致或在最小下单量以内）")
    for order in plan.orders:
        verb = {"OPEN": "开仓", "INCREASE": "加仓", "REDUCE": "减仓", "CLOSE": "平仓"}[order.action]
        lines.append(
            f"  {verb} {order.asset.upper()}：{order.side} {order.size:.8g} 枚"
            f"（名义 {_fmt_money(order.notional)} USDT @ {order.price:.8g}"
            f"{'，reduce-only' if order.reduce_only else ''}"
            f"{f'，止损 {order.stop_loss:.8g}' if order.stop_loss is not None else ''}）"
        )
    lines += ["", "保证金调整:"]
    if not plan.margin_intents:
        lines.append("  无需调整")
    for intent in plan.margin_intents:
        verb = "追加" if intent.operation == "add" else "撤出"
        lines.append(
            f"  {verb} {intent.asset.upper()} {_fmt_money(intent.amount)} USDT"
            f"（isolated · {intent.symbol} · {intent.pos_side}）"
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
    atomic_write_text(path, json.dumps(state, indent=2, sort_keys=True))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--spec", default=TRACKED_SPEC)
    parser.add_argument("--targets-file", type=Path, default=DEFAULT_TARGETS_FILE)
    parser.add_argument("--manifest-file", type=Path, default=DEFAULT_MANIFEST_FILE)
    parser.add_argument("--symbol-map", type=Path, default=DEFAULT_SYMBOL_MAP)
    parser.add_argument("--account-file", type=Path, default=None)
    parser.add_argument("--equity", type=float, default=None, help="manual equity for a plan without positions")
    parser.add_argument("--live", action="store_true", help="read the account from the Bitget UTA API")
    parser.add_argument("--leverage", type=float, default=2.0)
    parser.add_argument("--long-buffer", type=float, default=0.50)
    parser.add_argument("--short-buffer", type=float, default=0.50)
    parser.add_argument(
        "--short-stop-loss-pct",
        type=float,
        default=0.20,
        help="attach a mark-price stop this far above each short entry",
    )
    parser.add_argument(
        "--max-gross-multiple",
        type=float,
        default=1.25,
        help="hard cap on absolute target notional divided by account equity",
    )
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
    signal_date, research_execution_hint, book = load_latest_targets(args.targets_file)
    signal_end_date = manifest_signal_end_date(args.manifest_file)
    execution_hint = pd.Timestamp(
        live_execution_hint_for_signal(signal_end_date or signal_date)
    )
    targets = {
        str(record["asset"]): float(record["target_weight"])
        for record in book.to_dict("records")
        if abs(float(record["target_weight"])) > 0.0
    }
    gross_weight = target_gross_weight(targets)
    if gross_weight > float(args.max_gross_multiple) + 1e-9:
        raise SystemExit(
            f"frozen target gross {gross_weight:.6f}x exceeds the "
            f"{float(args.max_gross_multiple):g}x spec cap"
        )
    relevant_symbols = spec_symbol_universe(symbols_by_asset, targets)

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

    missing_specs = missing_contract_specs(
        specs,
        set(targets).union(account.positions),
    )
    if missing_specs:
        raise SystemExit(
            "no Bitget contract spec for required asset(s): " + ", ".join(missing_specs)
        )

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
        short_buffer=float(args.short_buffer),
        short_stop_loss_pct=float(args.short_stop_loss_pct),
        max_gross_exposure=float(args.max_gross_multiple) * account.equity,
        taker_fee_rate=max(float(args.cost_bps), 0.0) / 10_000.0,
        min_rebalance_usdt=float(args.min_rebalance_usdt),
    )
    message = format_execution_plan(
        plan,
        signal_date=signal_date,
        execution_hint=execution_hint,
        research_execution_hint=research_execution_hint,
        signal_end_date=signal_end_date,
        spec=args.spec,
    )
    print(message)

    if args.json_out is not None:
        ensure_dir(Path(args.json_out).parent)
        atomic_write_text(
            args.json_out,
            json.dumps(
                {
                    "spec": args.spec,
                    "signal_date": str(signal_date.date()),
                    "execution_hint": str(execution_hint),
                    "research_execution_hint": str(research_execution_hint),
                    "plan": plan.as_dict(),
                },
                indent=2,
                sort_keys=True,
                default=str,
            ),
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
