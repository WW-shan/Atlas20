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

from atlas20.analytics.metrics import compute_summary_metrics  # noqa: E402
from atlas20.backtest.engine import BacktestResult, run_backtest  # noqa: E402
from atlas20.config import FrictionConfig, ResearchConfig  # noqa: E402
from atlas20.signals.risk import btc_above_moving_average, btc_above_trailing_price  # noqa: E402
from atlas20.strategies.convex_leader import (  # noqa: E402
    CTREND_LITE_SCORE_FAMILIES,
    build_ctrend_lite_targets,
)
from atlas20.strategies.momentum_lead import build_momentum_lead_targets  # noqa: E402
from atlas20.strategies.overlays import apply_daily_risk_overlay  # noqa: E402
from atlas20.universe.builder import MarketDataBundle  # noqa: E402


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


LEADER_MOMENTUM_WEIGHTS: dict[str, dict[str, float]] = {
    "base": {
        "momentum_rank": 0.45,
        "ret_21_rank": 0.25,
        "ret_42_rank": 0.20,
        "near_high_rank": 0.10,
    },
    "short_accel": {
        "momentum_rank": 0.35,
        "ret_21_rank": 0.35,
        "ret_42_rank": 0.15,
        "near_high_rank": 0.15,
    },
    "breakout": {
        "momentum_rank": 0.30,
        "ret_21_rank": 0.20,
        "ret_42_rank": 0.15,
        "near_high_rank": 0.35,
    },
    "balanced": {
        "momentum_rank": 0.40,
        "ret_21_rank": 0.20,
        "ret_42_rank": 0.20,
        "near_high_rank": 0.20,
    },
}


PARKING_TARGETS: dict[str, pd.Series | None] = {
    "cash": None,
    "btc": pd.Series({"bitcoin": 1.0}),
    "eth": pd.Series({"ethereum": 1.0}),
}


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


def _ordered_unique_ids(candidate_ids: pd.Series) -> list[str]:
    return list(dict.fromkeys(candidate_ids.astype(str)))


def _ranked_candidate_ids(summary: pd.DataFrame, score_column: str) -> list[str]:
    if score_column not in summary.columns:
        return []
    sorted_summary = summary.sort_values(score_column, ascending=False, kind="mergesort")
    return _ordered_unique_ids(sorted_summary["candidate_id"])


def _threshold_candidate_ids(
    summary: pd.DataFrame,
    min_multiple_for_validation: float,
) -> list[str]:
    threshold_summary = summary[summary["multiple"] >= min_multiple_for_validation].sort_values(
        "multiple",
        ascending=False,
        kind="mergesort",
    )
    return _ordered_unique_ids(threshold_summary["candidate_id"])


def _has_unselected(candidate_ids: list[str], selected: list[str]) -> bool:
    return any(candidate_id not in selected for candidate_id in candidate_ids)


def _lane_quotas(capacity: int, active_lanes: list[str]) -> dict[str, int]:
    quotas = {lane: 0 for lane in active_lanes}
    if capacity <= 0 or not active_lanes:
        return quotas

    guaranteed_lanes = active_lanes[:capacity]
    for lane in guaranteed_lanes:
        quotas[lane] = 1

    remaining = capacity - len(guaranteed_lanes)
    lane_index = 0
    while remaining > 0:
        quotas[active_lanes[lane_index % len(active_lanes)]] += 1
        remaining -= 1
        lane_index += 1
    return quotas


def _add_candidate_ids(
    selected: list[str],
    candidate_ids: list[str],
    max_candidates: int,
    *,
    limit: int | None = None,
) -> None:
    if limit is not None and limit <= 0:
        return
    added = 0
    for candidate_id in candidate_ids:
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

    lanes = {
        "raw": _ranked_candidate_ids(summary, "raw_convexity_score"),
        "robust": _ranked_candidate_ids(summary, "robust_convexity_score"),
        "threshold": _threshold_candidate_ids(summary, min_multiple_for_validation),
    }
    lane_order = ["raw", "robust", "threshold"]
    active_lanes = [lane for lane in lane_order if _has_unselected(lanes[lane], selected)]
    quotas = _lane_quotas(max_validation_candidates - len(selected), active_lanes)

    for lane in lane_order:
        _add_candidate_ids(
            selected,
            lanes[lane],
            max_validation_candidates,
            limit=quotas.get(lane, 0),
        )

    for lane in lane_order:
        _add_candidate_ids(selected, lanes[lane], max_validation_candidates)

    return selected


def _risk_on_series(market: MarketDataBundle, candidate: CandidateDefinition) -> pd.Series:
    if candidate.stop_kind == "none":
        return pd.Series(True, index=market.price.index, name="no_stop")

    if candidate.stop_kind == "trailing":
        if candidate.stop_lookback is None:
            raise ValueError(f"{candidate.candidate_id} trailing stop requires stop_lookback")
        return btc_above_trailing_price(
            market.price,
            lookback_days=candidate.stop_lookback,
            confirm_days=candidate.stop_confirm_days,
        )

    if candidate.stop_kind == "ma":
        if candidate.ma_window is None:
            raise ValueError(f"{candidate.candidate_id} MA stop requires ma_window")
        return btc_above_moving_average(
            market.price,
            ma_window=candidate.ma_window,
            confirm_days=candidate.stop_confirm_days,
        )

    raise ValueError(f"Unknown stop_kind for {candidate.candidate_id}: {candidate.stop_kind}")


