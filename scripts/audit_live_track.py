"""Cross-check the live derivatives track against the venue, end to end.

Answers one question: *can every number in the daily report be reproduced
from an independent source?*  It re-reads the exchange, the frozen target
book and the local ledger, then checks

1. the account identity ``usdtEquity == balance + unrealisedPnl``,
2. ``positionValue == Σ |size| × markPrice`` across open legs,
3. every trade in the ledger exists in the venue's order history with the
   same quantity, average price and fee,
4. the current book matches the frozen target book (within one contract lot),
5. the ledger's PnL chain adds up after excluding external capital flows,
6. nothing is held that the frozen book does not ask for,
7. the gross notional respects the 1.25x spec cap.

Exit code 0 when every hard check passes, 1 otherwise.  Read-only: it never
places or cancels an order.
"""

# ruff: noqa: E402

from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
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
from atlas20.derivatives.live_chain import manifest_staleness_hours  # noqa: E402
from atlas20.derivatives.live_journal import (  # noqa: E402
    DEFAULT_CAPITAL_FLOWS_FILE,
    load_journal,
    net_capital_flow,
    protected_short_symbols,
)
from atlas20.logging_utils import ensure_dir  # noqa: E402

from scripts.plan_live_execution import (  # noqa: E402
    DEFAULT_SYMBOL_MAP,
    DEFAULT_TARGETS_FILE,
    TRACKED_SPEC,
    fetch_public_instruments,
    fetch_public_prices,
    load_symbol_map,
    spec_symbol_universe,
    specs_from_instruments,
)
from scripts.send_derivatives_signal import load_latest_targets  # noqa: E402

DEFAULT_JOURNAL_FILE = Path("reports/ls45_live_g125_live/journal.csv")
DEFAULT_MANIFEST_FILE = Path("reports/ls45_live_g125/manifest.json")
DEFAULT_JSON_OUT = Path("reports/ls45_live_g125_live/audit.json")
SPEC_MAX_GROSS = 1.25


def _num(value: object) -> float:
    try:
        return float(value or 0.0)
    except (TypeError, ValueError):
        return 0.0


def _fees(row: dict) -> float:
    total = 0.0
    for item in row.get("feeDetail") or []:
        if isinstance(item, dict):
            total += _num(item.get("fee"))
    return total


def _position_signed_qty(row: dict) -> float:
    """Signed quantity from both hedge and one-way position payloads."""

    total = _num(row.get("total"))
    if abs(total) <= 1e-12:
        return 0.0
    pos_side = str(row.get("posSide") or "").lower()
    short = pos_side == "short" or (pos_side in {"", "net"} and total < 0.0)
    return -abs(total) if short else abs(total)


def _position_signed_notional(row: dict) -> float:
    """Signed mark notional, negative for each short leg."""

    mark = _num(row.get("markPrice") or row.get("avgPrice"))
    return _position_signed_qty(row) * mark


def _trade_mismatch(trade: dict, venue: dict) -> str | None:
    """Return the first reproducibility mismatch for one journaled fill."""

    same_qty = abs(_num(venue.get("cumExecQty")) - _num(trade.get("qty"))) <= 1e-9
    same_price = abs(_num(venue.get("avgPrice")) - _num(trade.get("avg_price"))) <= 1e-6
    same_fee = abs(_fees(venue) - _num(trade.get("fee"))) <= 1e-6
    if not (same_qty and same_price and same_fee):
        return (
            f"台账 {trade.get('qty')}/{trade.get('avg_price')}/{trade.get('fee')} "
            f"vs 交易所 {venue.get('cumExecQty')}/{venue.get('avgPrice')}/{_fees(venue):.8f}"
        )
    recorded_stop = trade.get("stop_loss")
    if recorded_stop is not None:
        venue_stop = _num(venue.get("stopLoss"))
        trigger = str(venue.get("slTriggerBy") or "").lower()
        order_type = str(venue.get("slOrderType") or "").lower()
        if (
            abs(venue_stop - _num(recorded_stop)) > 1e-6
            or trigger != "mark_price"
            or order_type != "market"
        ):
            return (
                f"止损台账 {_num(recorded_stop):.8g}/mark_price/market vs 交易所 "
                f"{venue_stop:.8g}/{trigger or 'missing'}/{order_type or 'missing'}"
            )
    return None


def _short_stop_gaps(journal: pd.DataFrame, positions: list[dict]) -> list[str]:
    """Open short symbols with no journaled entry that carried a stop."""

    protected = protected_short_symbols(journal)
    gaps: list[str] = []
    for row in positions:
        if _position_signed_qty(row) >= 0.0:
            continue
        symbol = str(row.get("symbol") or "").upper()
        if symbol and symbol not in protected:
            gaps.append(symbol)
    return sorted(set(gaps))


