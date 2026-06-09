from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import math
from pathlib import Path
import sys

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from atlas20.strategies.convex_leader import CTREND_LITE_SCORE_FAMILIES  # noqa: E402


@dataclass(frozen=True)
class CandidateDefinition:
    candidate_id: str
    family_id: str
    strategy_kind: str
    top_n: int
    frequency: str
    score_family: str
    liquidity_label: str
    min_history_days: int
    min_daily_dollar_volume: float
    include_btc: bool
    overlay_set: str
    risk_off_asset: str
    initial_asset: str
    stop_kind: str
    stop_lookback: int | None
    stop_confirm_days: int
    ma_window: int | None


LIQUIDITY_SETS: dict[str, tuple[int, float]] = {
    "loose": (30, 1_000_000.0),
    "medium": (60, 10_000_000.0),
    "strict": (90, 25_000_000.0),
}


OVERLAY_SETS: dict[str, dict[str, object]] = {
    "champion_like": {
        "stop_kind": "trailing",
        "stop_lookback": 11,
        "stop_confirm_days": 2,
        "ma_window": None,
        "risk_off_asset": "btc",
        "initial_asset": "btc",
    },
    "btc_fast_stop": {
        "stop_kind": "trailing",
        "stop_lookback": 10,
        "stop_confirm_days": 1,
        "ma_window": None,
        "risk_off_asset": "cash",
        "initial_asset": "btc",
    },
    "btc_medium_stop": {
        "stop_kind": "trailing",
        "stop_lookback": 14,
        "stop_confirm_days": 2,
        "ma_window": None,
        "risk_off_asset": "btc",
        "initial_asset": "btc",
    },
    "btc_ma_defensive": {
        "stop_kind": "ma",
        "stop_lookback": None,
        "stop_confirm_days": 2,
        "ma_window": 100,
        "risk_off_asset": "cash",
        "initial_asset": "btc",
    },
    "no_stop_control": {
        "stop_kind": "none",
        "stop_lookback": None,
        "stop_confirm_days": 1,
        "ma_window": None,
        "risk_off_asset": "cash",
        "initial_asset": "cash",
    },
}


LEADER_MOMENTUM_SCORE_FAMILIES: tuple[str, ...] = (
    "base",
    "short_accel",
    "breakout",
    "balanced",
)


def _candidate_id(parts: list[object]) -> str:
    return "__".join(str(part).replace(" ", "_").lower() for part in parts)


def _champion_ablation_overlays() -> dict[str, dict[str, object]]:
    return {
        f"champion_ablation_stop{stop_lookback}": {
            "stop_kind": "trailing",
            "stop_lookback": stop_lookback,
            "stop_confirm_days": 2,
            "ma_window": None,
            "risk_off_asset": "btc",
            "initial_asset": "btc",
        }
        for stop_lookback in (10, 11, 12, 13, 14, 15)
    }


def _candidate_from_parts(
    *,
    family_id: str,
    strategy_kind: str,
    top_n: int,
    frequency: str,
    score_family: str,
    liquidity_label: str,
    include_btc: bool,
    overlay_set: str,
    overlay_sets: dict[str, dict[str, object]],
) -> CandidateDefinition:
    min_history_days, min_daily_dollar_volume = LIQUIDITY_SETS[liquidity_label]
    overlay = overlay_sets[overlay_set]
    candidate_id = _candidate_id(
        [
            family_id,
            strategy_kind,
            f"top{top_n}",
            frequency,
            score_family,
            liquidity_label,
            "with_btc" if include_btc else "ex_btc",
            overlay_set,
        ]
    )
    return CandidateDefinition(
        candidate_id=candidate_id,
        family_id=family_id,
        strategy_kind=strategy_kind,
        top_n=top_n,
        frequency=frequency,
        score_family=score_family,
        liquidity_label=liquidity_label,
        min_history_days=min_history_days,
        min_daily_dollar_volume=min_daily_dollar_volume,
        include_btc=include_btc,
        overlay_set=overlay_set,
        risk_off_asset=str(overlay["risk_off_asset"]),
        initial_asset=str(overlay["initial_asset"]),
        stop_kind=str(overlay["stop_kind"]),
        stop_lookback=overlay["stop_lookback"] if isinstance(overlay["stop_lookback"], int) else None,
        stop_confirm_days=int(overlay["stop_confirm_days"]),
        ma_window=overlay["ma_window"] if isinstance(overlay["ma_window"], int) else None,
    )


