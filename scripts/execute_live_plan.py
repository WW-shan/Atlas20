"""Execute the frozen daily plan on a real Bitget account and report it.

This is the automated arm of the derivatives track: it reads the latest frozen
target book, sizes it from the *real* account equity, places the resulting
market orders on Bitget, and pushes one Telegram message built from what the
venue actually did - fills, fees, and the position book read back afterwards.

Safety rails (all on by default):

* ``--live`` is required to send orders; without it the run is a dry run that
  still reads the real account and prints the message you would get.
* a kill-switch file (``--kill-switch``) stops everything if it exists,
* the target data/manifest must be fresh (``--max-mark-staleness-hours``,
  default 30) unless ``--allow-stale-signal`` is passed,
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
import hashlib
import json
import os
from pathlib import Path
import sys
from typing import Any, Callable

import pandas as pd
import requests

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
for path in (PROJECT_ROOT, SRC_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from atlas20.derivatives.account import BitgetCredentials, BitgetPrivateClient  # noqa: E402
from atlas20.derivatives.execution import build_execution_plan  # noqa: E402
from atlas20.derivatives.live_chain import manifest_staleness_hours  # noqa: E402
from atlas20.derivatives.live_executor import (  # noqa: E402
    ExecutionReport,
    execute_plan,
    format_execution_report,
)
from atlas20.derivatives.live_journal import (  # noqa: E402
    DEFAULT_CAPITAL_FLOWS_FILE,
    JournalEntry,
    load_journal,
    net_capital_flow,
    previous_row,
    protected_short_symbols,
    upsert_entry,
)
from atlas20.derivatives.quotes import (  # noqa: E402
    ExecutionQuote,
    QuoteError,
    fetch_execution_quotes,
    orderbook_warnings,
    quote_warnings,
    require_fresh_quotes,
)
from atlas20.logging_utils import ensure_dir  # noqa: E402

from scripts.plan_live_execution import (  # noqa: E402
    DEFAULT_SYMBOL_MAP,
    DEFAULT_TARGETS_FILE,
    TRACKED_SPEC,
    account_state_from_bitget,
    fetch_public_instruments,
    load_symbol_map,
    spec_symbol_universe,
    specs_from_instruments,
)
from scripts.send_derivatives_signal import load_latest_targets  # noqa: E402
from scripts.send_telegram_signal import _chat_ids, _read_state, send_telegram_message  # noqa: E402

DEFAULT_STATE_FILE = Path("data/ls45_g125_execution_state.json")
DEFAULT_JOURNAL_FILE = Path("reports/ls45_live_g125_live/journal.csv")
DEFAULT_MANIFEST_FILE = Path("reports/ls45_live_g125/manifest.json")
DEFAULT_KILL_SWITCH = Path("data/ls45_g125_execution.KILL")
DEFAULT_JSON_OUT = Path("reports/ls45_live_g125_live/latest.json")


def _live_quote_snapshot(
    session: requests.Session,
    symbols: set[str],
    *,
    required_symbols: set[str] | None = None,
    max_age_seconds: float = 120.0,
    spread_warning_bps: float = 50.0,
    mark_deviation_warning_bps: float = 100.0,
) -> tuple[dict[str, float], dict[str, ExecutionQuote], list[str]]:
    """Fetch fresh ticker quotes and return prices, snapshots, and warnings."""

    quotes = fetch_execution_quotes(session, symbols)
    required = set(symbols) if required_symbols is None else set(required_symbols)
    require_fresh_quotes(quotes, required, max_age_seconds=max_age_seconds)
    prices = {symbol: quote.last_price for symbol, quote in quotes.items()}
    warnings = quote_warnings(
        quotes,
        required,
        spread_warning_bps=spread_warning_bps,
        mark_deviation_warning_bps=mark_deviation_warning_bps,
    )
    return prices, quotes, warnings


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
    parser.add_argument("--manifest-file", type=Path, default=DEFAULT_MANIFEST_FILE)
    parser.add_argument(
        "--max-mark-staleness-hours",
        type=float,
        default=30.0,
        help="refuse to trade when the frozen mark tree is older than this",
    )
    parser.add_argument(
        "--max-event-age-days",
        type=float,
        default=7.0,
        help="warn (do not block) when the newest book change is older than this",
    )
    parser.add_argument("--equity-floor", type=float, default=20.0)
    parser.add_argument("--leverage", type=float, default=2.0)
    parser.add_argument("--long-buffer", type=float, default=0.50)
    parser.add_argument("--short-buffer", type=float, default=0.50)
    parser.add_argument("--short-stop-loss-pct", type=float, default=0.20)
    parser.add_argument("--max-gross-multiple", type=float, default=1.25)
    parser.add_argument("--cost-bps", type=float, default=20.0)
    parser.add_argument("--min-rebalance-usdt", type=float, default=5.0)
    parser.add_argument(
        "--max-quote-age-seconds",
        type=float,
        default=120.0,
        help="refuse to trade when Bitget's ticker timestamp is older than this",
    )
    parser.add_argument(
        "--spread-warning-bps",
        type=float,
        default=50.0,
        help="warn when the live bid/ask spread exceeds this threshold",
    )
    parser.add_argument(
        "--mark-deviation-warning-bps",
        type=float,
        default=100.0,
        help="warn when last and mark price diverge beyond this threshold",
    )
    parser.add_argument(
        "--margin-mode",
        choices=("auto", "isolated", "crossed"),
        default="auto",
        help="auto = try isolated, fall back to crossed; require-isolated makes that fatal",
    )
    parser.add_argument("--require-isolated", action="store_true")
    parser.add_argument("--state-file", type=Path, default=DEFAULT_STATE_FILE)
    parser.add_argument("--journal-file", type=Path, default=DEFAULT_JOURNAL_FILE)
    parser.add_argument("--capital-flows-file", type=Path, default=DEFAULT_CAPITAL_FLOWS_FILE)
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
    capital_flow: float,
    warnings: list[str],
) -> JournalEntry:
    equity = (
        report.equity_after
        if report.equity_after is not None
        else report.equity_before
    )
    positions: list[dict] = []
    position_value = 0.0
    unrealised = 0.0
    funding = 0.0
    for row in report.positions_after:
        raw_total = float(row.get("total") or 0.0)
        size = abs(raw_total)
        if size <= 0.0:
            continue
        reported_side = str(row.get("posSide") or "").lower()
        side = (
            "short"
            if reported_side == "short"
            or (reported_side in {"", "net"} and raw_total < 0.0)
            else "long"
        )
        mark = float(row.get("markPrice") or row.get("avgPrice") or 0.0)
        notional = size * mark
        position_value += notional
        unrealised += float(row.get("unrealisedPnl") or 0.0)
        funding += float(row.get("totalFunding") or 0.0)
        positions.append(
            {
                "asset": str(row.get("asset") or "").lower(),
                "symbol": str(row.get("symbol") or ""),
                "side": side,
                "qty": size,
                "avg_price": float(row.get("avgPrice") or 0.0),
                "mark_price": mark,
                "notional": round(notional, 6),
                "weight": (
                    round((notional if side == "long" else -notional) / equity, 6)
                    if equity > 0
                    else 0.0
                ),
                "unrealised_pnl": round(float(row.get("unrealisedPnl") or 0.0), 6),
            }
        )
    day_pnl = (
        None
        if prev_equity is None
        else round(equity - float(prev_equity) - float(capital_flow), 6)
    )
    capital_base = (
        None if prev_equity is None else float(prev_equity) + float(capital_flow)
    )
    day_return = (
        None
        if not capital_base or capital_base <= 0 or day_pnl is None
        else round(day_pnl / capital_base, 8)
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
        capital_flow=round(float(capital_flow), 6),
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
                "status": fill.status,
                "stop_loss": fill.stop_loss,
                "requested_stop_loss": fill.requested_stop_loss,
                "position_side": fill.position_side,
                "client_oid": fill.client_oid,
                "stop_trigger_by": fill.stop_trigger_by,
                "stop_order_type": fill.stop_order_type,
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


def _persist_run_result(
    *,
    json_out: Path,
    payload: dict[str, Any],
    journal_file: Path,
    entry: JournalEntry,
    state_file: Path,
    key: str,
    status: str,
    report: ExecutionReport,
    notify: Callable[[], None] | None = None,
) -> None:
    """Persist artifacts in an order that never marks an unwritten run as done."""

    output = ensure_dir(json_out.parent)
    (output / json_out.name).write_text(
        json.dumps(payload, indent=2, sort_keys=True, default=str),
        encoding="utf-8",
    )
    upsert_entry(journal_file, entry)
    if notify is not None:
        notify()
    _write_state(state_file, key, status, report)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    if args.kill_switch.exists():
        raise SystemExit(
            f"kill switch present at {args.kill_switch}; refusing to trade "
            "(delete the file to resume)"
        )

    signal_date, execution_hint, book = load_latest_targets(args.targets_file)
    event_age_days = (
        pd.Timestamp.now(tz="UTC").normalize() - pd.Timestamp(signal_date).normalize()
    ).days

    # The frozen book is an *event* series: it only gets a new row when a
    # sleeve changes its pick.  A book dated days ago is therefore normal -
    # what must be current is the data behind it.  Guard that instead.
    freshness_note: str | None = None
    if args.manifest_file.exists():
        manifest = json.loads(args.manifest_file.read_text(encoding="utf-8"))
        staleness = manifest_staleness_hours(manifest, datetime.now(timezone.utc))
        index_end = str(manifest.get("index_end_date") or "")
        signal_end = str(manifest.get("signal_end_date") or "")
        if not args.allow_stale_signal:
            if staleness > args.max_mark_staleness_hours:
                raise SystemExit(
                    f"mark tree is {staleness:.1f}h old "
                    f"(> {args.max_mark_staleness_hours:g}h); "
                    "run make derivatives-live-data first"
                )
            if index_end and signal_end and index_end < signal_end:
                raise SystemExit(
                    f"target book was only evaluated through {index_end} while data "
                    f"reaches {signal_end}; run make derivatives-oos first"
                )
        freshness_note = (
            f"数据管线: mark 最新 {manifest.get('last_mark')}（{staleness:.1f}h 前）、"
            f"账本评估到 {index_end}、信号事件 {signal_date.date()}（{event_age_days} 天前）"
        )
    elif not args.allow_stale_signal and event_age_days > 1:
        raise SystemExit(
            f"no manifest at {args.manifest_file} and the newest book row is "
            f"{event_age_days} days old; refresh the pipeline "
            "(make derivatives-live-data derivatives-ls45-signal) or pass --allow-stale-signal"
        )

    warnings: list[str] = []
    if event_age_days > args.max_event_age_days:
        warnings.append(
            f"最新信号事件在 {event_age_days} 天前（事件驱动策略，无变化＝继续持有；"
            "若与回测不一致请跑 make audit-live）"
        )

    targets = {
        str(record["asset"]): float(record["target_weight"])
        for record in book.to_dict("records")
        if abs(float(record["target_weight"])) > 0.0
    }
    symbols_by_asset = load_symbol_map(args.symbol_map)
    # Resolve the venue contract for every asset the account can hold, not just
    # today's targets: a "go to cash" book has no targets at all and the close
    # of the held leg still needs its contract.
    relevant_symbols = spec_symbol_universe(symbols_by_asset, targets)
    session = requests.Session()
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
    required_assets = set(targets) | set(account.positions)
    required_symbols = {
        str(relevant_symbols[asset]).upper()
        for asset in required_assets
        if asset in relevant_symbols
    }
    quotes: dict[str, ExecutionQuote] = {}
    if args.prices_file is not None:
        price_payload = json.loads(Path(args.prices_file).read_text(encoding="utf-8"))
        prices = {str(key).upper(): float(value) for key, value in price_payload.items()}
    else:
        try:
            prices, quotes, live_quote_warnings = _live_quote_snapshot(
                session,
                set(relevant_symbols.values()),
                required_symbols=required_symbols,
                max_age_seconds=float(args.max_quote_age_seconds),
                spread_warning_bps=float(args.spread_warning_bps),
                mark_deviation_warning_bps=float(args.mark_deviation_warning_bps),
            )
        except QuoteError as exc:
            raise SystemExit(f"live quote check failed: {exc}") from exc
        warnings.extend(live_quote_warnings)

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
        short_buffer=float(args.short_buffer),
        short_stop_loss_pct=float(args.short_stop_loss_pct),
        max_gross_exposure=float(args.max_gross_multiple) * account.equity,
        taker_fee_rate=max(float(args.cost_bps), 0.0) / 10_000.0,
        min_rebalance_usdt=float(args.min_rebalance_usdt),
    )
    if quotes:
        warnings.extend(
            orderbook_warnings(
                quotes,
                [
                    (order.symbol, order.side, order.notional)
                    for order in plan.orders
                ],
            )
        )

    # Idempotency is per *run day*, not per signal date: the book only changes
    # when a sleeve changes its pick, so keying on the signal date alone would
    # silently skip every day in between - no rebalance check, no daily
    # report, no ledger row.  A second run on the same day still skips.
    run_day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    key = f"{args.spec}|{signal_date.date()}|{run_day}"
    client_oid_prefix = "a20" + hashlib.sha256(key.encode("utf-8")).hexdigest()[:20]
    state = _read_state(args.state_file)
    already = state.get("last_key") == key and state.get("last_status") == "ok"
    if already and not args.force and args.live:
        print(f"already executed {key} (status ok); nothing to do")
        return 0

    lot_notional = {
        asset: float(spec.min_order_qty or spec.quantity_multiplier) * prices_by_asset[asset]
        for asset, spec in specs.items()
        if asset in prices_by_asset
    }
    warnings = [*plan.warnings, *warnings]
    run_at = datetime.now(timezone.utc)
    journal = load_journal(args.journal_file)
    previous = previous_row(journal, run_at.strftime("%Y-%m-%d"))
    prev_equity = float(previous["equity"]) if previous and previous.get("equity") is not None else None
    capital_flow = net_capital_flow(
        args.capital_flows_file,
        after=previous.get("run_at_utc") if previous else None,
        through=run_at,
    )
    if abs(capital_flow) > 0.005:
        warnings.append(f"外部资金流 {capital_flow:+.2f} USDT（已从盈亏中剔除）")
    notes = list(warnings)
    if freshness_note:
        notes.append(freshness_note)
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
            require_isolated=bool(args.require_isolated),
            known_protected_short_symbols=protected_short_symbols(journal),
            hold_mode=hold_mode,
            client_oid_prefix=client_oid_prefix,
        )
        report.positions_after = _stamp_assets(
            report.positions_after, {**symbols_by_asset, **relevant_symbols}
        )
        planned_orders = []
        if (
            args.require_isolated
            and report.positions_after
            and report.margin_mode != "isolated"
        ):
            warnings.append(
                "REQUIRE-ISOLATED：持仓回读不是 isolated，规格未满足；"
                "新的 open/increase 已被阻断，请复核并处理现有仓位"
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
        capital_flow=capital_flow,
        run_at=run_at,
        event_age_days=event_age_days,
    )
    print(message)

    def notify_report() -> None:
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

    if args.live:
        entry = _journal_entry(
            report,
            signal_date=str(signal_date.date()),
            run_at=run_at,
            prev_equity=prev_equity,
            capital_flow=capital_flow,
            warnings=notes,
        )
        _persist_run_result(
            json_out=args.json_out,
            payload={
                "spec": args.spec,
                "signal_date": str(signal_date.date()),
                "execution_hint": str(execution_hint),
                "live_execution_hint": str(execution_hint),
                "client_oid_prefix": client_oid_prefix,
                "quotes": {
                    asset: quotes[symbol].as_dict()
                    for asset, symbol in relevant_symbols.items()
                    if asset in required_assets and symbol in quotes
                },
                "plan": plan.as_dict(),
                "report": report.as_dict(),
                "status": status,
            },
            journal_file=args.journal_file,
            entry=entry,
            state_file=args.state_file,
            key=key,
            status=status,
            report=report,
            notify=notify_report if args.notify else None,
        )
        print(f"journal updated: {args.journal_file} ({entry.date})")
    elif args.notify:
        notify_report()

    if report.failures:
        print(f"{len(report.failures)} order(s) failed; state written as {status}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