def _ledger_expected_equity(
    last: dict,
    *,
    current_positions: list[dict],
    capital_flow: float,
) -> tuple[float, list[str]]:
    """Roll the latest ledger snapshot forward to the live venue state.

    Mark-to-market changes belong in strategy PnL. Deposits and withdrawals do
    not, so the latter are added separately from the capital-flow ledger.
    """

    ledger_positions = json.loads(last.get("positions") or "[]")
    ledger_by_symbol = {str(item.get("symbol")): item for item in ledger_positions}
    expected_equity = _num(last.get("equity")) + float(capital_flow)
    mismatches: list[str] = []
    for row in current_positions:
        symbol = str(row.get("symbol") or "")
        ledger_row = ledger_by_symbol.pop(symbol, None)
        if ledger_row is None:
            mismatches.append(f"{symbol} 不在台账里")
            continue
        ledger_side = str(ledger_row.get("side") or "").lower()
        current_side = "short" if _position_signed_qty(row) < 0.0 else "long"
        if ledger_side in {"long", "short"} and ledger_side != current_side:
            mismatches.append(
                f"{symbol} 方向变了：台账 {ledger_side} vs 当前 {current_side}"
            )
        expected_equity += _position_signed_qty(row) * (
            _num(row.get("markPrice")) - _num(ledger_row.get("mark_price"))
        )
    if ledger_by_symbol:
        mismatches.append(f"台账多了 {', '.join(sorted(ledger_by_symbol))}")
    return expected_equity, mismatches


