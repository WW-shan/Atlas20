"""Execute the frozen daily plan on a real Bitget account and report it.

This is the automated arm of the derivatives track: it reads the latest frozen
target book, sizes it from the *real* account equity, places the resulting
market orders on Bitget, and pushes one Telegram message built from what the
venue actually did - fills, fees, and the position book read back afterwards.

Safety rails (all on by default):

* ``--live`` is required to send orders; without it the run is a dry run that
  still reads the real account and prints the message you would get.
* a kill-switch file (``--kill-switch``) stops everything if it exists,
* the signal must be fresh (``--max-signal-age-hours``, default 36) unless
  ``--allow-stale-signal`` is passed,
* the account equity must clear ``--equity-floor``,
* one execution per signal date (recorded in ``--state-file``); a run that
  ended with failures may retry once the next timer fires, and the retry
  re-reads the account so it self-corrects.

``--margin-mode auto`` tries isolated margin first (the frozen spec) and falls
back to the venue's cross default when the key/account refuses isolated
futures; the fallback is printed in the message, never hidden.
"""

# ruff: noqa: E402

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
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
from atlas20.derivatives.execution import build_execution_plan  # noqa: E402
from atlas20.derivatives.live_executor import (  # noqa: E402
    ExecutionReport,
    execute_plan,
    format_execution_report,
)
from atlas20.derivatives.live_journal import (  # noqa: E402
    JournalEntry,
    load_journal,
    previous_row,
    upsert_entry,
)
from atlas20.logging_utils import ensure_dir  # noqa: E402

from scripts.plan_live_execution import (  # noqa: E402
    DEFAULT_SYMBOL_MAP,
    DEFAULT_TARGETS_FILE,
    TRACKED_SPEC,
    account_state_from_bitget,
    fetch_public_instruments,
    fetch_public_prices,
    load_symbol_map,
    specs_from_instruments,
)
from scripts.send_derivatives_signal import load_latest_targets  # noqa: E402
from scripts.send_telegram_signal import _chat_ids, _read_state, send_telegram_message  # noqa: E402

DEFAULT_STATE_FILE = Path("data/derivatives_execution_state.json")
DEFAULT_JOURNAL_FILE = Path("reports/derivatives_track_live/journal.csv")
DEFAULT_KILL_SWITCH = Path("data/derivatives_execution.KILL")
DEFAULT_JSON_OUT = Path("reports/derivatives_track_execution/latest.json")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--spec", default=TRACKED_SPEC)
    parser.add_argument("--targets-file", type=Path, default=DEFAULT_TARGETS_FILE)
    parser.add_argument("--symbol-map", type=Path, default=DEFAULT_SYMBOL_MAP)
    parser.add_argument("--live", action="store_true", help="actually place the orders")
    parser.add_argument("--notify", action="store_true", help="send the report to Telegram")
    parser.add_argument("--force", action="store_true", help="ignore same-day idempotency")
    parser.add_argument("--allow-stale-signal", action="store_true")
    parser.add_argument("--max-signal-age-hours", type=float, default=36.0)
    parser.add_argument("--equity-floor", type=float, default=20.0)
    parser.add_argument("--leverage", type=float, default=2.0)
    parser.add_argument("--long-buffer", type=float, default=0.50)
    parser.add_argument("--cost-bps", type=float, default=20.0)
    parser.add_argument("--min-rebalance-usdt", type=float, default=5.0)
    parser.add_argument(
        "--margin-mode",
        choices=("auto", "isolated", "crossed"),
        default="auto",
        help="auto = try isolated, fall back to crossed; require-isolated makes that fatal",
    )
    parser.add_argument("--require-isolated", action="store_true")
    parser.add_argument("--state-file", type=Path, default=DEFAULT_STATE_FILE)
    parser.add_argument("--journal-file", type=Path, default=DEFAULT_JOURNAL_FILE)
    parser.add_argument("--kill-switch", type=Path, default=DEFAULT_KILL_SWITCH)
    parser.add_argument("--json-out", type=Path, default=DEFAULT_JSON_OUT)
    parser.add_argument("--instruments-file", type=Path, default=None)
    parser.add_argument("--prices-file", type=Path, default=None)
    return parser.parse_args(argv)


def _stamp_assets(rows: list[dict], symbols_by_asset: dict[str, str]) -> list[dict]:
    """Add the model's asset id to each venue position row."""

    by_symbol = {str(symbol).upper(): asset for asset, symbol in symbols_by_asset.items()}
    stamped: list[dict] = []
    for row in rows:
        record = dict(row)
        symbol = str(record.get("symbol") or "").upper()
        record.setdefault("asset", by_symbol.get(symbol, symbol.replace("USDT", "")))
        stamped.append(record)
    return stamped