def build_candidate_definitions() -> list[CandidateDefinition]:
    candidates: list[CandidateDefinition] = []

    for liquidity_label in LIQUIDITY_SETS:
        for top_n in (1, 2, 3):
            for frequency in ("7D", "14D", "21D", "28D"):
                for score_family in LEADER_MOMENTUM_SCORE_FAMILIES:
                    for overlay_set in (
                        "champion_like",
                        "btc_fast_stop",
                        "btc_medium_stop",
                        "no_stop_control",
                    ):
                        candidates.append(
                            _candidate_from_parts(
                                family_id="leader_momentum",
                                strategy_kind="leader_momentum",
                                top_n=top_n,
                                frequency=frequency,
                                score_family=score_family,
                                liquidity_label=liquidity_label,
                                include_btc=True,
                                overlay_set=overlay_set,
                                overlay_sets=OVERLAY_SETS,
                            )
                        )

    for liquidity_label in LIQUIDITY_SETS:
        for top_n in (1, 2, 3):
            for frequency in ("7D", "14D", "21D", "28D"):
                for score_family in CTREND_LITE_SCORE_FAMILIES:
                    for include_btc in (True, False):
                        for overlay_set in (
                            "champion_like",
                            "btc_fast_stop",
                            "btc_medium_stop",
                            "btc_ma_defensive",
                        ):
                            candidates.append(
                                _candidate_from_parts(
                                    family_id="ctrend_lite",
                                    strategy_kind="ctrend_lite",
                                    top_n=top_n,
                                    frequency=frequency,
                                    score_family=score_family,
                                    liquidity_label=liquidity_label,
                                    include_btc=include_btc,
                                    overlay_set=overlay_set,
                                    overlay_sets=OVERLAY_SETS,
                                )
                            )

    champion_overlays = _champion_ablation_overlays()
    for overlay_set in champion_overlays:
        candidates.append(
            _candidate_from_parts(
                family_id="champion_ablation",
                strategy_kind="leader_momentum",
                top_n=1,
                frequency="14D",
                score_family="base",
                liquidity_label="loose",
                include_btc=True,
                overlay_set=overlay_set,
                overlay_sets=champion_overlays,
            )
        )

    unique: dict[str, CandidateDefinition] = {}
    for candidate in candidates:
        unique[candidate.candidate_id] = candidate
    return list(unique.values())


def _safe_float(value: object, default: float = 0.0) -> float:
    if pd.isna(value):
        return default
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return default
    if not math.isfinite(numeric):
        return default
    return numeric


def _safe_log_multiple(value: object) -> float:
    return math.log(max(_safe_float(value), 1e-9))


def compute_raw_convexity_score(row: pd.Series) -> float:
    return (
        0.45 * _safe_log_multiple(row.get("multiple", 0.0))
        + 0.25 * _safe_log_multiple(row.get("best_rolling_5y_multiple", row.get("multiple", 0.0)))
        + 0.15 * _safe_float(row.get("hundred_x_hit_rate_5y", 0.0))
        - 0.15 * abs(_safe_float(row.get("max_drawdown", 0.0)))
    )


def compute_robust_convexity_score(row: pd.Series) -> float:
    turnover = _safe_float(row.get("annualized_turnover", 0.0))
    turnover_penalty = min(max(turnover / 100.0, 0.0), 1.0)
    return (
        0.30
        * _safe_log_multiple(row.get("median_rolling_start_multiple", row.get("multiple", 0.0)))
        + 0.20 * _safe_float(row.get("hundred_x_hit_rate_5y", 0.0))
        - 0.20 * abs(_safe_float(row.get("max_drawdown", 0.0)))
        + 0.15 * _safe_float(row.get("cost_survival_100bps", 0.0))
        + 0.10 * _safe_float(row.get("stability_score", 0.0))
        - 0.05 * turnover_penalty
    )


def _add_candidate(selected: list[str], candidate_id: str, max_candidates: int) -> None:
    if candidate_id not in selected and len(selected) < max_candidates:
        selected.append(candidate_id)


def _add_ranked_candidates(
    selected: list[str],
    summary: pd.DataFrame,
    score_column: str,
    max_candidates: int,
    *,
    limit: int | None = None,
) -> None:
    if score_column not in summary.columns:
        return
    sorted_summary = summary.sort_values(score_column, ascending=False, kind="mergesort")
    added = 0
    for candidate_id in sorted_summary["candidate_id"].astype(str):
        before_count = len(selected)
        _add_candidate(selected, candidate_id, max_candidates)
        if len(selected) > before_count:
            added += 1
        if len(selected) >= max_candidates or (limit is not None and added >= limit):
            return


def _validate_selection_summary(summary: pd.DataFrame) -> None:
    required_columns = {"candidate_id", "multiple"}
    missing_columns = sorted(required_columns.difference(summary.columns))
    if missing_columns:
        missing = ", ".join(missing_columns)
        raise ValueError(f"summary is missing required column(s): {missing}")


def select_validation_candidates(
    summary: pd.DataFrame,
    *,
    champion_candidate_id: str,
    max_validation_candidates: int,
    min_multiple_for_validation: float,
) -> list[str]:
    selected: list[str] = []
    if max_validation_candidates <= 0:
        return selected
    _validate_selection_summary(summary)
    if summary.empty:
        return selected

    candidate_ids = set(summary["candidate_id"].astype(str))
    if champion_candidate_id in candidate_ids:
        _add_candidate(selected, champion_candidate_id, max_validation_candidates)

    raw_limit = max(1, (max_validation_candidates - len(selected)) // 2)
    _add_ranked_candidates(
        selected,
        summary,
        "raw_convexity_score",
        max_validation_candidates,
        limit=raw_limit,
    )
    _add_ranked_candidates(selected, summary, "robust_convexity_score", max_validation_candidates)

    threshold_summary = summary[summary["multiple"] >= min_multiple_for_validation].sort_values(
        "multiple",
        ascending=False,
        kind="mergesort",
    )
    for candidate_id in threshold_summary["candidate_id"].astype(str):
        _add_candidate(selected, candidate_id, max_validation_candidates)

    return selected


def candidate_records(candidates: list[CandidateDefinition]) -> pd.DataFrame:
    return pd.DataFrame([asdict(candidate) for candidate in candidates])


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Top20 convex leader validation.")
    parser.add_argument("--config", default="config/bear_bottom_to_current_2022_11_21_2026_04_22.yaml")
    parser.parse_args()
    print("Task 6 adds full CLI execution.")


if __name__ == "__main__":
    main()