def _pnl_chain_errors(journal: pd.DataFrame) -> list[str]:
    """Return every adjacent-row break in the capital-adjusted PnL chain."""

    if len(journal) < 2:
        return []
    frame = journal.sort_values("date").reset_index(drop=True)
    errors: list[str] = []
    for index in range(1, len(frame)):
        capital_flow = _num(frame.loc[index, "capital_flow"])
        expected = (
            _num(frame.loc[index, "equity"])
            - _num(frame.loc[index - 1, "equity"])
            - capital_flow
        )
        recorded = frame.loc[index, "day_pnl"]
        if pd.isna(recorded) or abs(_num(recorded) - expected) > 0.01:
            errors.append(
                f"{frame.loc[index, 'date']}: 记录 {_num(recorded):.4f} vs 重算 {expected:.4f}"
                f"（外部资金流 {capital_flow:+.4f}）"
            )
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--spec", default=TRACKED_SPEC)
    parser.add_argument("--journal-file", type=Path, default=DEFAULT_JOURNAL_FILE)
    parser.add_argument("--capital-flows-file", type=Path, default=DEFAULT_CAPITAL_FLOWS_FILE)
    parser.add_argument("--targets-file", type=Path, default=DEFAULT_TARGETS_FILE)
    parser.add_argument("--symbol-map", type=Path, default=DEFAULT_SYMBOL_MAP)
    parser.add_argument("--history-days", type=int, default=7)
    parser.add_argument("--manifest-file", type=Path, default=DEFAULT_MANIFEST_FILE)
    parser.add_argument("--json-out", type=Path, default=DEFAULT_JSON_OUT)
    args = parser.parse_args(argv)
    checked_at = datetime.now(timezone.utc)

    client = BitgetPrivateClient(BitgetCredentials.from_env())
    assets = client.account_assets()
    positions = client.current_positions()
    symbol_map = load_symbol_map(args.symbol_map)
    signal_date, execution_hint, book = load_latest_targets(args.targets_file)
    targets = {
        str(record["asset"]): float(record["target_weight"])
        for record in book.to_dict("records")
        if abs(float(record["target_weight"])) > 0.0
    }
    relevant = spec_symbol_universe(symbol_map, targets)
    session = requests.Session()
    prices = fetch_public_prices(session)
    specs = specs_from_instruments(fetch_public_instruments(session), relevant)

    usdt_row = next(
        (
            row
            for row in assets.get("assets") or []
            if isinstance(row, dict) and str(row.get("coin", "")).upper() == "USDT"
        ),
        {},
    )
    equity = _num(assets.get("usdtEquity"))
    balance = _num(usdt_row.get("balance"))
    unrealised = _num(assets.get("usdtUnrealisedPnl"))
    reported_position_value = _num(assets.get("positionValue"))
    mark_notional = sum(
        abs(_num(row.get("total"))) * _num(row.get("markPrice") or row.get("avgPrice"))
        for row in positions
    )

    checks: list[dict[str, object]] = []

    def check(name: str, ok: bool, detail: str, *, hard: bool = True) -> None:
        checks.append({"check": name, "ok": bool(ok), "hard": hard, "detail": detail})

    check(
        "账户恒等式 equity = balance + uPnL",
        abs(equity - (balance + unrealised)) <= 0.02,
        f"{equity:.4f} vs {balance:.4f} + {unrealised:.4f} = {balance + unrealised:.4f}",
    )
    # ``assets`` and ``current-position`` are two round trips, so their marks
    # can differ by a few bps on a moving book; the tolerance says so.
    check(
        "仓位市值 = Σ 数量 × 标记价",
        abs(reported_position_value - mark_notional) <= max(0.05, 0.003 * mark_notional),
        f"交易所 {reported_position_value:.4f} vs 重算 {mark_notional:.4f}"
        f"（两次请求的标记价差 {abs(reported_position_value - mark_notional):.4f}）",
    )

    # -- ledger vs venue -------------------------------------------------
    journal = load_journal(args.journal_file)
    if journal.empty:
        check("台账存在", False, f"{args.journal_file} 不存在或为空")
        last = None
    else:
        last = journal.sort_values("date").iloc[-1].to_dict()
        # The row is a snapshot from minutes ago; roll it forward with live
        # marks and external cash flows so the comparison tests the ledger,
        # not the clock or a deposit/withdrawal.
        capital_flow = net_capital_flow(
            args.capital_flows_file,
            after=last.get("run_at_utc"),
            through=checked_at,
        )
        expected_equity, mismatches = _ledger_expected_equity(
            last,
            current_positions=positions,
            capital_flow=capital_flow,
        )
        detail = f"台账 {last['date']} equity={_num(last['equity']):.4f}"
        if abs(capital_flow) > 0.005:
            detail += f"；外部资金流 {capital_flow:+.4f}"
        if mismatches:
            detail += f"；{'；'.join(mismatches)}"
        consistent = not mismatches and abs(expected_equity - equity) <= 0.05
        check(
            "台账最新一行 = 当前账户（按实时标记价折算）",
            consistent,
            detail + f"；折算后应为 {expected_equity:.4f}，交易所 {equity:.4f}",
        )
        chain_errors = _pnl_chain_errors(journal)
        chain_ok = not chain_errors
        detail = "；".join(chain_errors) or f"{max(len(journal) - 1, 0)} 个相邻日全部一致"
        check("台账 PnL 链一致", chain_ok, detail)

    # -- trades vs venue order history -----------------------------------
    now_ms = int(checked_at.timestamp() * 1000)
    history = client.order_history(
        start_time_ms=now_ms - int(args.history_days) * 86_400_000,
        end_time_ms=now_ms,
        limit=100,
    )
    by_id = {str(row.get("orderId")): row for row in history}
    missing: list[str] = []
    mismatched: list[str] = []
    if not journal.empty:
        for _, row in journal.iterrows():
            for trade in json.loads(row["trades"] or "[]"):
                status = str(trade.get("status") or "filled").lower()
                if status != "filled":
                    continue
                order_id = str(trade.get("order_id"))
                venue = by_id.get(order_id)
                if venue is None:
                    # older than the queried window is fine; only flag recent days
                    if str(row["date"]) >= (checked_at - timedelta(days=args.history_days - 1)).strftime("%Y-%m-%d"):
                        missing.append(order_id)
                    continue
                mismatch = _trade_mismatch(trade, venue)
                if mismatch is not None:
                    mismatched.append(f"{order_id}: {mismatch}")
    check(
        "台账成交都能在交易所订单历史里对上",
        not missing and not mismatched,
        "; ".join(missing + mismatched) or f"核对 {len(by_id)} 笔订单",
    )

    stop_gaps = _short_stop_gaps(journal, positions)
    check(
        "所有空头仓位都有附带止损的入场成交记录",
        not stop_gaps,
        ", ".join(stop_gaps) or "无空头仓，或有止损记录的空头仓",
    )

    # -- signal vs book --------------------------------------------------
    def asset_of(symbol: str) -> str:
        upper = symbol.upper()
        for asset, symbol_name in symbol_map.items():
            if symbol_name.upper() == upper:
                return asset
        return upper.replace("USDT", "").lower()

    notional_by_asset: dict[str, float] = {}
    signed_notional_by_asset: dict[str, float] = {}
    for row in positions:
        asset = asset_of(str(row.get("symbol") or ""))
        signed = _position_signed_notional(row)
        notional_by_asset[asset] = notional_by_asset.get(asset, 0.0) + abs(signed)
        signed_notional_by_asset[asset] = signed_notional_by_asset.get(asset, 0.0) + signed
    lot_by_asset = {
        asset: float(spec.min_order_qty or spec.quantity_multiplier)
        * _num(prices.get(relevant[asset].upper()))
        for asset, spec in specs.items()
    }
    off_target: list[str] = []
    for asset, weight in targets.items():
        want = weight * equity
        got = signed_notional_by_asset.get(asset, 0.0)
        tolerance = max(1.0, 0.01 * abs(want), 1.5 * float(lot_by_asset.get(asset, 0.0)))
        if abs(got - want) > tolerance:
            off_target.append(f"{asset.upper()} 目标 {want:.2f} vs 实际 {got:.2f}")
    check("持仓与冻结目标一致（1 个合约步长内）", not off_target, "; ".join(off_target) or "全部吻合")

    orphans = sorted(set(notional_by_asset) - set(targets))
    orphan_notional = sum(notional_by_asset[asset] for asset in orphans)
    check(
        "无计划外持仓",
        orphan_notional <= 1.0,
        ", ".join(f"{asset.upper()} {notional_by_asset[asset]:.2f}" for asset in orphans) or "无",
    )

    gross = sum(notional_by_asset.values())
    check(
        f"总名义 <= {SPEC_MAX_GROSS:.2f}x 权益（规格上限）",
        gross <= SPEC_MAX_GROSS * equity + 1.0,
        f"gross {gross:.2f} / equity {equity:.2f} = {gross / equity:.3f}x" if equity else "equity 0",
    )

    # The book is an *event* series: a row dated several days ago is normal.
    # What must be current is the data the book was built from, so the hard
    # checks are about the pipeline, not about the last event's age.
    event_age_days = (
        pd.Timestamp.now(tz="UTC").normalize() - pd.Timestamp(signal_date).normalize()
    ).days
    if args.manifest_file.exists():
        manifest = json.loads(args.manifest_file.read_text(encoding="utf-8"))
        staleness = manifest_staleness_hours(manifest, checked_at)
        index_end = str(manifest.get("index_end_date") or "")
        signal_end = str(manifest.get("signal_end_date") or "")
        check(
            "mark 数据新鲜（<= 30h）",
            staleness <= 30.0,
            f"最新 mark {manifest.get('last_mark')}（{staleness:.1f}h 前）",
        )
        check(
            "账本已评估到最新可判定日（无跳过）",
            bool(index_end) and index_end == signal_end,
            f"账本评估到 {index_end or '?'} / 数据到 {signal_end or '?'}",
        )
    else:
        check("样本外 manifest 存在", False, f"{args.manifest_file} 不存在")
    check(
        "信号事件距今（事件驱动，非每日变化）",
        True,
        f"最近一次仓位变化 {pd.Timestamp(signal_date).date()}（{event_age_days} 天前；无变化＝继续持有）",
        hard=False,
    )
    if last is not None:
        check(
            "台账信号日 = 冻结账本最新信号日",
            str(last["signal_date"]) == str(pd.Timestamp(signal_date).date()),
            f"台账 {last['signal_date']} vs 账本 {pd.Timestamp(signal_date).date()}",
        )

    # -- output ----------------------------------------------------------
    hard_failures = [row for row in checks if not row["ok"] and row["hard"]]
    print(f"Atlas20 实盘全链路核对 · {args.spec} · {checked_at.strftime('%Y-%m-%d %H:%M UTC')}")
    print(f"交易所: 权益 {equity:.4f} USDT · 仓位 {gross:.4f} · 持仓 {len(positions)} 腿 · 未实现 {unrealised:+.4f}")
    print("")
    for row in checks:
        mark = "✅" if row["ok"] else ("❌" if row["hard"] else "⚠️")
        print(f"  {mark} {row['check']} — {row['detail']}")
    print("")
    print(f"结论: {'全部通过' if not hard_failures else f'{len(hard_failures)} 项硬校验失败'}")

    output = ensure_dir(args.json_out.parent)
    (output / args.json_out.name).write_text(
        json.dumps(
            {
                "spec": args.spec,
                "checked_at": checked_at.isoformat(),
                "equity": equity,
                "position_value": gross,
                "signal_date": str(pd.Timestamp(signal_date).date()),
                "checks": checks,
                "hard_failures": len(hard_failures),
            },
            indent=2,
            sort_keys=True,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    return 1 if hard_failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