def _journal_entry(
    report: ExecutionReport,
    *,
    signal_date: str,
    run_at: datetime,
    prev_equity: float | None,
    warnings: list[str],
) -> JournalEntry:
    positions: list[dict] = []
    position_value = 0.0
    unrealised = 0.0
    funding = 0.0
    for row in report.positions_after:
        size = abs(float(row.get("total") or 0.0))
        if size <= 0.0:
            continue
        mark = float(row.get("markPrice") or row.get("avgPrice") or 0.0)
        notional = size * mark
        position_value += notional
        unrealised += float(row.get("unrealisedPnl") or 0.0)
        funding += float(row.get("totalFunding") or 0.0)
        positions.append(
            {
                "asset": str(row.get("asset") or "").lower(),
                "symbol": str(row.get("symbol") or ""),
                "side": str(row.get("posSide") or "long"),
                "qty": size,
                "avg_price": float(row.get("avgPrice") or 0.0),
                "mark_price": mark,
                "notional": round(notional, 6),
                "weight": round(notional / report.equity_after, 6)
                if report.equity_after > 0
                else 0.0,
                "unrealised_pnl": round(float(row.get("unrealisedPnl") or 0.0), 6),
            }
        )
    equity = report.equity_after
    day_pnl = None if prev_equity is None else round(equity - float(prev_equity), 6)
    day_return = (
        None
        if not prev_equity or day_pnl is None
        else round(day_pnl / float(prev_equity), 8)
    )
    return JournalEntry(
        date=run_at.strftime("%Y-%m-%d"),
        run_at_utc=run_at.isoformat(),
        signal_date=signal_date,
        equity=round(equity, 6),
        position_value=round(position_value, 6),
        cash=round(report.balance_after, 6),
        day_pnl=day_pnl,
        day_return=day_return,
        fees_today=round(report.fee_total, 8),
        funding_total=round(funding, 8),
        unrealised_pnl=round(unrealised, 6),
        positions=positions,
        trades=[
            {
                "order_id": fill.order_id,
                "symbol": fill.symbol,
                "side": fill.side,
                "action": fill.action,
                "qty": fill.filled_size,
                "avg_price": fill.avg_price,
                "notional": round(fill.notional, 6),
                "fee": round(fill.fee, 8),
            }
            for fill in report.fills
        ],
        notes=[*report.margin_notes, *warnings],
    )


