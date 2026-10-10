"""Read-only live health monitor: the check that runs *between* rebalances.

The daily executor already re-reads the real account every day at 11:05
Beijing. This script adds the missing piece: a scheduled, read-only probe that
answers "is anything wrong right now?" without waiting for the next rebalance.

It never places orders and never touches the executor's idempotency state. It
runs the full audit (``scripts/audit_live_track.py``) plus two checks the audit
does not cover on its own, and pushes a Telegram alert **only when something
needs attention** - the daily rebalance report stays the only routine message.

Checks:

1. the 12-item live audit (venue vs ledger, target alignment, gross cap, mark
   freshness, ...) - any hard failure is an alert;
2. position drift vs the frozen target beyond what the 5 USDT rebalance
   threshold would correct on the next run;
3. gross notional / equity within the 1.25x specification cap;
4. execution freshness: the last successful run is too old, or today's run is
   already overdue (after 06:00 UTC);
5. account equity above the executor's floor.

Exit code is 0 when healthy (and with ``--quiet`` nothing is printed/sent),
1 when an alert was sent.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import sys

import requests

# ruff: noqa: E402

PROJECT_ROOT = Path(__file__).resolve().parents[1]
for path in (PROJECT_ROOT, PROJECT_ROOT / "src"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from atlas20.derivatives.account import BitgetCredentials, BitgetPrivateClient  # noqa: E402
from atlas20.derivatives.live_journal import load_journal, previous_row  # noqa: E402
from atlas20.logging_utils import ensure_dir  # noqa: E402

from scripts.audit_live_track import (  # noqa: E402
    DEFAULT_JOURNAL_FILE,
    DEFAULT_MANIFEST_FILE,
    DEFAULT_TARGETS_FILE,
)
from scripts.plan_live_execution import (  # noqa: E402
    DEFAULT_SYMBOL_MAP,
    fetch_public_instruments,
    fetch_public_prices,
    load_symbol_map,
    specs_from_instruments,
)
from scripts.send_derivatives_signal import load_latest_targets  # noqa: E402
from scripts.send_telegram_signal import _chat_ids, send_telegram_message  # noqa: E402

DEFAULT_STATE_FILE = Path("data/derivatives_execution_state.json")
DEFAULT_OUT = Path("reports/derivatives_track_live/health.json")
AUDIT_SCRIPT = PROJECT_ROOT / "scripts" / "audit_live_track.py"
SPEC_MAX_GROSS = 1.25
EXECUTION_FLOOR_USDT = 20.0
EXECUTION_OVERDUE_UTC_HOUR = 6  # by 11:05 Beijing the daily run should have landed
MAX_EXECUTION_AGE_HOURS = 36.0


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state-file", type=Path, default=DEFAULT_STATE_FILE)
    parser.add_argument("--journal-file", type=Path, default=DEFAULT_JOURNAL_FILE)
    parser.add_argument("--targets-file", type=Path, default=DEFAULT_TARGETS_FILE)
    parser.add_argument("--symbol-map", type=Path, default=DEFAULT_SYMBOL_MAP)
    parser.add_argument("--manifest-file", type=Path, default=DEFAULT_MANIFEST_FILE)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--notify", action="store_true", help="send the alert to Telegram")
    parser.add_argument(
        "--always-report",
        action="store_true",
        help="send a message even when healthy (default: silence = healthy)",
    )
    parser.add_argument("--quiet", action="store_true")
    return parser.parse_args(argv)


def _run_audit() -> tuple[int, dict]:
    """Run the read-only audit in a subprocess and parse its JSON payload."""

    import tempfile

    with tempfile.TemporaryDirectory(prefix="atlas20-monitor-") as tmp:
        json_out = Path(tmp) / "audit.json"
        proc = subprocess.run(
            [sys.executable, str(AUDIT_SCRIPT), "--json-out", str(json_out)],
            cwd=str(PROJECT_ROOT),
            capture_output=True,
            text=True,
            timeout=180,
        )
        payload = json.loads(json_out.read_text(encoding="utf-8")) if json_out.exists() else {}
        return proc.returncode, payload


def _position_notional(positions: list[dict], symbol_map: dict[str, str]) -> dict[str, float]:
    by_symbol = {str(sym).upper(): asset for asset, sym in symbol_map.items()}
    out: dict[str, float] = {}
    for row in positions:
        symbol = str(row.get("symbol") or "").upper()
        asset = by_symbol.get(symbol)
        if asset is None:
            continue
        price = float(row.get("markPrice") or row.get("avgPrice") or 0.0)
        out[asset] = abs(float(row.get("total") or 0.0)) * price
    return out


def _execution_freshness(state_file: Path, now: datetime) -> tuple[bool, str]:
    """Fail when the daily run is missing today (after 06:00 UTC) or too old."""

    if not state_file.exists():
        return False, "no execution state file; the daily run has never completed"
    state = json.loads(state_file.read_text(encoding="utf-8"))
    last_at = state.get("last_run_at") or ""
    if not last_at:
        return False, "execution state has no last_run_at"
    last = datetime.fromisoformat(str(last_at))
    if last.tzinfo is None:
        last = last.replace(tzinfo=timezone.utc)
    age_hours = (now - last).total_seconds() / 3600.0
    today = now.strftime("%Y-%m-%d")
    ran_today = last.astimezone(timezone.utc).strftime("%Y-%m-%d") == today
    if now.hour >= EXECUTION_OVERDUE_UTC_HOUR and not ran_today:
        return False, f"今天的调仓还没执行（状态文件最后成功：{last_at}）"
    if age_hours > MAX_EXECUTION_AGE_HOURS:
        return False, f"超过 {MAX_EXECUTION_AGE_HOURS:.0f}h 没有成功执行（最后：{last_at}）"
    return True, f"最近成功执行 {last_at}（{age_hours:.1f}h 前）"


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    now = datetime.now(timezone.utc)

    audit_exit, audit = _run_audit()
    audit_failures = int(audit.get("hard_failures") or 0)
    equity = float(audit.get("equity") or 0.0)
    gross = float(audit.get("position_value") or 0.0)
    signal_date = str(audit.get("signal_date") or "?")

    client = BitgetPrivateClient(BitgetCredentials.from_env())
    positions = client.current_positions()
    symbol_map = load_symbol_map(args.symbol_map)
    signal_date, _hint, book = load_latest_targets(args.targets_file)
    targets = {
        str(record["asset"]): float(record["target_weight"])
        for record in book.to_dict("records")
        if abs(float(record["target_weight"])) > 0.0
    }

    session = requests.Session()
    prices = fetch_public_prices(session)
    specs = specs_from_instruments(
        fetch_public_instruments(session),
        {asset: symbol_map.get(asset, f"{asset.upper()}USDT") for asset in targets},
    )

    issues: list[str] = []
    if audit_exit != 0 or audit_failures:
        issues.append(f"全链路核对有 {audit_failures} 项硬失败（跑 make audit-live 看明细）")

    actual = _position_notional(positions, symbol_map)
    for asset, weight in targets.items():
        symbol = symbol_map.get(asset, f"{asset.upper()}USDT")
        price = float(prices.get(symbol.upper()) or 0.0)
        spec = specs.get(asset)
        lot_notional = (
            float(spec.min_order_qty or spec.quantity_multiplier) * price
            if spec is not None and price > 0
            else 0.0
        )
        want = weight * equity
        got = actual.get(asset, 0.0)
        # The executor only trades gaps above 5 USDT; anything larger that
        # survives to a monitor run means the rebalance did not land.
        tolerance = max(5.0, 0.02 * want, 1.5 * lot_notional)
        if abs(got - want) > tolerance:
            direction = "低" if got < want else "高"
            issues.append(
                f"{asset.upper()} 仓位偏离冻结目标 {abs(got - want):.1f} USDT（实际 {got:.1f} / 目标 {want:.1f}，偏{direction}）"
            )

    ratio = gross / equity if equity else float("inf")
    if ratio > SPEC_MAX_GROSS:
        issues.append(f"总名义 {ratio:.2f}x 权益，超过规格上限 {SPEC_MAX_GROSS:.2f}x")

    if equity < EXECUTION_FLOOR_USDT:
        issues.append(f"权益 {equity:.2f} USDT 低于执行下限 {EXECUTION_FLOOR_USDT:.0f}")

    fresh_ok, fresh_detail = _execution_freshness(args.state_file, now)
    if not fresh_ok:
        issues.append(fresh_detail)

    journal = load_journal(args.journal_file)
    previous = previous_row(journal, now.strftime("%Y-%m-%d"))
    prev_equity = (
        float(previous["equity"]) if previous is not None and previous.get("equity") is not None else None
    )
    day_pnl = equity - prev_equity if prev_equity is not None else None

    flags = {"audit_exit": audit_exit, "issues": issues, "checked_at": now.isoformat()}
    ensure_dir(args.out.parent)
    args.out.write_text(json.dumps(flags, indent=2, ensure_ascii=False), encoding="utf-8")

    lines = [
        "🩺 Atlas20 实盘巡检",
        f"账户总价值: {equity:.2f} USDT",
        f"仓位价值: {gross:.2f} USDT（{ratio:.2f}x）",
    ]
    if day_pnl is not None:
        lines.append(f"较上次记账: {day_pnl:+.2f} USDT")
    lines.append(f"当前信号日: {signal_date}")
    lines.append(f"最近执行: {fresh_detail}")
    if issues:
        lines.append("")
        lines.append("⚠️ 需要处理:")
        lines.extend(f"• {item}" for item in issues)
    else:
        lines.append("")
        lines.append("✅ 全部正常（这条只在有异常时才发）")

    message = "\n".join(lines)
    if not args.quiet:
        print(message)

    if issues or args.always_report:
        token = os.environ.get("ATLAS20_TELEGRAM_BOT_TOKEN", "")
        chat_ids = _chat_ids(os.environ.get("ATLAS20_TELEGRAM_CHAT_ID"))
        if args.notify and token and chat_ids:
            for chat_id in chat_ids:
                send_telegram_message(message, token=token, chat_id=chat_id)
        elif args.notify:
            print("monitor: no telegram credentials in environment; alert not sent", file=sys.stderr)

    return 1 if issues else 0


if __name__ == "__main__":
    raise SystemExit(main())