def _build_base_targets(
    market: MarketDataBundle,
    universe: pd.DataFrame,
    config: ResearchConfig,
    candidate: CandidateDefinition,
) -> dict[pd.Timestamp, pd.Series]:
    if candidate.strategy_kind == "ctrend_lite":
        return build_ctrend_lite_targets(
            market,
            universe,
            config,
            top_n=candidate.top_n,
            frequency=candidate.frequency,
            score_family=candidate.score_family,
            include_btc=candidate.include_btc,
        ).targets

    if candidate.strategy_kind == "leader_momentum":
        try:
            score_weights = LEADER_MOMENTUM_WEIGHTS[candidate.score_family]
        except KeyError as exc:
            known_families = ", ".join(sorted(LEADER_MOMENTUM_WEIGHTS))
            raise ValueError(
                f"Unknown leader momentum score_family {candidate.score_family!r}; "
                f"expected one of: {known_families}"
            ) from exc

        regime_frame = pd.DataFrame({"bull": True}, index=market.price.index)
        return build_momentum_lead_targets(
            market,
            universe,
            regime_frame,
            config,
            top_n=candidate.top_n,
            frequency=candidate.frequency,
            regime_mode="always_on",
            weighted=candidate.top_n > 1,
            score_weights=score_weights,
        ).targets

    raise ValueError(
        f"Unknown strategy_kind for {candidate.candidate_id}: {candidate.strategy_kind}"
    )


def _parking_target(candidate: CandidateDefinition, asset: str, field_name: str) -> pd.Series | None:
    try:
        return PARKING_TARGETS[asset]
    except KeyError as exc:
        known_assets = ", ".join(sorted(PARKING_TARGETS))
        raise ValueError(
            f"Unknown {field_name} for {candidate.candidate_id}: {asset!r}; "
            f"expected one of: {known_assets}"
        ) from exc


def _candidate_targets(
    market: MarketDataBundle,
    universe_by_liquidity: dict[str, pd.DataFrame],
    config: ResearchConfig,
    candidate: CandidateDefinition,
) -> dict[pd.Timestamp, pd.Series]:
    try:
        universe = universe_by_liquidity[candidate.liquidity_label]
    except KeyError as exc:
        available = ", ".join(sorted(universe_by_liquidity)) or "<none>"
        raise ValueError(
            f"No universe found for liquidity_label {candidate.liquidity_label!r}; "
            f"available labels: {available}"
        ) from exc

    base_targets = _build_base_targets(market, universe, config, candidate)
    risk_on = _risk_on_series(market, candidate)
    return apply_daily_risk_overlay(
        base_targets,
        risk_on,
        risk_off_target=_parking_target(candidate, candidate.risk_off_asset, "risk_off_asset"),
        initial_target=_parking_target(candidate, candidate.initial_asset, "initial_asset"),
    )


def _friction_with_total_cost(
    base: FrictionConfig,
    total_cost_bps: float | None = None,
) -> FrictionConfig:
    friction = base.model_copy(deep=True)
    if total_cost_bps is not None:
        half_cost = float(total_cost_bps) / 2.0
        friction.fee_bps = half_cost
        friction.slippage_bps = half_cost
    return friction


def _sector_by_coin(market: MarketDataBundle) -> pd.Series:
    if "sector" not in market.metadata.columns:
        raise ValueError("market metadata is missing required 'sector' column")
    return market.metadata["sector"]


def run_one_candidate(
    market: MarketDataBundle,
    universe_by_liquidity: dict[str, pd.DataFrame],
    config: ResearchConfig,
    candidate: CandidateDefinition,
    *,
    total_cost_bps: float | None = None,
) -> BacktestResult:
    targets = _candidate_targets(market, universe_by_liquidity, config, candidate)
    return run_backtest(
        name=candidate.candidate_id,
        asset_returns=market.returns,
        rebalance_targets=targets,
        sector_by_coin=_sector_by_coin(market),
        friction=_friction_with_total_cost(config.frictions, total_cost_bps),
        initial_capital=config.initial_capital,
        gross_target_exposure=1.0,
    )


def run_full_window_screen(
    market: MarketDataBundle,
    universe_by_liquidity: dict[str, pd.DataFrame],
    config: ResearchConfig,
    candidates: list[CandidateDefinition],
) -> tuple[pd.DataFrame, dict[str, BacktestResult]]:
    rows: list[dict[str, object]] = []
    results: dict[str, BacktestResult] = {}

    for candidate in candidates:
        result = run_one_candidate(market, universe_by_liquidity, config, candidate)
        results[candidate.candidate_id] = result

        metrics = compute_summary_metrics(result, config.annualization_days)
        row: dict[str, object] = asdict(candidate)
        row.update(metrics)

        multiple = float(metrics["total_return"]) + 1.0
        row["multiple"] = multiple
        row["best_rolling_5y_multiple"] = multiple
        row["hundred_x_hit_rate_5y"] = 1.0 if multiple >= 100.0 else 0.0
        row["median_rolling_start_multiple"] = multiple
        row["cost_survival_100bps"] = 0.0
        row["stability_score"] = 0.0
        row["trial_count_estimate"] = len(candidates)
        rows.append(row)

    if not rows:
        return pd.DataFrame(), results

    summary = pd.DataFrame(rows)
    summary["raw_convexity_score"] = summary.apply(compute_raw_convexity_score, axis=1)
    summary["robust_convexity_score"] = summary.apply(
        compute_robust_convexity_score,
        axis=1,
    )
    return summary.sort_values(
        ["raw_convexity_score", "multiple"],
        ascending=[False, False],
        kind="mergesort",
    ).reset_index(drop=True), results


def candidate_records(candidates: list[CandidateDefinition]) -> pd.DataFrame:
    return pd.DataFrame([asdict(candidate) for candidate in candidates])


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Top20 convex leader validation.")
    parser.add_argument("--config", default="config/bear_bottom_to_current_2022_11_21_2026_04_22.yaml")
    parser.parse_args()
    print("Task 6 adds full CLI execution.")


if __name__ == "__main__":
    main()