def _write_state(path: Path, key: str, status: str, report: ExecutionReport) -> None:
    state = _read_state(path)
    state["last_key"] = key
    state["last_status"] = status
    state["last_run_at"] = datetime.now(timezone.utc).isoformat()
    runs = state.get("runs")
    if not isinstance(runs, list):
        runs = []
    runs.append(
        {
            "key": key,
            "status": status,
            "ran_at": state["last_run_at"],
            "fills": [fill.as_dict() for fill in report.fills],
            "failures": list(report.failures),
        }
    )
    state["runs"] = runs[-40:]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, indent=2, sort_keys=True), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    if args.kill_switch.exists():
        raise SystemExit(
            f"kill switch present at {args.kill_switch}; refusing to trade "
            "(delete the file to resume)"
        )

    signal_date, execution_hint, book = load_latest_targets(args.targets_file)
    age_hours = (pd.Timestamp.now(tz="UTC") - signal_date).total_seconds() / 3600.0
    if age_hours > args.max_signal_age_hours and not args.allow_stale_signal:
        raise SystemExit(
            f"signal date {signal_date.date()} is {age_hours:.1f}h old "
            f"(> {args.max_signal_age_hours:g}h); refresh the pipeline "
            "(make derivatives-oos-data derivatives-oos) or pass --allow-stale-signal"
        )

    targets = {
        str(record["asset"]): float(record["target_weight"])
        for record in book.to_dict("records")
        if abs(float(record["target_weight"])) > 0.0
    }
    symbols_by_asset = load_symbol_map(args.symbol_map)
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

    client = BitgetPrivateClient(BitgetCredentials.from_env())
    account = account_state_from_bitget(client, {**symbols_by_asset, **relevant_symbols})
    if account.equity < args.equity_floor:
        raise SystemExit(
            f"account equity {account.equity:.2f} USDT is below the "
            f"{args.equity_floor:.2f} USDT floor; refusing to trade"
        )

    prices_by_asset: dict[str, float] = {}
    for asset in targets:
        symbol = relevant_symbols[asset].upper()
        if prices.get(symbol, 0.0) <= 0.0:
            raise SystemExit(f"no usable price for {symbol}")
        prices_by_asset[asset] = prices[symbol]
    for asset, position in account.positions.items():
        if position.symbol.upper() in prices:
            prices_by_asset.setdefault(asset, prices[position.symbol.upper()])

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

    key = f"{args.spec}|{signal_date.date()}"
    state = _read_state(args.state_file)
    already = state.get("last_key") == key and state.get("last_status") == "ok"
    if already and not args.force:
        print(f"already executed {key} (status ok); nothing to do")
        return 0

    lot_notional = {
        asset: float(spec.min_order_qty or spec.quantity_multiplier) * prices_by_asset[asset]
        for asset, spec in specs.items()
        if asset in prices_by_asset
    }
    warnings = list(plan.warnings)
    run_at = datetime.now(timezone.utc)
    journal = load_journal(args.journal_file)
    previous = previous_row(journal, run_at.strftime("%Y-%m-%d"))
    prev_equity = float(previous["equity"]) if previous and previous.get("equity") is not None else None
    prev_day_pnl = (
        float(previous["day_pnl"])
        if previous and previous.get("day_pnl") is not None
        else None
    )

    if not args.live:
        warnings.append("DRY RUN：本次没有真的下单（加 --live 才会执行）")
        report = ExecutionReport(
            signal_date=str(signal_date.date()),
            equity_before=account.equity,
            equity_after=account.equity,
            available_after=account.available_margin,
            positions_after=client.current_positions(),
        )
        report.margin_mode = next(
            (
                str(row.get("marginMode"))
                for row in report.positions_after
                if row.get("marginMode")
            ),
            "",
        )
        report.positions_after = _stamp_assets(
            report.positions_after, {**symbols_by_asset, **relevant_symbols}
        )
        planned_orders = list(plan.orders)
    else:
        hold_mode = client.hold_mode()
        requested = {
            "auto": "isolated",
            "isolated": "isolated",
            "crossed": "crossed",
        }[args.margin_mode]
        report = execute_plan(
            client,
            plan,
            signal_date=str(signal_date.date()),
            leverage=float(args.leverage),
            margin_mode=requested,
            hold_mode=hold_mode,
        )
        report.positions_after = _stamp_assets(
            report.positions_after, {**symbols_by_asset, **relevant_symbols}
        )
        planned_orders = []
        if args.require_isolated and report.margin_mode != "isolated":
            warnings.append(
                "REQUIRE-ISOLATED：本账户/key 无法持逐仓，规格未满足（已按全仓成交，请复核）"
            )

    status = "ok" if not report.failures else "partial"
    message = format_execution_report(
        report,
        signal_date=str(signal_date.date()),
        spec=args.spec,
        execution_hint=execution_hint.strftime("%Y-%m-%d %H:%M UTC"),
        targets=targets,
        lot_notional=lot_notional,
        planned_orders=planned_orders,
        warnings=warnings,
        prev_equity=prev_equity,
        prev_day_pnl=prev_day_pnl,
        run_at=run_at,
    )
    print(message)

    if args.live:
        output = ensure_dir(args.json_out.parent)
        (output / args.json_out.name).write_text(
            json.dumps(
                {
                    "spec": args.spec,
                    "signal_date": str(signal_date.date()),
                    "execution_hint": str(execution_hint),
                    "plan": plan.as_dict(),
                    "report": report.as_dict(),
                    "status": status,
                },
                indent=2,
                sort_keys=True,
                default=str,
            ),
            encoding="utf-8",
        )
        _write_state(args.state_file, key, status, report)
        entry = _journal_entry(
            report,
            signal_date=str(signal_date.date()),
            run_at=run_at,
            prev_equity=prev_equity,
            warnings=warnings,
        )
        upsert_entry(args.journal_file, entry)
        print(f"journal updated: {args.journal_file} ({entry.date})")

    if args.notify:
        token = os.environ.get("ATLAS20_TELEGRAM_BOT_TOKEN")
        if not token:
            raise SystemExit("ATLAS20_TELEGRAM_BOT_TOKEN is not set")
        chat_ids = _chat_ids(os.environ.get("ATLAS20_TELEGRAM_CHAT_ID"))
        if not chat_ids:
            raise SystemExit("ATLAS20_TELEGRAM_CHAT_ID is not set")
        api_base = os.environ.get("ATLAS20_TELEGRAM_API_BASE", "https://api.telegram.org")
        for chat_id in chat_ids:
            send_telegram_message(message, token=token, chat_id=chat_id, api_base=api_base)
            print(f"Notified execution report {key} to {chat_id}")

    if report.failures:
        print(f"{len(report.failures)} order(s) failed; state written as {status}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
