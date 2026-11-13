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
   already overdue after the early window and fallbacks have had time to run;
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

import pandas as pd
import requests

# ruff: noqa: E402

PROJECT_ROOT = Path(__file__).resolve().parents[1]
for path in (PROJECT_ROOT, PROJECT_ROOT / "src"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from atlas20.derivatives.account import BitgetCredentials, BitgetPrivateClient  # noqa: E402
from atlas20.derivatives.live_journal import (  # noqa: E402
    DEFAULT_CAPITAL_FLOWS_FILE,
    latest_row,
    load_journal,
    net_capital_flow,
)
from atlas20.logging_utils import ensure_dir  # noqa: E402

from scripts.audit_live_track import (  # noqa: E402
    DEFAULT_JOURNAL_FILE,
    DEFAULT_MANIFEST_FILE,
    DEFAULT_TARGETS_FILE,
    _position_signed_notional,
)
from scripts.plan_live_execution import (  # noqa: E402
    DEFAULT_SYMBOL_MAP,
    fetch_public_instruments,
    fetch_public_prices,
    load_symbol_map,
    spec_symbol_universe,
    specs_from_instruments,
)
from scripts.send_derivatives_signal import load_latest_targets  # noqa: E402
from scripts.send_telegram_signal import _chat_ids, send_telegram_message  # noqa: E402

DEFAULT_STATE_FILE = Path("data/ls45_g125_execution_state.json")
DEFAULT_OUT = Path("reports/ls45_live_g125_live/health.json")
AUDIT_SCRIPT = PROJECT_ROOT / "scripts" / "audit_live_track.py"
SPEC_MAX_GROSS = 1.25
EXECUTION_FLOOR_USDT = 20.0
EXECUTION_OVERDUE_UTC_HOUR = 7  # after the 06:35 UTC final fallback has landed
MAX_EXECUTION_AGE_HOURS = 36.0


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state-file", type=Path, default=DEFAULT_STATE_FILE)
    parser.add_argument("--journal-file", type=Path, default=DEFAULT_JOURNAL_FILE)
    parser.add_argument("--capital-flows-file", type=Path, default=DEFAULT_CAPITAL_FLOWS_FILE)
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


def _audit_command(json_out: Path, capital_flows_file: Path) -> list[str]:
    return [
        sys.executable,
        str(AUDIT_SCRIPT),
        "--json-out",
        str(json_out),
        "--capital-flows-file",
        str(capital_flows_file),
    ]


def _audit_metrics(audit: dict) -> tuple[float | None, float | None]:
    def metric(key: str) -> float | None:
        value = audit.get(key)
        if value is None or value == "":
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    return metric("equity"), metric("position_value")


def _gross_ratio(*, gross: float, equity: float) -> float | None:
    return gross / equity if equity > 0 else None


def _audit_failure_details(
    audit: dict,
    *,
    exit_code: int = 0,
    stderr: str = "",
) -> str:
    failures = [
        row
        for row in audit.get("checks") or []
        if isinstance(row, dict) and row.get("hard") and not row.get("ok")
    ]
    if not failures:
        if exit_code != 0:
            diagnostic = stderr.strip()[-1_200:] or "未返回 stderr"
            return f"全链路核对进程失败（退出码 {exit_code}）：{diagnostic}"
        return "全链路核对失败（未返回明细；手动运行 make audit-live）"
    details = "；".join(
        f"{row.get('check') or '未命名检查'} — {row.get('detail') or '无详情'}"
        for row in failures
    )
    return f"全链路核对失败：{details}"


def _run_audit(capital_flows_file: Path) -> tuple[int, dict, str]:
    """Run the read-only audit in a subprocess and preserve failure diagnostics."""

    import tempfile

    with tempfile.TemporaryDirectory(prefix="atlas20-monitor-") as tmp:
        json_out = Path(tmp) / "audit.json"
        proc = subprocess.run(
            _audit_command(json_out, capital_flows_file),
            cwd=str(PROJECT_ROOT),
            capture_output=True,
            text=True,
            timeout=180,
        )
        payload: dict = {}
        stderr = proc.stderr.strip()
        if json_out.exists():
            try:
                payload = json.loads(json_out.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                stderr = f"{stderr}\naudit JSON unreadable: {exc}".strip()
        return proc.returncode, payload, stderr


def _position_notional(positions: list[dict], symbol_map: dict[str, str]) -> dict[str, float]:
    by_symbol = {str(sym).upper(): asset for asset, sym in symbol_map.items()}
    out: dict[str, float] = {}
    for row in positions:
        symbol = str(row.get("symbol") or "").upper()
        asset = by_symbol.get(symbol)
        if asset is None:
            continue
        out[asset] = out.get(asset, 0.0) + _position_signed_notional(row)
    return out


def _execution_freshness(state_file: Path, now: datetime) -> tuple[bool, str]:
    """Fail unless the latest daily run is both successful and recent."""

    if not state_file.exists():
        return False, "no execution state file; the daily run has never completed"
    state = json.loads(state_file.read_text(encoding="utf-8"))
    last_at = state.get("last_run_at") or ""
    if not last_at:
        return False, "execution state has no last_run_at"
    status = str(state.get("last_status") or "missing")
    if status != "ok":
        return False, f"最近一次调仓未完成（status={status}，最后尝试：{last_at}）"
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


def _ledger_change(
    journal: pd.DataFrame,
    capital_flows_file: Path,
    *,
    equity: float,
    now: datetime,
) -> float | None:
    """Account change since the latest ledger row, excluding outside cash."""

    latest = latest_row(journal)
    if latest is None or latest.get("equity") is None:
        return None
    flow = net_capital_flow(
        capital_flows_file,
        after=latest.get("run_at_utc"),
        through=now,
    )
    return equity - float(latest["equity"]) - flow


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    now = datetime.now(timezone.utc)

    audit_exit, audit, audit_stderr = _run_audit(args.capital_flows_file)
    audit_failures = int(audit.get("hard_failures") or 0)
    equity, gross = _audit_metrics(audit)
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
        spec_symbol_universe(symbol_map, targets),
    )

    issues: list[str] = []
    if audit_exit != 0 or audit_failures or equity is None or gross is None:
        issues.append(
            _audit_failure_details(
                audit,
                exit_code=audit_exit,
                stderr=audit_stderr,
            )
        )

    actual = _position_notional(positions, symbol_map)
    if equity is not None:
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
            tolerance = max(5.0, 0.02 * abs(want), 1.5 * lot_notional)
            if abs(got - want) > tolerance:
                direction = "低" if got < want else "高"
                issues.append(
                    f"{asset.upper()} 仓位偏离冻结目标 {abs(got - want):.1f} USDT（实际 {got:.1f} / 目标 {want:.1f}，偏{direction}）"
                )

    ratio = (
        _gross_ratio(gross=gross, equity=equity)
        if gross is not None and equity is not None
        else None
    )
    if ratio is not None and ratio > SPEC_MAX_GROSS:
        issues.append(f"总名义 {ratio:.2f}x 权益，超过规格上限 {SPEC_MAX_GROSS:.2f}x")
    elif equity is not None and equity <= 0 and gross is not None and gross > 1.0:
        issues.append(
            f"权益 {equity:.2f} USDT 但仓位价值 {gross:.2f} USDT，无法计算名义倍数，请立即核对"
        )

    if equity is not None and equity < EXECUTION_FLOOR_USDT:
        issues.append(f"权益 {equity:.2f} USDT 低于执行下限 {EXECUTION_FLOOR_USDT:.0f}")

    fresh_ok, fresh_detail = _execution_freshness(args.state_file, now)
    if not fresh_ok:
        issues.append(fresh_detail)

    journal = load_journal(args.journal_file)
    day_pnl = (
        _ledger_change(
            journal,
            args.capital_flows_file,
            equity=equity,
            now=now,
        )
        if equity is not None
        else None
    )

    flags = {
        "audit_exit": audit_exit,
        "audit_stderr": audit_stderr or None,
        "equity": equity,
        "position_value": gross,
        "issues": issues,
        "checked_at": now.isoformat(),
    }
    ensure_dir(args.out.parent)
    args.out.write_text(json.dumps(flags, indent=2, ensure_ascii=False), encoding="utf-8")

    equity_line = (
        f"账户总价值: {equity:.2f} USDT"
        if equity is not None
        else "账户总价值: 未知（全链路核对失败）"
    )
    if gross is None:
        position_line = "仓位价值: 未知（全链路核对失败）"
    elif ratio is None:
        position_line = f"仓位价值: {gross:.2f} USDT（权益≤0 或未知，比例不可计算）"
    else:
        position_line = f"仓位价值: {gross:.2f} USDT（{ratio:.2f}x）"
    lines = ["🩺 Atlas20 实盘巡检", equity_line, position_line]
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
