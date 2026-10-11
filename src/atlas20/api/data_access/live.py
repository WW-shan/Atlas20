"""Read-only adapter for current research and live-operation artifacts."""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

import pandas as pd

from atlas20.api.settings import Settings


SPOT_SIGNAL = "phase_momentum_live/latest_signal.json"
FROZEN_DECISION = "phase_momentum_candidate_eval_h5/decision_table.csv"
FROZEN_DSR = "phase_momentum_candidate_eval_h5/deflated_sharpe.csv"
OOS_MANIFEST = "phase_momentum_oos_2026/manifest.json"
OOS_SUMMARY = "phase_momentum_oos_2026/oos_summary.csv"
OOS_BENCHMARK = "phase_momentum_oos_2026/benchmark.csv"
DERIVATIVES_EXECUTION = "derivatives_track_execution/latest.json"
DERIVATIVES_HEALTH = "derivatives_track_live/health.json"
DERIVATIVES_AUDIT = "derivatives_track_live/audit.json"
DERIVATIVES_EQUIVALENCE = "derivatives_track_live/signal_equivalence.json"
DERIVATIVES_JOURNAL = "derivatives_track_live/journal.csv"

_ARTIFACTS: tuple[tuple[str, str, str], ...] = (
    ("spot_signal", "spot", SPOT_SIGNAL),
    ("frozen_decision", "spot", FROZEN_DECISION),
    ("frozen_dsr", "spot", FROZEN_DSR),
    ("oos_manifest", "oos", OOS_MANIFEST),
    ("oos_summary", "oos", OOS_SUMMARY),
    ("oos_benchmark", "oos", OOS_BENCHMARK),
    ("derivatives_execution", "derivatives", DERIVATIVES_EXECUTION),
    ("derivatives_health", "derivatives", DERIVATIVES_HEALTH),
    ("derivatives_audit", "derivatives", DERIVATIVES_AUDIT),
    ("derivatives_equivalence", "derivatives", DERIVATIVES_EQUIVALENCE),
    ("derivatives_journal", "derivatives", DERIVATIVES_JOURNAL),
)


def load_live_research(settings: Settings) -> dict[str, Any]:
    """Build the live-research payload from checked-in artifacts.

    The adapter is intentionally read-only. Missing sections become ``None``
    and are reported through ``artifacts`` rather than being replaced by
    plausible-looking defaults.
    """

    root = settings.report_root
    spot = _spot_payload(root)
    oos = _oos_payload(root)
    derivatives = _derivatives_payload(root)
    return {
        "spot": spot,
        "oos": oos,
        "derivatives": derivatives,
        "artifacts": _artifact_status(root),
    }


