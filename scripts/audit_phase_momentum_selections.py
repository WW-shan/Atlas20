"""Independently audit every phase-momentum selection against the Top20 snapshot.

Checks, each against the point-in-time snapshot and the provider's raw print:
sleeve selections (membership, price, Rain, configured stablecoin and excluded
ids), one snapshot of exactly ``universe.universe_size`` coins per evaluated
date, the hold rule on every scheduled check, and every traded target weight.
Exits 1 when any violation count is non-zero so it can gate automation.
"""

# ruff: noqa: E402

from __future__ import annotations

import argparse
from collections.abc import Iterable
from dataclasses import asdict
import json
from pathlib import Path
import sys

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
for path in (PROJECT_ROOT, SRC_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from atlas20.config import ResearchConfig  # noqa: E402
from atlas20.logging_utils import configure_logging, ensure_dir  # noqa: E402
from atlas20.reporting.report import dataframe_to_markdown  # noqa: E402
from atlas20.strategies.phase_momentum import (  # noqa: E402
    PRIMARY_SIGNAL_SPECS,
    PhaseMomentumSpec,
    build_phase_momentum_targets,
)
from atlas20.universe.builder import MarketDataBundle  # noqa: E402

from scripts.run_phase_momentum import _load_market  # noqa: E402


SELECTION_COLUMNS = [
    "signal_date",
    "signal_name",
    "phase_offset",
    "selected_asset",
    "selected_rank",
    "in_point_in_time_top20",
    "has_price",
    "snapshot_size",
    "is_rain",
    "is_stablecoin",
    "is_excluded_id",
]


def _config_ids(values: Iterable[object]) -> set[str]:
    return {str(value).lower() for value in values}


def _has_raw_price(market: MarketDataBundle, date: pd.Timestamp, asset: str) -> bool:
    """A provider print on ``date``.

    ``market.price`` carries the last close across short provider gaps, so a
    stale price would pass there; only ``raw_price`` shows what was quoted.
    """
    raw = market.raw_price
    if asset not in raw.columns or date not in raw.index:
        return False
    value = float(raw.at[date, asset])
    return bool(np.isfinite(value) and value > 0.0)


def _selection_audit(
    history: pd.DataFrame,
    membership: dict[pd.Timestamp, set[str]],
    market: MarketDataBundle,
    config: ResearchConfig,
) -> pd.DataFrame:
    """One row per non-empty sleeve selection, checked on its signal date."""
    if history.empty:
        return pd.DataFrame(columns=SELECTION_COLUMNS)
    stablecoin_ids = _config_ids(config.universe.stablecoin_ids)
    excluded_ids = _config_ids(config.universe.excluded_ids)
    rows: list[dict[str, object]] = []
    selected = history[history["selected_asset"].fillna("").astype(str).ne("")]
    for row in selected.itertuples(index=False):
        signal_date = pd.Timestamp(row.signal_date).normalize()
        asset = str(row.selected_asset)
        snapshot = membership.get(signal_date, set())
        rows.append(
            {
                "signal_date": signal_date,
                "signal_name": row.signal_name,
                "phase_offset": row.phase_offset,
                "selected_asset": asset,
                "selected_rank": row.selected_rank,
                "in_point_in_time_top20": asset in snapshot,
                "has_price": _has_raw_price(market, signal_date, asset),
                "snapshot_size": len(snapshot),
                "is_rain": asset.lower() == "rain",
                "is_stablecoin": asset.lower() in stablecoin_ids,
                "is_excluded_id": asset.lower() in excluded_ids,
            }
        )
    return pd.DataFrame(rows, columns=SELECTION_COLUMNS)


def _selection_failures(selection: pd.DataFrame) -> pd.Series:
    return (
        ~selection["in_point_in_time_top20"].astype(bool)
        | ~selection["has_price"].astype(bool)
        | selection["is_rain"].astype(bool)
        | selection["is_stablecoin"].astype(bool)
        | selection["is_excluded_id"].astype(bool)
    )


def _selection_counts(selection: pd.DataFrame) -> dict[str, int]:
    return {
        "selection_rows": int(len(selection)),
        "violations": int(_selection_failures(selection).sum()),
        "missing_price_rows": int((~selection["has_price"].astype(bool)).sum()),
        "outside_top20_rows": int((~selection["in_point_in_time_top20"].astype(bool)).sum()),
        "rain_rows": int(selection["is_rain"].astype(bool).sum()),
        "stablecoin_rows": int(selection["is_stablecoin"].astype(bool).sum()),
        "excluded_id_rows": int(selection["is_excluded_id"].astype(bool).sum()),
    }


def _snapshot_size_audit(
    universe: pd.DataFrame,
    index: pd.DatetimeIndex,
    *,
    expected_size: int,
) -> pd.DataFrame:
    """One row per evaluated date with the size of that date's snapshot.

    Sizes are measured over the evaluated ``index``, not over the snapshots
    that happen to exist, so a date the universe builder skipped shows up as
    size 0 instead of silently dropping out of the check.
    """
    dates = pd.to_datetime(universe["rebalance_date"]).dt.normalize()
    sizes = universe["coin_id"].astype(str).groupby(dates).nunique()
    evaluated = pd.DatetimeIndex(index).normalize()
    frame = pd.DataFrame({"date": evaluated})
    frame["universe_size"] = sizes.reindex(evaluated).fillna(0).astype(int).to_numpy()
    frame["has_snapshot"] = evaluated.isin(sizes.index)
    frame["wrong_size"] = frame["has_snapshot"] & frame["universe_size"].ne(int(expected_size))
    return frame


def _snapshot_counts(sizes: pd.DataFrame) -> dict[str, int]:
    return {
        "dates_evaluated": int(len(sizes)),
        "dates_without_snapshot": int((~sizes["has_snapshot"].astype(bool)).sum()),
        "dates_with_wrong_size": int(sizes["wrong_size"].astype(bool).sum()),
        "max_universe_size": int(sizes["universe_size"].max()) if not sizes.empty else 0,
        "min_universe_size": int(sizes["universe_size"].min()) if not sizes.empty else 0,
    }


HOLD_RULE_COLUMNS = [
    "signal_date",
    "signal_name",
    "phase_offset",
    "selected_asset",
    "selected_rank",
    "hold_rule_ok",
]


def _hold_rule_audit(
    history: pd.DataFrame,
    index: pd.DatetimeIndex,
    spec: PhaseMomentumSpec,
) -> pd.DataFrame:
    """Every holding on its sleeve's scheduled check, with the hold rule applied.

    A sleeve with phase offset ``p`` checks its holding on the days ``d`` where
    ``(d - index[0]).days % spec.rebalance_days == p``; whatever it holds after
    that check must rank within ``spec.hold_rank``.  A missing rank cannot be
    verified, so it fails closed.
    """
    if history.empty or len(index) == 0:
        return pd.DataFrame(columns=HOLD_RULE_COLUMNS)
    start = pd.Timestamp(index[0]).normalize()
    dates = pd.to_datetime(history["signal_date"]).dt.normalize()
    selected = history["selected_asset"].fillna("").astype(str).ne("")
    phase = pd.to_numeric(history["phase_offset"], errors="coerce")
    scheduled = ((dates - start).dt.days % spec.rebalance_days).eq(phase)
    checked = selected & scheduled
    rows = history.loc[checked, HOLD_RULE_COLUMNS[:-1]].copy()
    rows["signal_date"] = dates[checked]
    rows["hold_rule_ok"] = pd.to_numeric(rows["selected_rank"], errors="coerce").le(spec.hold_rank)
    return rows.reset_index(drop=True)


def _hold_rule_counts(rows: pd.DataFrame) -> dict[str, int]:
    return {
        "hold_rule_checked_rows": int(len(rows)),
        "hold_rule_violations": int((~rows["hold_rule_ok"].astype(bool)).sum()),
    }


TRADED_COLUMNS = ["target_date", "asset", "weight", "in_point_in_time_top20", "has_price"]


def _traded_target_audit(
    targets: dict[pd.Timestamp, pd.Series],
    membership: dict[pd.Timestamp, set[str]],
    market: MarketDataBundle,
) -> pd.DataFrame:
    """Every positive weight of every aggregate target the engine trades.

    Sleeve selections are not the whole story: the aggregate carries each
    sleeve's latest event forward, so the traded book is checked on its own
    against the snapshot and the provider print of its target date.
    """
    rows: list[dict[str, object]] = []
    for target_date in sorted(targets, key=pd.Timestamp):
        date = pd.Timestamp(target_date).normalize()
        snapshot = membership.get(date, set())
        weights = pd.to_numeric(targets[target_date], errors="coerce")
        for asset, weight in weights[weights > 0.0].items():
            rows.append(
                {
                    "target_date": date,
                    "asset": str(asset),
                    "weight": float(weight),
                    "in_point_in_time_top20": str(asset) in snapshot,
                    "has_price": _has_raw_price(market, date, str(asset)),
                }
            )
    return pd.DataFrame(rows, columns=TRADED_COLUMNS)


def _traded_counts(rows: pd.DataFrame) -> dict[str, int]:
    return {
        "traded_rows": int(len(rows)),
        "traded_outside_top20": int((~rows["in_point_in_time_top20"].astype(bool)).sum()),
        "traded_without_price": int((~rows["has_price"].astype(bool)).sum()),
    }


# Any non-zero count here fails the audit (and its exit code).
VIOLATION_KEYS = (
    "violations",
    "missing_price_rows",
    "outside_top20_rows",
    "rain_rows",
    "stablecoin_rows",
    "excluded_id_rows",
    "dates_without_snapshot",
    "dates_with_wrong_size",
    "hold_rule_violations",
    "traded_outside_top20",
    "traded_without_price",
)


def _membership(universe: pd.DataFrame) -> dict[pd.Timestamp, set[str]]:
    dates = pd.to_datetime(universe["rebalance_date"]).dt.normalize()
    return {
        pd.Timestamp(date): set(coins.astype(str))
        for date, coins in universe["coin_id"].groupby(dates)
    }


def _failed_checks(summary: dict[str, int]) -> dict[str, int]:
    return {key: int(summary[key]) for key in VIOLATION_KEYS if summary[key]}


def _write_report(
    path: Path,
    *,
    summary: dict[str, int],
    failed: dict[str, int],
    expected_size: int,
    selection: pd.DataFrame,
    sizes: pd.DataFrame,
    hold_rule: pd.DataFrame,
    traded: pd.DataFrame,
) -> None:
    counts = pd.DataFrame(
        {"count": [str(value) for value in summary.values()]},
        index=pd.Index(list(summary), name="check"),
    )
    status = (
        "FAIL: " + ", ".join(f"{key}={value}" for key, value in failed.items())
        if failed
        else "PASS: every violation count is zero."
    )
    lines = [
        "# Phase-Momentum Selection Audit",
        "",
        "Every check uses the point-in-time Top20 snapshot the strategy ranked from and",
        "the provider's own print for the day (a carried, forward-filled price counts",
        "as missing):",
        "",
        "- every non-empty sleeve selection is in that date's snapshot, has a print, and",
        "  is not Rain, a configured stablecoin (`universe.stablecoin_ids`) or a",
        "  configured excluded id (`universe.excluded_ids`);",
        f"- every evaluated date has a snapshot of exactly {expected_size} coins;",
        "- on each sleeve's scheduled check the asset it holds ranks within the hold rank;",
        "- every positive weight of every traded aggregate target is in that date's",
        "  snapshot and has a print.",
        "",
        f"Result: {status}",
        "",
        "## Summary",
        "",
        dataframe_to_markdown(counts),
        "",
        "## Selection violations",
        "",
        dataframe_to_markdown(selection[_selection_failures(selection)].head(100)),
        "",
        "## Snapshot violations",
        "",
        dataframe_to_markdown(sizes[~sizes["has_snapshot"] | sizes["wrong_size"]].head(100)),
        "",
        "## Hold-rule violations",
        "",
        dataframe_to_markdown(hold_rule[~hold_rule["hold_rule_ok"].astype(bool)].head(100)),
        "",
        "## Traded-target violations",
        "",
        dataframe_to_markdown(
            traded[
                ~traded["in_point_in_time_top20"].astype(bool) | ~traded["has_price"].astype(bool)
            ].head(100)
        ),
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default="config/base.yaml")
    parser.add_argument("--start-date", default="2022-01-01")
    parser.add_argument("--end-date", default="2026-09-21")
    parser.add_argument("--output-dir", type=Path, default=Path("reports/phase_momentum_selection_audit_2022"))
    args = parser.parse_args(argv)

    configure_logging("ERROR")
    config, market, universe, index = _load_market(
        args.config,
        start_date=args.start_date,
        end_date=args.end_date,
    )
    spec = PhaseMomentumSpec()
    signal_specs = PRIMARY_SIGNAL_SPECS
    built = build_phase_momentum_targets(market, universe, index, signal_specs=signal_specs, spec=spec)
    membership = _membership(universe)
    expected_size = int(config.universe.universe_size)

    selection = _selection_audit(built.selection_history, membership, market, config)
    sizes = _snapshot_size_audit(universe, index, expected_size=expected_size)
    hold_rule = _hold_rule_audit(built.selection_history, index, spec)
    traded = _traded_target_audit(built.targets, membership, market)
    summary = {
        **_selection_counts(selection),
        **_snapshot_counts(sizes),
        **_hold_rule_counts(hold_rule),
        **_traded_counts(traded),
    }
    failed = _failed_checks(summary)

    output_dir = ensure_dir(args.output_dir)
    selection.to_csv(output_dir / "selection_audit.csv", index=False)
    sizes.to_csv(output_dir / "universe_sizes.csv", index=False)
    hold_rule.to_csv(output_dir / "hold_rule_audit.csv", index=False)
    traded.to_csv(output_dir / "traded_target_audit.csv", index=False)
    pd.DataFrame([summary]).to_csv(output_dir / "summary.csv", index=False)
    _write_report(
        output_dir / "report.md",
        summary=summary,
        failed=failed,
        expected_size=expected_size,
        selection=selection,
        sizes=sizes,
        hold_rule=hold_rule,
        traded=traded,
    )
    manifest = {
        "config": args.config,
        "start_date": args.start_date,
        "end_date": args.end_date,
        "evaluated_start": pd.Timestamp(index.min()).date().isoformat(),
        "evaluated_end": pd.Timestamp(index.max()).date().isoformat(),
        "spec": asdict(spec),
        "signal_names": [signal.name for signal in signal_specs],
        "expected_universe_size": expected_size,
        "summary": summary,
        "failed_checks": failed,
    }
    (output_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(pd.Series(summary).to_string())
    print(f"Wrote selection audit to {output_dir}")
    if failed:
        print(
            "Selection audit FAILED: " + ", ".join(f"{key}={value}" for key, value in failed.items()),
            file=sys.stderr,
        )
        raise SystemExit(1)


if __name__ == "__main__":
    main()
