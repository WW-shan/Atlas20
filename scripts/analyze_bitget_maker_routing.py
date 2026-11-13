"""Analyze a pre-registered taker-routing rule on Bitget trade-tape outcomes.

The simulator records maker outcomes for one or more fill haircuts. This script
does not download data or send orders. It compares the haircut baseline with a
single, explicit routing rule (default: long opens are immediate taker, all
other legs keep maker-first execution).
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import sys
from typing import Any

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
for path in (PROJECT_ROOT, SRC_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

BASELINE_TAKER_COST_BPS = 20.0
DEFAULT_HAIRCUT = 0.25


def _haircut_tag(haircut: float) -> str:
    percent = int(round(float(haircut) * 100.0))
    if not math.isclose(percent / 100.0, float(haircut), abs_tol=1e-12):
        raise ValueError("fill haircut must be a whole percentage")
    return f"{percent:03d}"


def _weighted_mean(frame: pd.DataFrame, column: str) -> float:
    valid = frame[[column, "requested_notional"]].dropna()
    requested = float(valid["requested_notional"].sum())
    if valid.empty or requested <= 0.0:
        return float("nan")
    return float(np.average(valid[column], weights=valid["requested_notional"]))


def apply_taker_route(
    events: pd.DataFrame,
    *,
    haircut: float = DEFAULT_HAIRCUT,
    route_position_side: str = "long",
    route_action: str = "open",
    baseline_cost_bps: float = BASELINE_TAKER_COST_BPS,
) -> pd.DataFrame:
    """Return event outcomes after replacing selected legs with immediate taker."""
    prefix = f"haircut_{_haircut_tag(haircut)}"
    required = {
        "requested_notional",
        "haircut_025_maker_filled_notional",
        "haircut_025_taker_filled_notional",
        "haircut_025_effective_cost_bps",
        "haircut_025_improvement_bps",
        "haircut_025_guard_triggered",
        "haircut_025_status",
    }
    required = {name.replace("haircut_025", prefix) for name in required}
    missing = sorted(required.difference(events.columns))
    if missing:
        raise ValueError(f"events are missing routing columns: {missing}")
    if baseline_cost_bps <= 0.0:
        raise ValueError("baseline_cost_bps must be positive")

    frame = events.copy()
    side_match = frame["position_side"].astype(str).str.lower() == route_position_side.lower()
    action_match = frame["action"].astype(str).str.lower() == route_action.lower()
    routed = side_match & action_match
    maker_col = f"{prefix}_maker_filled_notional"
    taker_col = f"{prefix}_taker_filled_notional"
    cost_col = f"{prefix}_effective_cost_bps"
    improvement_col = f"{prefix}_improvement_bps"
    guard_col = f"{prefix}_guard_triggered"
    status_col = f"{prefix}_status"

    frame["taker_routed"] = routed
    frame["baseline_maker_filled_notional"] = frame[maker_col]
    frame["baseline_taker_filled_notional"] = frame[taker_col]
    frame["baseline_effective_cost_bps"] = frame[cost_col]
    frame["baseline_improvement_bps"] = frame[improvement_col]
    frame["baseline_guard_triggered"] = frame[guard_col]
    frame["baseline_status"] = frame[status_col]
    frame["routed_maker_filled_notional"] = frame[maker_col].where(~routed, 0.0)
    frame["routed_taker_filled_notional"] = frame[taker_col].where(
        ~routed, frame["requested_notional"]
    )
    frame["routed_effective_cost_bps"] = frame[cost_col].where(
        ~routed, float(baseline_cost_bps)
    )
    frame["routed_improvement_bps"] = float(baseline_cost_bps) - frame[
        "routed_effective_cost_bps"
    ]
    frame["routed_status"] = frame[status_col].where(~routed, "taker_route")
    return frame


def _policy_metrics(
    frame: pd.DataFrame,
    *,
    policy: str,
    maker_col: str,
    taker_col: str,
    cost_col: str,
    improvement_col: str,
    status_col: str,
    route_flag_col: str | None,
) -> dict[str, Any]:
    requested = float(frame["requested_notional"].sum())
    if requested <= 0.0:
        raise ValueError("requested notional must be positive")
    maker = float(frame[maker_col].sum())
    taker = float(frame[taker_col].sum())
    route_notional = (
        float(frame.loc[frame[route_flag_col], "requested_notional"].sum())
        if route_flag_col is not None
        else 0.0
    )
    return {
        "policy": policy,
        "events": int(len(frame)),
        "requested_notional": requested,
        "maker_fill_rate": maker / requested,
        "taker_notional_share": taker / requested,
        "routed_notional_share": route_notional / requested,
        "effective_cost_bps": _weighted_mean(frame, cost_col),
        "improvement_bps": _weighted_mean(frame, improvement_col),
        "effective_cost_p05_bps": float(frame[cost_col].quantile(0.05)),
        "effective_cost_p95_bps": float(frame[cost_col].quantile(0.95)),
        "full_fill_share": float((frame[status_col] == "filled").mean()),
        "timeout_event_share": float((frame[status_col] == "timeout").mean()),
    }


def routing_summary(events: pd.DataFrame) -> pd.DataFrame:
    """Compare the haircut baseline with the routed execution policy."""
    required = {
        "requested_notional",
        "taker_routed",
        "baseline_maker_filled_notional",
        "baseline_taker_filled_notional",
        "baseline_effective_cost_bps",
        "baseline_improvement_bps",
        "baseline_status",
        "routed_maker_filled_notional",
        "routed_taker_filled_notional",
        "routed_effective_cost_bps",
        "routed_improvement_bps",
        "routed_status",
    }
    missing = sorted(required.difference(events.columns))
    if missing:
        raise ValueError(f"routed events are missing columns: {missing}")
    rows = [
        _policy_metrics(
            events,
            policy="baseline_maker_25pct",
            maker_col="baseline_maker_filled_notional",
            taker_col="baseline_taker_filled_notional",
            cost_col="baseline_effective_cost_bps",
            improvement_col="baseline_improvement_bps",
            status_col="baseline_status",
            route_flag_col=None,
        ),
        _policy_metrics(
            events,
            policy="long_open_taker",
            maker_col="routed_maker_filled_notional",
            taker_col="routed_taker_filled_notional",
            cost_col="routed_effective_cost_bps",
            improvement_col="routed_improvement_bps",
            status_col="routed_status",
            route_flag_col="taker_routed",
        ),
    ]
    return pd.DataFrame(rows)


def _breakdown(events: pd.DataFrame, columns: str | list[str]) -> pd.DataFrame:
    frame = events.copy()
    frame["month"] = pd.to_datetime(frame["date"], utc=True).dt.strftime("%Y-%m")
    group_columns = [columns] if isinstance(columns, str) else columns
    if group_columns == ["month"]:
        frame["group"] = frame["month"]
    else:
        frame["group"] = frame[group_columns].astype(str).agg("|".join, axis=1)
    rows: list[dict[str, Any]] = []
    for group_value, group in frame.groupby("group", dropna=False):
        baseline = _policy_metrics(
            group,
            policy="baseline_maker_25pct",
            maker_col="baseline_maker_filled_notional",
            taker_col="baseline_taker_filled_notional",
            cost_col="baseline_effective_cost_bps",
            improvement_col="baseline_improvement_bps",
            status_col="baseline_status",
            route_flag_col=None,
        )
        routed = _policy_metrics(
            group,
            policy="long_open_taker",
            maker_col="routed_maker_filled_notional",
            taker_col="routed_taker_filled_notional",
            cost_col="routed_effective_cost_bps",
            improvement_col="routed_improvement_bps",
            status_col="routed_status",
            route_flag_col="taker_routed",
        )
        rows.append(
            {
                "group": str(group_value),
                "events": baseline["events"],
                "requested_notional": baseline["requested_notional"],
                "baseline_improvement_bps": baseline["improvement_bps"],
                "routed_improvement_bps": routed["improvement_bps"],
                "routed_minus_baseline_bps": routed["improvement_bps"]
                - baseline["improvement_bps"],
                "routed_maker_fill_rate": routed["maker_fill_rate"],
                "routed_notional_share": routed["routed_notional_share"],
            }
        )
    return pd.DataFrame(rows).sort_values("group", kind="stable").reset_index(drop=True)


def _ex_top_asset_improvement(events: pd.DataFrame) -> tuple[str | None, float]:
    savings = (
        events["requested_notional"]
        * (BASELINE_TAKER_COST_BPS - events["routed_effective_cost_bps"])
        / 10_000.0
    )
    by_asset = savings.groupby(events["asset"]).sum().sort_values(ascending=False)
    if by_asset.empty:
        return None, float("nan")
    top = str(by_asset.index[0])
    remaining = events.loc[events["asset"] != top]
    return top, _weighted_mean(remaining, "routed_improvement_bps")


def routing_acceptance(
    *,
    covered_events: int,
    notional_coverage: float,
    baseline_improvement_bps: float,
    long_open_baseline_improvement_bps: float,
    routed_improvement_bps: float,
    routed_minus_baseline_bps: float,
    months: int,
    months_ge_5bps: int,
    ex_top_asset_improvement_bps: float,
) -> dict[str, bool]:
    checks = {
        "events_ge_300": covered_events >= 300,
        "notional_coverage_ge_70pct": notional_coverage >= 0.70,
        "baseline_improvement_ge_5bps": baseline_improvement_bps >= 5.0,
        "long_open_baseline_not_profitable": long_open_baseline_improvement_bps <= 0.0,
        "routed_improvement_ge_5bps": routed_improvement_bps >= 5.0,
        "routed_gain_ge_0_5bps": routed_minus_baseline_bps >= 0.5,
        "month_breadth_ge_70pct": months > 0 and months_ge_5bps / months >= 0.70,
        "ex_top_asset_ge_5bps": ex_top_asset_improvement_bps >= 5.0,
    }
    return {name: bool(passed) for name, passed in checks.items()}


def _report(
    routed: pd.DataFrame,
    summary: pd.DataFrame,
    side_action: pd.DataFrame,
    month: pd.DataFrame,
    asset: pd.DataFrame,
    acceptance: dict[str, bool],
    *,
    top_asset: str | None,
    ex_top_improvement: float,
) -> str:
    lookup = summary.set_index("policy")
    baseline = lookup.loc["baseline_maker_25pct"]
    policy = lookup.loc["long_open_taker"]
    long_open = routed.loc[
        routed["position_side"].astype(str).str.lower().eq("long")
        & routed["action"].astype(str).str.lower().eq("open")
    ]
    long_open_baseline = (
        _weighted_mean(long_open, "baseline_improvement_bps")
        if not long_open.empty
        else float("nan")
    )
    verdict = (
        "PASS (routing shadow candidate only)"
        if all(acceptance.values())
        else "FAIL"
    )
    lines = [
        "# Bitget long-open taker routing confirmatory test",
        "",
        "- status: execution research only; orders sent: **no**",
        f"- sample events: **{int(policy['events'])}**; requested notional: **{policy['requested_notional']:.2f} USDT**",
        f"- routed long-open notional share: **{policy['routed_notional_share']:.2%}**",
        f"- baseline 25% haircut: cost **{baseline['effective_cost_bps']:.4f}bps**, improvement **{baseline['improvement_bps']:.4f}bps**",
        f"- long-open taker routing: cost **{policy['effective_cost_bps']:.4f}bps**, improvement **{policy['improvement_bps']:.4f}bps**",
        f"- routing gain vs baseline: **{policy['improvement_bps'] - baseline['improvement_bps']:.4f}bps**",
        f"- long-open subgroup baseline improvement: **{long_open_baseline:.4f}bps**",
        f"- largest savings contributor: **{top_asset}**; ex-asset routed improvement: **{ex_top_improvement:.4f}bps**",
        f"- acceptance verdict: **{verdict}**",
        "",
        "## Acceptance checks",
        "",
        *[f"- [{'x' if passed else ' '}] {name}" for name, passed in acceptance.items()],
        "",
        "## Policy summary",
        "",
        summary.to_csv(index=False),
        "",
        "## By side and action",
        "",
        side_action.to_csv(index=False),
        "",
        "## By month",
        "",
        month.to_csv(index=False),
        "",
        "## By asset",
        "",
        asset.to_csv(index=False),
        "",
        "## Interpretation guardrail",
        "",
        "This test uses a single pre-registered rule: long-open legs are immediate taker and every other leg keeps maker-first execution. It does not prove queue position, hidden liquidity, cancellation latency, partial-fill priority, ADL or venue acceptance. The result is a shadow execution candidate only and does not authorize live routing.",
        "",
    ]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--events-path", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--haircut", type=float, default=DEFAULT_HAIRCUT)
    parser.add_argument("--route-position-side", default="long")
    parser.add_argument("--route-action", default="open")
    parser.add_argument("--baseline-cost-bps", type=float, default=BASELINE_TAKER_COST_BPS)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args(argv)
    if not 0.0 < args.haircut <= 1.0:
        parser.error("--haircut must be in (0, 1]")
    if args.baseline_cost_bps <= 0.0:
        parser.error("--baseline-cost-bps must be positive")

    events = pd.read_csv(args.events_path)
    routed = apply_taker_route(
        events,
        haircut=float(args.haircut),
        route_position_side=str(args.route_position_side),
        route_action=str(args.route_action),
        baseline_cost_bps=float(args.baseline_cost_bps),
    )
    summary = routing_summary(routed)
    side_action = _breakdown(routed, ["exec_side", "position_side", "action"])
    month = _breakdown(routed, "month")
    asset = _breakdown(routed, "asset")
    top_asset, ex_top = _ex_top_asset_improvement(routed)
    months_total = int(len(month))
    months_ge_5 = int((month["routed_improvement_bps"] >= 5.0).sum())
    manifest_path = args.events_path.parent / "manifest.json"
    expected_manifest = (
        json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest_path.is_file()
        else {}
    )
    expected_notional = expected_manifest.get("notional_expected")
    if expected_notional is None or float(expected_notional) <= 0.0:
        raise SystemExit(f"missing positive notional_expected in {manifest_path}")
    requested = float(summary.loc[summary["policy"] == "long_open_taker", "requested_notional"].iloc[0])
    notional_coverage = requested / float(expected_notional)
    baseline_improvement = float(
        summary.loc[summary["policy"] == "baseline_maker_25pct", "improvement_bps"].iloc[0]
    )
    routed_improvement = float(
        summary.loc[summary["policy"] == "long_open_taker", "improvement_bps"].iloc[0]
    )
    long_open = routed.loc[
        routed["position_side"].astype(str).str.lower().eq(str(args.route_position_side).lower())
        & routed["action"].astype(str).str.lower().eq(str(args.route_action).lower())
    ]
    long_open_baseline = (
        _weighted_mean(long_open, "baseline_improvement_bps")
        if not long_open.empty
        else float("nan")
    )
    checks = routing_acceptance(
        covered_events=int(len(routed)),
        notional_coverage=notional_coverage,
        baseline_improvement_bps=baseline_improvement,
        long_open_baseline_improvement_bps=long_open_baseline,
        routed_improvement_bps=routed_improvement,
        routed_minus_baseline_bps=routed_improvement - baseline_improvement,
        months=months_total,
        months_ge_5bps=months_ge_5,
        ex_top_asset_improvement_bps=ex_top,
    )

    output_dir: Path = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    files = {
        "events": output_dir / "routing_events.csv",
        "summary": output_dir / "routing_summary.csv",
        "side_action": output_dir / "routing_side_action.csv",
        "month": output_dir / "routing_month.csv",
        "asset": output_dir / "routing_asset.csv",
        "report": output_dir / "report.md",
        "manifest": output_dir / "manifest.json",
    }
    existing = [path for path in files.values() if path.exists()]
    if existing and not args.overwrite:
        raise SystemExit(f"output already exists: {existing[0]}; pass --overwrite")
    routed.to_csv(files["events"], index=False)
    summary.to_csv(files["summary"], index=False)
    side_action.to_csv(files["side_action"], index=False)
    month.to_csv(files["month"], index=False)
    asset.to_csv(files["asset"], index=False)
    files["report"].write_text(
        _report(
            routed,
            summary,
            side_action,
            month,
            asset,
            checks,
            top_asset=top_asset,
            ex_top_improvement=ex_top,
        ),
        encoding="utf-8",
    )
    manifest = {
        "events_path": str(args.events_path),
        "events_covered": int(len(routed)),
        "requested_notional": requested,
        "expected_notional": expected_notional,
        "notional_coverage": notional_coverage,
        "haircut": float(args.haircut),
        "route_position_side": str(args.route_position_side),
        "route_action": str(args.route_action),
        "baseline_cost_bps": float(args.baseline_cost_bps),
        "baseline_improvement_bps": baseline_improvement,
        "routed_improvement_bps": routed_improvement,
        "routing_gain_bps": routed_improvement - baseline_improvement,
        "long_open_baseline_improvement_bps": long_open_baseline,
        "months": months_total,
        "months_ge_5bps": months_ge_5,
        "top_savings_asset": top_asset,
        "ex_top_asset_improvement_bps": ex_top,
        "acceptance_checks": checks,
        "acceptance_verdict": "pass" if all(checks.values()) else "fail",
        "read_only": True,
        "orders_sent": False,
    }
    files["manifest"].write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(f"wrote {output_dir} with {len(routed)} events; verdict={manifest['acceptance_verdict']}")


if __name__ == "__main__":
    main()