def _read_json(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.is_file():
        return pd.DataFrame()
    try:
        return pd.read_csv(path)
    except (OSError, pd.errors.EmptyDataError, pd.errors.ParserError):
        return pd.DataFrame()


def _text(value: Any, default: str | None = None) -> str | None:
    if value is None or pd.isna(value):
        return default
    result = str(value).strip()
    return result or default


def _number(value: Any) -> float | None:
    if value is None or pd.isna(value):
        return None
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def _required_number(value: Any, field: str) -> float:
    result = _number(value)
    if result is None:
        raise ValueError(f"non-finite or missing value in {field}")
    return result


def _weights(targets: dict[str, Any], current: dict[str, Any]) -> list[dict[str, Any]]:
    assets = sorted(set(targets) | set(current))
    return [
        {
            "asset": asset,
            "target": _number(targets.get(asset)),
            "current": _number(current.get(asset)),
        }
        for asset in assets
    ]


def _data_quality(raw: dict[str, Any]) -> dict[str, Any]:
    value = raw.get("last_day_check")
    if not isinstance(value, dict):
        value = {}
    reasons = value.get("reasons", [])
    if not isinstance(reasons, list):
        reasons = []
    return {
        "complete": bool(value.get("complete", False)),
        "date": _text(value.get("date")),
        "market_cap_coverage": _number(value.get("market_cap_coverage")),
        "median_volume_ratio": _number(value.get("median_volume_ratio")),
        "reasons": [str(item) for item in reasons],
    }


def _spot_payload(root: Path) -> dict[str, Any] | None:
    signal = _read_json(root / SPOT_SIGNAL)
    if signal is None:
        return None

    targets = _string_map(signal.get("targets"))
    current = _string_map(signal.get("current_weights"))
    frozen = _frozen_payload(root)
    return {
        "trial_id": _text(signal.get("trial_id"), "unknown"),
        "status": "provisional",
        "signal_date": _text(signal.get("as_of") or signal.get("latest_target_date")),
        "panel_last_date": _text(signal.get("panel_last_date")),
        "next_check_date": _text(signal.get("next_check_date")),
        "gross_exposure": _number(signal.get("gross_exposure")),
        "current_gross_exposure": _number(signal.get("current_gross_exposure")),
        "btc_gate_open": bool(signal.get("btc_gate_open", False)),
        "trade_required": bool(signal.get("trade_required", False)),
        "cost_bps": _number(signal.get("cost_bps")),
        "rule": _text(signal.get("rule"), ""),
        "weights": _weights(targets, current),
        "data_quality": _data_quality(signal),
        "frozen": frozen,
    }


def _string_map(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    return {str(key).strip(): item for key, item in value.items() if str(key).strip()}


def _frozen_payload(root: Path) -> list[dict[str, Any]]:
    decisions = _read_csv(root / FROZEN_DECISION)
    dsr = _read_csv(root / FROZEN_DSR)
    if decisions.empty:
        return []
    dsr_by_fill = {
        (_text(row.get("trial_id")), _number(row.get("fill_hours"))): _number(
            row.get("deflated_sharpe_probability")
        )
        for _, row in dsr.iterrows()
    }
    rows: list[dict[str, Any]] = []
    for _, row in decisions.iterrows():
        trial_id = _text(row.get("trial_id"))
        fill_hours = _number(row.get("fill_hours"))
        rows.append(
            {
                "trial_id": trial_id,
                "fill_hours": fill_hours,
                "fill_policy": _text(row.get("worse_policy")),
                "multiple": _number(row.get("multiple")),
                "sharpe": _number(row.get("sharpe")),
                "max_drawdown": _number(row.get("max_drawdown")),
                "rolling_1y_worst": _number(row.get("rolling_1y_worst")),
                "best_year_removed": _number(row.get("best_year_removed")),
                "turnover_annual": _number(row.get("turnover_annual")),
                "avg_gross_exposure": _number(row.get("avg_gross_exposure")),
                "observed_weight_share": _number(row.get("observed_weight_share")),
                "deflated_sharpe_probability": dsr_by_fill.get((trial_id, fill_hours)),
            }
        )
    return rows


def _row_by_cost(frame: pd.DataFrame, cost: float, fill_policy: str) -> pd.Series | None:
    if frame.empty or "cost_bps" not in frame.columns:
        return None
    matching = frame[
        frame["cost_bps"].map(_number).eq(cost)
        & frame["fill_policy"].map(lambda value: _text(value) == fill_policy)
    ]
    return None if matching.empty else matching.iloc[0]


def _oos_payload(root: Path) -> dict[str, Any] | None:
    manifest = _read_json(root / OOS_MANIFEST)
    summary = _read_csv(root / OOS_SUMMARY)
    benchmark = _read_csv(root / OOS_BENCHMARK)
    if manifest is None or summary.empty or benchmark.empty:
        return None

    production = _row_by_cost(summary, 20.0, "close")
    btc = benchmark.iloc[0]
    if production is None:
        return None

    stress_rows: list[dict[str, Any]] = []
    for _, row in summary[summary["fill_policy"].map(lambda value: _text(value) == "close")].iterrows():
        stress_rows.append(
            {
                "fill_policy": _text(row.get("fill_policy")),
                "cost_bps": _number(row.get("cost_bps")),
                "multiple": _number(row.get("multiple")),
                "cagr": _number(row.get("cagr")),
                "sharpe": _number(row.get("sharpe")),
                "max_drawdown": _number(row.get("max_drawdown")),
            }
        )

    return {
        "trial_id": _text(manifest.get("trial_id"), "unknown"),
        "start": _text(production.get("start") or manifest.get("oos_start")),
        "end": _text(production.get("end") or manifest.get("oos_end")),
        "days": int(_required_number(production.get("days"), "oos.days")),
        "fill_policy": _text(production.get("fill_policy"), "close"),
        "cost_bps": _required_number(production.get("cost_bps"), "oos.cost_bps"),
        "multiple": _required_number(production.get("multiple"), "oos.multiple"),
        "cagr": _number(production.get("cagr")),
        "sharpe": _number(production.get("sharpe")),
        "max_drawdown": _number(production.get("max_drawdown")),
        "benchmark_fill_policy": _text(btc.get("fill_policy")),
        "benchmark_multiple": _required_number(btc.get("multiple"), "oos.benchmark_multiple"),
        "benchmark_cagr": _number(btc.get("cagr")),
        "benchmark_sharpe": _number(btc.get("sharpe")),
        "benchmark_max_drawdown": _number(btc.get("max_drawdown")),
        "stress": stress_rows,
    }


def _execution_payload(raw: dict[str, Any]) -> dict[str, Any]:
    plan_value = raw.get("plan")
    report_value = raw.get("report")
    plan = plan_value if isinstance(plan_value, dict) else {}
    report = report_value if isinstance(report_value, dict) else {}
    failures = report.get("failures", [])
    notes = report.get("margin_notes", [])
    return {
        "status": _text(raw.get("status"), "unknown"),
        "execution_hint": _text(raw.get("execution_hint")),
        "signal_date": _text(raw.get("signal_date")),
        "spec": _text(raw.get("spec")),
        "equity_before": _number(report.get("equity_before") or plan.get("equity")),
        "equity_after": _number(report.get("equity_after") or plan.get("equity")),
        "balance_after": _number(report.get("balance_after")),
        "position_value": _number(
            report.get("position_value") or plan.get("expected_gross_notional")
        ),
        "traded": bool(report.get("traded", False)),
        "margin_mode": _text(report.get("margin_mode")),
        "failures": [str(item) for item in failures if isinstance(failures, list)],
        "notes": [str(item) for item in notes if isinstance(notes, list)],
    }


def _health_payload(health: dict[str, Any], audit: dict[str, Any]) -> dict[str, Any]:
    issues = health.get("issues", [])
    if not isinstance(issues, list):
        issues = []
    hard_failures = int(_number(audit.get("hard_failures")) or 0)
    audit_exit = _number(health.get("audit_exit"))
    healthy = audit_exit == 0 and not issues and hard_failures == 0
    checks = audit.get("checks", [])
    if not isinstance(checks, list):
        checks = []
    normalized_checks = [
        {
            "check": _text(row.get("check"), ""),
            "detail": _text(row.get("detail"), ""),
            "hard": bool(row.get("hard", False)),
            "ok": bool(row.get("ok", False)),
        }
        for row in checks
        if isinstance(row, dict)
    ]
    return {
        "status": "healthy" if healthy else "attention",
        "checked_at": _text(health.get("checked_at") or audit.get("checked_at")),
        "audit_exit": int(audit_exit) if audit_exit is not None else None,
        "issues": [str(item) for item in issues],
        "hard_failures": hard_failures,
        "equity": _number(audit.get("equity")),
        "position_value": _number(audit.get("position_value")),
        "signal_date": _text(audit.get("signal_date")),
        "spec": _text(audit.get("spec")),
        "checks": normalized_checks,
    }


def _equivalence_payload(raw: dict[str, Any]) -> dict[str, Any]:
    return {
        "passed": bool(raw.get("passed", False)),
        "checked_at": _text(raw.get("checked_at")),
        "backtest_end": _text(raw.get("backtest_end")),
        "live_end": _text(raw.get("live_end")),
        "differing_event_days": int(_number(raw.get("differing_event_days")) or 0),
        "differences": [str(item) for item in raw.get("differences", []) if isinstance(raw.get("differences"), list)],
        "events_only_in_backtest": [str(item) for item in raw.get("events_only_in_backtest", []) if isinstance(raw.get("events_only_in_backtest"), list)],
        "events_only_in_live": [str(item) for item in raw.get("events_only_in_live", []) if isinstance(raw.get("events_only_in_live"), list)],
        "overlapping_event_days": int(_number(raw.get("overlapping_event_days")) or 0),
        "spec": _text(raw.get("spec")),
        "trial_id_backtest": _text(raw.get("trial_id_backtest")),
        "trial_id_live": _text(raw.get("trial_id_live")),
    }


def _json_count(value: Any) -> int | None:
    if isinstance(value, list):
        return len(value)
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return None
    return len(parsed) if isinstance(parsed, list) else None


def _json_string_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value]
    if not isinstance(value, str) or not value.strip():
        return []
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return []
    if not isinstance(parsed, list):
        return []
    return [str(item) for item in parsed]


def _journal_payload(path: Path) -> list[dict[str, Any]]:
    frame = _read_csv(path)
    if frame.empty:
        return []
    rows: list[dict[str, Any]] = []
    for _, row in frame.tail(20).iloc[::-1].iterrows():
        rows.append(
            {
                "date": _text(row.get("date")),
                "run_at_utc": _text(row.get("run_at_utc")),
                "signal_date": _text(row.get("signal_date")),
                "equity": _number(row.get("equity")),
                "position_value": _number(row.get("position_value")),
                "cash": _number(row.get("cash")),
                "day_pnl": _number(row.get("day_pnl")),
                "day_return": _number(row.get("day_return")),
                "fees_today": _number(row.get("fees_today")),
                "funding_total": _number(row.get("funding_total")),
                "unrealised_pnl": _number(row.get("unrealised_pnl")),
                "positions": _json_count(row.get("positions")),
                "trades": _json_count(row.get("trades")),
                "notes": _json_string_list(row.get("notes")),
            }
        )
    return rows


def _derivatives_payload(root: Path) -> dict[str, Any] | None:
    execution = _read_json(root / DERIVATIVES_EXECUTION)
    health = _read_json(root / DERIVATIVES_HEALTH)
    audit = _read_json(root / DERIVATIVES_AUDIT)
    equivalence = _read_json(root / DERIVATIVES_EQUIVALENCE)
    if execution is None and health is None and audit is None and equivalence is None:
        return None
    if health is None:
        health = {}
    if audit is None:
        audit = {}
    if equivalence is None:
        equivalence = {}
    return {
        "execution": _execution_payload(execution or {}),
        "health": _health_payload(health, audit),
        "equivalence": _equivalence_payload(equivalence),
        "journal": _journal_payload(root / DERIVATIVES_JOURNAL),
    }


def _artifact_status(root: Path) -> list[dict[str, Any]]:
    return [
        {
            "id": artifact_id,
            "section": section,
            "path": relative,
            "available": (root / relative).is_file(),
        }
        for artifact_id, section, relative in _ARTIFACTS
    ]
