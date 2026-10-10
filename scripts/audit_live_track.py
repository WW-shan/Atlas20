"""Cross-check the live derivatives track against the venue, end to end.

Answers one question: *can every number in the daily report be reproduced
from an independent source?*  It re-reads the exchange, the frozen target
book and the local ledger, then checks

1. the account identity ``usdtEquity == balance + unrealisedPnl``,
2. ``positionValue == Σ |size| × markPrice`` across open legs,
3. every trade in the ledger exists in the venue's order history with the
   same quantity, average price and fee,
4. the current book matches the frozen target book (within one contract lot),
5. the ledger's PnL chain adds up (``Σ day_pnl == equity_end - equity_start``),
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
from atlas20.derivatives.live_journal import load_journal  # noqa: E402
from atlas20.logging_utils import ensure_dir  # noqa: E402

from scripts.plan_live_execution import (  # noqa: E402
    DEFAULT_SYMBOL_MAP,
    DEFAULT_TARGETS_FILE,
    TRACKED_SPEC,
    fetch_public_instruments,
    fetch_public_prices,
    load_symbol_map,
    specs_from_instruments,
)
from scripts.send_derivatives_signal import load_latest_targets  # noqa: E402

DEFAULT_JOURNAL_FILE = Path("reports/derivatives_track_live/journal.csv")
DEFAULT_JSON_OUT = Path("reports/derivatives_track_live/audit.json")
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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--spec", default=TRACKED_SPEC)
    parser.add_argument("--journal-file", type=Path, default=DEFAULT_JOURNAL_FILE)
    parser.add_argument("--targets-file", type=Path, default=DEFAULT_TARGETS_FILE)
    parser.add_argument("--symbol-map", type=Path, default=DEFAULT_SYMBOL_MAP)
    parser.add_argument("--history-days", type=int, default=7)
    parser.add_argument("--json-out", type=Path, default=DEFAULT_JSON_OUT)
    args = parser.parse_args(argv)

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
    relevant = {asset: symbol_map.get(asset, f"{asset.upper()}USDT") for asset in targets}
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
        # The row is a snapshot from minutes ago; roll it forward with the
        # live marks so the comparison tests the ledger, not the clock.
        ledger_positions = json.loads(last["positions"] or "[]")
        ledger_by_symbol = {str(item.get("symbol")): item for item in ledger_positions}
        expected_equity = _num(last["equity"])
        consistent = True
        detail = f"台账 {last['date']} equity={_num(last['equity']):.4f}"
        for row in positions:
            symbol = str(row.get("symbol") or "")
            ledger_row = ledger_by_symbol.pop(symbol, None)
            if ledger_row is None:
                consistent = False
                detail += f"；{symbol} 不在台账里"
                continue
            expected_equity += abs(_num(row.get("total"))) * (
                _num(row.get("markPrice")) - _num(ledger_row.get("mark_price"))
            )
        if ledger_by_symbol:
            consistent = False
            detail += f"；台账多了 {', '.join(sorted(ledger_by_symbol))}"
        consistent = consistent and abs(expected_equity - equity) <= 0.05
        check(
            "台账最新一行 = 当前账户（按实时标记价折算）",
            consistent,
            detail + f"；折算后应为 {expected_equity:.4f}，交易所 {equity:.4f}",
        )
        chain_ok = True
        detail = "无可校验的相邻行"
        if len(journal) >= 2:
            frame = journal.sort_values("date").reset_index(drop=True)
            detail_parts = []
            for index in range(1, len(frame)):
                expected = _num(frame.loc[index, "equity"]) - _num(frame.loc[index - 1, "equity"])
                recorded = frame.loc[index, "day_pnl"]
                recorded_value = _num(recorded)
                if pd.isna(recorded) or abs(recorded_value - expected) > 0.01:
                    chain_ok = False
                    detail_parts.append(
                        f"{frame.loc[index, 'date']}: 记录 {recorded_value:.4f} vs 重算 {expected:.4f}"
                    )
            detail = "；".join(detail_parts) or f"{len(frame) - 1} 个相邻日全部一致"
        check("台账 PnL 链一致", chain_ok, detail)

    # -- trades vs venue order history -----------------------------------
    now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
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
                order_id = str(trade.get("order_id"))
                venue = by_id.get(order_id)
                if venue is None:
                    # older than the queried window is fine; only flag recent days
                    if str(row["date"]) >= (datetime.now(timezone.utc) - timedelta(days=args.history_days - 1)).strftime("%Y-%m-%d"):
                        missing.append(order_id)
                    continue
                same_qty = abs(_num(venue.get("cumExecQty")) - _num(trade.get("qty"))) <= 1e-9
                same_price = abs(_num(venue.get("avgPrice")) - _num(trade.get("avg_price"))) <= 1e-6
                same_fee = abs(_fees(venue) - _num(trade.get("fee"))) <= 1e-6
                if not (same_qty and same_price and same_fee):
                    mismatched.append(
                        f"{order_id}: 台账 {trade.get('qty')}/{trade.get('avg_price')}/{trade.get('fee')}"
                        f" vs 交易所 {venue.get('cumExecQty')}/{venue.get('avgPrice')}/{_fees(venue):.8f}"
                    )
    check(
        "台账成交都能在交易所订单历史里对上",
        not missing and not mismatched,
        "; ".join(missing + mismatched) or f"核对 {len(by_id)} 笔订单",
    )

    # -- signal vs book --------------------------------------------------
    def asset_of(symbol: str) -> str:
        upper = symbol.upper()
        for asset, symbol_name in symbol_map.items():
            if symbol_name.upper() == upper:
                return asset
        return upper.replace("USDT", "").lower()

    notional_by_asset: dict[str, float] = {}
    for row in positions:
        asset = asset_of(str(row.get("symbol") or ""))
        notional_by_asset[asset] = abs(_num(row.get("total"))) * _num(
            row.get("markPrice") or row.get("avgPrice")
        )
    lot_by_asset = {
        asset: float(spec.min_order_qty or spec.quantity_multiplier)
        * _num(prices.get(relevant[asset].upper()))
        for asset, spec in specs.items()
    }
    off_target: list[str] = []
    for asset, weight in targets.items():
        want = weight * equity
        got = notional_by_asset.get(asset, 0.0)
        tolerance = max(1.0, 0.01 * want, 1.5 * float(lot_by_asset.get(asset, 0.0)))
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

    age_hours = (pd.Timestamp.now(tz="UTC") - pd.Timestamp(signal_date)).total_seconds() / 3600.0
    check(
        "信号新鲜度（<= 36h，硬门槛为执行时）",
        age_hours <= 36.0,
        f"信号日 {pd.Timestamp(signal_date).date()}（{age_hours:.1f}h 前）",
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
    print(f"Atlas20 实盘全链路核对 · {args.spec} · {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
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
                "checked_at": datetime.now(timezone.utc).isoformat(),
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
