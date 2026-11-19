"""Read-only live health monitor: the check that runs *between* rebalances.

The daily executor already re-reads the real account every day at 09:05
Beijing; the signal ledger, live-parity research and live execution share that
T+1 01:05 UTC clock. This script adds the missing piece: a scheduled, read-only probe that
answers "is anything wrong right now?" without waiting for the next rebalance.

It never places orders and never touches the executor's idempotency state. It
runs the full audit (``scripts/audit_live_track.py``) plus two checks the audit
does not cover on its own, and pushes a Telegram alert **only when something
needs attention** - the daily rebalance report stays the only routine message.

Checks:

1. the full live audit (venue vs ledger, target alignment, gross cap, mark
   freshness, ...) - any hard failure is an alert;
2. position quantity drift vs the active event's frozen quantities beyond the
   venue lot tolerance; price-driven notional weight drift is not an alert;
3. gross notional / equity and isolated-margin utilization within the selected
   track profile caps;
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
from atlas20.derivatives.execution import ContractSpec  # noqa: E402
from atlas20.derivatives.live_chain import live_track_profile  # noqa: E402
from atlas20.derivatives.live_journal import (  # noqa: E402
    DEFAULT_CAPITAL_FLOWS_FILE,
    effective_event_target_quantities,
    latest_row,
    load_journal,
    net_capital_flow,
)
from atlas20.logging_utils import atomic_write_text, ensure_dir  # noqa: E402

from scripts.audit_live_track import (  # noqa: E402
    DEFAULT_JOURNAL_FILE,
    DEFAULT_MANIFEST_FILE,
    DEFAULT_TARGETS_FILE,
    _event_quantity_issues,
    _position_signed_notional,
    _unknown_position_symbols,
)
from scripts.plan_live_execution import (  # noqa: E402
    DEFAULT_SYMBOL_MAP,
    fetch_public_instruments,
    load_symbol_map,
    missing_asset_mappings,
    missing_contract_specs,
    spec_symbol_universe,
    specs_from_instruments,
    symbol_to_asset_index,
    target_weights_from_book,
    target_gross_weight,
)
from scripts.send_derivatives_signal import load_latest_targets  # noqa: E402
from scripts.send_telegram_signal import _chat_ids, send_telegram_message  # noqa: E402

DEFAULT_STATE_FILE = Path("data/ls45_g125_execution_state.json")
DEFAULT_OUT = Path("reports/ls45_live_g125_live/health.json")
DEFAULT_AUDIT_OUT = Path("reports/ls45_live_g125_live/audit.json")
DEFAULT_SPEC = "PR2026-11-LS45-H5-LS23-PROFITLOCK-STRONGER21"
AUDIT_SCRIPT = PROJECT_ROOT / "scripts" / "audit_live_track.py"
EXECUTION_FLOOR_USDT = 20.0
EXECUTION_OVERDUE_UTC_HOUR = 8  # after the 01:05 + 6h catch-up window closes at 07:05 UTC
MAX_EXECUTION_AGE_HOURS = 36.0


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--spec", default=DEFAULT_SPEC)
    parser.add_argument("--state-file", type=Path, default=DEFAULT_STATE_FILE)
    parser.add_argument("--journal-file", type=Path, default=DEFAULT_JOURNAL_FILE)
    parser.add_argument("--capital-flows-file", type=Path, default=DEFAULT_CAPITAL_FLOWS_FILE)
    parser.add_argument("--targets-file", type=Path, default=DEFAULT_TARGETS_FILE)
    parser.add_argument("--symbol-map", type=Path, default=DEFAULT_SYMBOL_MAP)
    parser.add_argument("--manifest-file", type=Path, default=DEFAULT_MANIFEST_FILE)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--audit-out", type=Path, default=DEFAULT_AUDIT_OUT)
    parser.add_argument("--prior-track-registry", type=Path, default=None)
    parser.add_argument("--notify", action="store_true", help="send the alert to Telegram")
    parser.add_argument(
        "--always-report",
        action="store_true",
        help="send a message even when healthy (default: silence = healthy)",
    )
    parser.add_argument("--quiet", action="store_true")
    return parser.parse_args(argv)


def _audit_command(
    json_out: Path,
    capital_flows_file: Path,
    *,
    spec: str = DEFAULT_SPEC,
    targets_file: Path = DEFAULT_TARGETS_FILE,
    manifest_file: Path = DEFAULT_MANIFEST_FILE,
    state_file: Path = DEFAULT_STATE_FILE,
    journal_file: Path = DEFAULT_JOURNAL_FILE,
    prior_track_registry: Path | None = None,
) -> list[str]:
    command = [
        sys.executable,
        str(AUDIT_SCRIPT),
        "--spec",
        str(spec),
        "--json-out",
        str(json_out),
        "--capital-flows-file",
        str(capital_flows_file),
        "--targets-file",
        str(targets_file),
        "--manifest-file",
        str(manifest_file),
        "--state-file",
        str(state_file),
        "--journal-file",
        str(journal_file),
    ]
    if prior_track_registry is not None:
        command.extend(
            ["--prior-track-registry", str(prior_track_registry)]
        )
    return command


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
    def failed_label(row: dict) -> str:
        label = str(row.get("check") or "未命名检查").strip()
        # Older audit payloads named the check "…通过".  That reads as a
        # contradiction when the same row is being reported as a failure.
        return label.removesuffix("通过").rstrip() or "未命名检查"

    details = "；".join(
        f"{failed_label(row)} — {row.get('detail') or '无详情'}"
        for row in failures
    )
    return f"全链路核对失败：{details}"


def _run_audit(
    capital_flows_file: Path,
    *,
    audit_out: Path | None = None,
    spec: str = DEFAULT_SPEC,
    targets_file: Path = DEFAULT_TARGETS_FILE,
    manifest_file: Path = DEFAULT_MANIFEST_FILE,
    state_file: Path = DEFAULT_STATE_FILE,
    journal_file: Path = DEFAULT_JOURNAL_FILE,
    prior_track_registry: Path | None = None,
) -> tuple[int, dict, str]:
    """Run the read-only audit in a subprocess and preserve failure diagnostics."""

    import tempfile

    temporary: tempfile.TemporaryDirectory[str] | None = None
    if audit_out is None:
        temporary = tempfile.TemporaryDirectory(prefix="atlas20-monitor-")
        json_out = Path(temporary.name) / "audit.json"
    else:
        json_out = Path(audit_out)
        ensure_dir(json_out.parent)
    try:
        try:
            proc = subprocess.run(
                _audit_command(
                    json_out,
                    capital_flows_file,
                    spec=spec,
                    targets_file=targets_file,
                    manifest_file=manifest_file,
                    state_file=state_file,
                    journal_file=journal_file,
                    prior_track_registry=prior_track_registry,
                ),
                cwd=str(PROJECT_ROOT),
                capture_output=True,
                text=True,
                timeout=180,
            )
        except subprocess.TimeoutExpired as exc:
            return 124, {}, f"audit timed out after {exc.timeout:g}s"
        payload: dict = {}
        stderr = proc.stderr.strip()
        if json_out.exists():
            try:
                payload = json.loads(json_out.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                stderr = f"{stderr}\naudit JSON unreadable: {exc}".strip()
        return proc.returncode, payload, stderr
    finally:
        if temporary is not None:
            temporary.cleanup()


def _position_notional(positions: list[dict], symbol_map: dict[str, str]) -> dict[str, float]:
    by_symbol = symbol_to_asset_index(symbol_map)
    out: dict[str, float] = {}
    for row in positions:
        symbol = str(row.get("symbol") or "").upper()
        asset = by_symbol.get(symbol)
        if asset is None:
            continue
        out[asset] = out.get(asset, 0.0) + _position_signed_notional(row)
    return out


def _event_position_issues(
    state: dict,
    positions: list[dict],
    symbol_map: dict[str, str],
    specs: dict[str, ContractSpec],
) -> list[str]:
    """Compare the live book to the quantities frozen by the active event.

    The target ledger is event-driven: after an event is applied, price moves
    change the *notional weight* while the correct quantity stays frozen.  A
    monitor that re-multiplies the old weight by today's equity creates false
    drift alerts.  Use the same quantity invariant as ``audit-live``.
    """

    active_event = state.get("active_event")
    if not isinstance(active_event, dict):
        return ["执行状态没有 active target event"]
    quantities = effective_event_target_quantities(active_event)
    if not quantities:
        return ["执行状态 active target event 缺少冻结目标数量"]
    weights = active_event.get("target_weights")
    prices = active_event.get("prices")
    stopped = active_event.get("stopped_symbols")
    specs_by_symbol = {
        str(getattr(spec, "symbol", "")).upper(): spec
        for spec in specs.values()
        if str(getattr(spec, "symbol", "")).strip()
    }
    issues = _event_quantity_issues(
        target_quantities=quantities,
        target_weights=weights if isinstance(weights, dict) else {},
        symbol_assets=symbol_to_asset_index(symbol_map),
        positions=positions,
        specs_by_symbol=specs_by_symbol,
        event_prices=prices if isinstance(prices, dict) else {},
        stopped_symbols=stopped if isinstance(stopped, dict) else {},
    )
    target_symbols = {str(symbol).upper() for symbol in quantities}
    actual_symbols = {
        str(row.get("symbol") or "").upper()
        for row in positions
        if abs(_position_signed_notional(row)) > 1e-12
    }
    extra = sorted(actual_symbols - target_symbols)
    if extra:
        issues.append("计划外持仓: " + ", ".join(extra))
    return issues


def _execution_freshness(state_file: Path, now: datetime) -> tuple[bool, str]:
    """Fail unless the latest daily run is both successful and recent."""

    if not state_file.exists():
        return False, "no execution state file; the daily run has never completed"
    state = json.loads(state_file.read_text(encoding="utf-8"))
    last_at = state.get("last_run_at") or ""
    if not last_at:
        return False, "execution state has no last_run_at"
    status = str(state.get("last_status") or "missing")
    mode = str(state.get("last_run_mode") or "execution")
    if status != "ok":
        return False, f"最近一次调仓未完成（status={status}，mode={mode}，最后尝试：{last_at}）"
    last = datetime.fromisoformat(str(last_at))
    if last.tzinfo is None:
        last = last.replace(tzinfo=timezone.utc)
    age_hours = (now - last).total_seconds() / 3600.0
    today = now.strftime("%Y-%m-%d")
    runs = state.get("runs")
    execution_today = False
    if isinstance(runs, list):
        for row in runs:
            if not isinstance(row, dict):
                continue
            if str(row.get("mode") or "") != "execution":
                continue
            if str(row.get("status") or "") != "ok":
                continue
            key_parts = str(row.get("key") or "").split("|")
            if key_parts and key_parts[-1] == today:
                execution_today = True
                break
    # Legacy state files had no runs array.  Fall back to the last key only
    # when the last completed operation was an execution, never when it was a
    # protect-only or reconcile pass.
    if not execution_today and not isinstance(runs, list):
        legacy_mode = str(state.get("last_run_mode") or "execution")
        key_parts = str(state.get("last_key") or "").split("|")
        execution_today = (
            legacy_mode == "execution"
            and bool(key_parts)
            and key_parts[-1] == today
        )
    if now.hour >= EXECUTION_OVERDUE_UTC_HOUR and not execution_today:
        return False, (
            "今天没有成功的 execution 运行"
            f"（最后成功：{last_at}，last_run_mode={mode}）"
        )
    if age_hours > MAX_EXECUTION_AGE_HOURS:
        return False, f"超过 {MAX_EXECUTION_AGE_HOURS:.0f}h 没有成功执行（最后：{last_at}）"
    return True, f"最近成功运行（{mode}）{last_at}（{age_hours:.1f}h 前）"


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


def _main(args: argparse.Namespace) -> int:
    now = datetime.now(timezone.utc)

    audit_exit, audit, audit_stderr = _run_audit(
        args.capital_flows_file,
        audit_out=args.audit_out,
        spec=args.spec,
        targets_file=args.targets_file,
        manifest_file=args.manifest_file,
        state_file=args.state_file,
        journal_file=args.journal_file,
        prior_track_registry=args.prior_track_registry,
    )
    profile = live_track_profile(args.spec)
    spec_max_gross = float(profile.manifest_top_level["max_total_gross"])
    audit_failures = int(audit.get("hard_failures") or 0)
    equity, gross = _audit_metrics(audit)
    signal_date = str(audit.get("signal_date") or "?")

    client = BitgetPrivateClient(BitgetCredentials.from_env())
    positions = client.current_positions()
    symbol_map = load_symbol_map(args.symbol_map)
    signal_date, _hint, book = load_latest_targets(args.targets_file)
    targets = target_weights_from_book(book, symbol_map)

    session = requests.Session()
    specs = specs_from_instruments(
        fetch_public_instruments(session),
        spec_symbol_universe(symbol_map, targets),
    )

    issues: list[str] = []
    missing_mappings = missing_asset_mappings(symbol_map, targets)
    if missing_mappings:
        issues.append(
            "冻结目标缺少 Bitget 合约映射: " + ", ".join(missing_mappings)
        )
    target_gross = target_gross_weight(targets)
    if target_gross > spec_max_gross + 1e-9:
        issues.append(
            f"冻结目标 gross {target_gross:.2f}x 超过规格上限 {spec_max_gross:.2f}x"
        )
    missing_specs = missing_contract_specs(specs, set(targets))
    if missing_specs:
        issues.append(
            "冻结目标缺少 Bitget 合约规格: " + ", ".join(missing_specs)
        )
    unknown_symbols = _unknown_position_symbols(positions, symbol_map)
    if unknown_symbols:
        issues.append(
            "存在无法唯一映射到冻结资产的持仓: " + ", ".join(unknown_symbols)
        )
    if audit_exit != 0 or audit_failures or equity is None or gross is None:
        issues.append(
            _audit_failure_details(
                audit,
                exit_code=audit_exit,
                stderr=audit_stderr,
            )
        )

    try:
        state_payload = json.loads(args.state_file.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        state_payload = {}
        issues.append(f"执行状态不可读：{exc}")
    if not isinstance(state_payload, dict):
        state_payload = {}
        issues.append("执行状态不是 JSON 对象")
    issues.extend(_event_position_issues(state_payload, positions, symbol_map, specs))

    ratio = (
        _gross_ratio(gross=gross, equity=equity)
        if gross is not None and equity is not None
        else None
    )
    if ratio is not None and ratio > spec_max_gross:
        issues.append(f"总名义 {ratio:.2f}x 权益，超过规格上限 {spec_max_gross:.2f}x")
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
    atomic_write_text(args.out, json.dumps(flags, indent=2, ensure_ascii=False))

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


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        return _main(args)
    except Exception as exc:
        now = datetime.now(timezone.utc)
        issue = f"巡检进程异常：{type(exc).__name__}: {exc}"
        flags = {
            "audit_exit": None,
            "audit_stderr": None,
            "equity": None,
            "position_value": None,
            "issues": [issue],
            "checked_at": now.isoformat(),
        }
        ensure_dir(args.out.parent)
        atomic_write_text(args.out, json.dumps(flags, indent=2, ensure_ascii=False))
        message = "\n".join(
            [
                "🩺 Atlas20 实盘巡检",
                "账户总价值: 未知（巡检进程异常）",
                "仓位价值: 未知（巡检进程异常）",
                "",
                "⚠️ 需要处理:",
                f"• {issue}",
            ]
        )
        if not args.quiet:
            print(message)
        if args.notify:
            token = os.environ.get("ATLAS20_TELEGRAM_BOT_TOKEN", "")
            chat_ids = _chat_ids(os.environ.get("ATLAS20_TELEGRAM_CHAT_ID"))
            if token and chat_ids:
                for chat_id in chat_ids:
                    send_telegram_message(message, token=token, chat_id=chat_id)
            else:
                print(
                    "monitor: no telegram credentials in environment; alert not sent",
                    file=sys.stderr,
                )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
