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
from atlas20.backtest.calendar import get_rebalance_dates  # noqa: E402
from atlas20.backtest.engine import BacktestResult, run_backtest  # noqa: E402
from atlas20.config import FrictionConfig, ResearchConfig, load_config, load_sector_config  # noqa: E402
from atlas20.data.processor import build_processed_datasets  # noqa: E402
from atlas20.logging_utils import configure_logging, ensure_dir  # noqa: E402
from atlas20.reporting.report import dataframe_to_markdown  # noqa: E402
from atlas20.signals.risk import btc_above_moving_average, btc_above_trailing_price  # noqa: E402
from atlas20.strategies.convex_leader import (  # noqa: E402
    CTREND_LITE_SCORE_FAMILIES,
    build_ctrend_lite_targets,
)
from atlas20.strategies.momentum_lead import build_momentum_lead_targets  # noqa: E402
from atlas20.strategies.overlays import apply_daily_risk_overlay  # noqa: E402
from atlas20.universe.builder import (  # noqa: E402
    MarketDataBundle,
    build_rebalance_universe,
    prepare_market_data,
)


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

CHAMPION_CANDIDATE_ID = (
    "champion_ablation__leader_momentum__top1__14d__base__loose__with_btc__"
    "champion_ablation_stop11"
)


FULL_WINDOW_SCREEN_COLUMNS: tuple[str, ...] = (
    *CandidateDefinition.__dataclass_fields__,
    "total_return",
    "cagr",
    "annualized_volatility",
    "sharpe",
    "sortino",
    "max_drawdown",
    "calmar",
    "monthly_win_rate",
    "annualized_turnover",
    "avg_turnover_per_rebalance",
    "average_holdings",
    "multiple",
    "best_rolling_5y_multiple",
    "hundred_x_hit_rate_5y",
    "median_rolling_start_multiple",
    "cost_survival_100bps",
    "stability_score",
    "trial_count_estimate",
    "raw_convexity_score",
    "robust_convexity_score",
)

ROLLING_START_DETAIL_COLUMNS: tuple[str, ...] = (
    "candidate_id",
    "start_date",
    "multiple",
    "cagr",
    "sharpe",
    "max_drawdown",
    "annualized_turnover",
)

ROLLING_START_SUMMARY_COLUMNS: tuple[str, ...] = (
    "candidate_id",
    "start_count",
    "median_rolling_start_multiple",
    "min_rolling_start_multiple",
    "max_rolling_start_multiple",
    "max_rolling_start_drawdown",
    "median_rolling_start_drawdown",
)

HUNDRED_X_WINDOWS_COLUMNS: tuple[str, ...] = (
    "candidate_id",
    "window_label",
    "window_end",
    "multiple",
)

COST_SENSITIVITY_COLUMNS: tuple[str, ...] = (
    "candidate_id",
    "total_cost_bps",
    "base_multiple",
    "stressed_multiple",
    "survival_ratio",
)

STABILITY_SURFACE_COLUMNS: tuple[str, ...] = (
    "candidate_id",
    "neighbor_count",
    "median_neighbor_multiple",
    "stability_score",
)

STABILITY_REQUIRED_COLUMNS: tuple[str, ...] = (
    "candidate_id",
    "family_id",
    "strategy_kind",
    "score_family",
    "include_btc",
    "liquidity_label",
    "top_n",
    "frequency",
    "stop_kind",
    "stop_lookback",
    "stop_confirm_days",
    "ma_window",
    "risk_off_asset",
    "initial_asset",
    "multiple",
)

CONTRIBUTION_SUMMARY_COLUMNS: tuple[str, ...] = (
    "candidate_id",
    "top_coin_id",
    "top1_contribution_share",
    "top3_contribution_share",
    "top5_contribution_share",
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
    start_date: pd.Timestamp | None = None,
) -> BacktestResult:
    local_config = config
    if start_date is not None:
        local_config = config.model_copy(deep=True)
        local_config.start_date = pd.Timestamp(start_date).strftime("%Y-%m-%d")

    targets = _candidate_targets(market, universe_by_liquidity, local_config, candidate)
    asset_returns = market.returns.loc[
        local_config.start_timestamp : local_config.end_timestamp
    ]
    return run_backtest(
        name=candidate.candidate_id,
        asset_returns=asset_returns,
        rebalance_targets=targets,
        sector_by_coin=_sector_by_coin(market),
        friction=_friction_with_total_cost(local_config.frictions, total_cost_bps),
        initial_capital=local_config.initial_capital,
        gross_target_exposure=1.0,
    )


def _monthly_start_dates(start: pd.Timestamp, end: pd.Timestamp) -> list[pd.Timestamp]:
    start_timestamp = pd.Timestamp(start).normalize()
    end_timestamp = pd.Timestamp(end).normalize()
    if start_timestamp > end_timestamp:
        return []

    dates = [start_timestamp]
    dates.extend(
        pd.Timestamp(date).normalize()
        for date in pd.date_range(start_timestamp, end_timestamp, freq="MS")
        if pd.Timestamp(date).normalize() != start_timestamp
    )
    return list(dict.fromkeys(sorted(dates)))


def compute_rolling_start_validation(
    market: MarketDataBundle,
    universe_by_liquidity: dict[str, pd.DataFrame],
    config: ResearchConfig,
    candidate_by_id: dict[str, CandidateDefinition],
    candidate_ids: list[str],
    *,
    min_days_after_start: int = 365,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    empty_summary = pd.DataFrame(columns=ROLLING_START_SUMMARY_COLUMNS)
    empty_detail = pd.DataFrame(columns=ROLLING_START_DETAIL_COLUMNS)
    if not candidate_ids:
        return empty_summary, empty_detail

    missing_candidate_ids = [
        candidate_id for candidate_id in candidate_ids if candidate_id not in candidate_by_id
    ]
    if missing_candidate_ids:
        missing = ", ".join(missing_candidate_ids)
        raise ValueError(f"candidate_by_id is missing candidate id(s): {missing}")

    if market.price.empty:
        return empty_summary, empty_detail

    max_market_date = pd.Timestamp(market.price.index.max())
    max_validation_date = min(max_market_date, config.end_timestamp)
    max_start = max_validation_date - pd.Timedelta(days=min_days_after_start)
    start_dates = [
        start_date
        for start_date in _monthly_start_dates(config.start_timestamp, max_validation_date)
        if start_date <= max_start
    ]
    if not start_dates:
        return empty_summary, empty_detail

    rows: list[dict[str, object]] = []
    for candidate_id in candidate_ids:
        candidate = candidate_by_id[candidate_id]
        for start_date in start_dates:
            result = run_one_candidate(
                market,
                universe_by_liquidity,
                config,
                candidate,
                start_date=start_date,
            )
            metrics = compute_summary_metrics(result, config.annualization_days)
            rows.append(
                {
                    "candidate_id": candidate_id,
                    "start_date": start_date.date().isoformat(),
                    "multiple": float(metrics["total_return"]) + 1.0,
                    "cagr": metrics["cagr"],
                    "sharpe": metrics["sharpe"],
                    "max_drawdown": metrics["max_drawdown"],
                    "annualized_turnover": metrics["annualized_turnover"],
                }
            )

    by_candidate = pd.DataFrame(rows, columns=ROLLING_START_DETAIL_COLUMNS)
    if by_candidate.empty:
        return empty_summary, by_candidate

    summary = (
        by_candidate.groupby("candidate_id")
        .agg(
            start_count=("start_date", "count"),
            median_rolling_start_multiple=("multiple", "median"),
            min_rolling_start_multiple=("multiple", "min"),
            max_rolling_start_multiple=("multiple", "max"),
            max_rolling_start_drawdown=("max_drawdown", "min"),
            median_rolling_start_drawdown=("max_drawdown", "median"),
        )
        .reset_index()
    )
    candidate_order = {candidate_id: index for index, candidate_id in enumerate(candidate_ids)}
    summary["_candidate_order"] = summary["candidate_id"].map(candidate_order)
    summary = summary.sort_values("_candidate_order", kind="mergesort").drop(
        columns="_candidate_order"
    )
    return summary.reset_index(drop=True), by_candidate


def _rolling_window_label(window_days: int) -> str:
    if window_days % 365 == 0:
        return f"{window_days // 365}y"
    return f"{window_days}d"


def _rolling_window_summary_columns(windows_days: tuple[int, ...]) -> list[str]:
    columns = ["candidate_id"]
    for window_days in windows_days:
        label = _rolling_window_label(window_days)
        columns.extend(
            [
                f"best_rolling_{label}_multiple",
                f"median_rolling_{label}_multiple",
                f"hundred_x_hit_rate_{label}",
            ]
        )
    return columns


def _rolling_compounded_multiples(returns: pd.Series, window_days: int) -> pd.Series:
    if window_days <= 0 or returns.empty or len(returns) < window_days:
        return pd.Series(dtype=float)

    gross_returns = 1.0 + returns
    return gross_returns.rolling(window_days).apply(
        lambda values: float(values.prod()),
        raw=True,
    ).dropna()


def _hundred_x_mask(multiples: pd.Series) -> pd.Series:
    return multiples >= 100.0 - 1e-9


def _stable_multiple(value: object) -> float:
    multiple = _safe_float(value)
    if math.isclose(multiple, 100.0, rel_tol=0.0, abs_tol=1e-9):
        return 100.0
    return multiple


def compute_rolling_window_summary(
    daily_returns_by_candidate: dict[str, pd.Series],
    *,
    windows_days: tuple[int, ...] = (365 * 3, 365 * 5),
) -> tuple[pd.DataFrame, pd.DataFrame]:
    summary_columns = _rolling_window_summary_columns(windows_days)
    if not daily_returns_by_candidate:
        return (
            pd.DataFrame(columns=summary_columns),
            pd.DataFrame(columns=HUNDRED_X_WINDOWS_COLUMNS),
        )

    summary_rows: list[dict[str, object]] = []
    window_rows: list[dict[str, object]] = []
    for candidate_id, returns in daily_returns_by_candidate.items():
        clean_returns = (
            pd.to_numeric(returns, errors="coerce")
            .replace([math.inf, -math.inf], 0.0)
            .fillna(0.0)
            .sort_index()
        )
        row: dict[str, object] = {"candidate_id": candidate_id}
        for window_days in windows_days:
            label = _rolling_window_label(window_days)
            rolling_multiple = _rolling_compounded_multiples(clean_returns, window_days)
            if rolling_multiple.empty:
                row[f"best_rolling_{label}_multiple"] = 0.0
                row[f"median_rolling_{label}_multiple"] = 0.0
                row[f"hundred_x_hit_rate_{label}"] = 0.0
                continue

            hit_mask = _hundred_x_mask(rolling_multiple)
            row[f"best_rolling_{label}_multiple"] = _stable_multiple(
                rolling_multiple.max()
            )
            row[f"median_rolling_{label}_multiple"] = float(rolling_multiple.median())
            row[f"hundred_x_hit_rate_{label}"] = float(hit_mask.mean())
            for window_end, multiple in rolling_multiple[hit_mask].items():
                window_rows.append(
                    {
                        "candidate_id": candidate_id,
                        "window_label": label,
                        "window_end": window_end,
                        "multiple": _stable_multiple(multiple),
                    }
                )
        summary_rows.append(row)

    return (
        pd.DataFrame(summary_rows, columns=summary_columns),
        pd.DataFrame(window_rows, columns=HUNDRED_X_WINDOWS_COLUMNS),
    )


def compute_cost_sensitivity(
    base_summary: pd.DataFrame,
    stressed_multiples: dict[float, dict[str, float]],
) -> pd.DataFrame:
    if base_summary.empty or not stressed_multiples:
        return pd.DataFrame(columns=COST_SENSITIVITY_COLUMNS)

    required_columns = {"candidate_id", "multiple"}
    missing_columns = sorted(required_columns.difference(base_summary.columns))
    if missing_columns:
        missing = ", ".join(missing_columns)
        raise ValueError(f"base_summary is missing required column(s): {missing}")

    base_by_id = base_summary.drop_duplicates("candidate_id").set_index("candidate_id")
    rows: list[dict[str, object]] = []
    for total_cost_bps in sorted(stressed_multiples):
        for candidate_id in sorted(stressed_multiples[total_cost_bps]):
            if candidate_id not in base_by_id.index:
                continue
            base_multiple = _safe_float(base_by_id.loc[candidate_id, "multiple"])
            stressed_multiple = _safe_float(stressed_multiples[total_cost_bps][candidate_id])
            rows.append(
                {
                    "candidate_id": candidate_id,
                    "total_cost_bps": float(total_cost_bps),
                    "base_multiple": base_multiple,
                    "stressed_multiple": stressed_multiple,
                    "survival_ratio": (
                        stressed_multiple / base_multiple if base_multiple > 0.0 else 0.0
                    ),
                }
            )
    return pd.DataFrame(rows, columns=COST_SENSITIVITY_COLUMNS)


def _duration_days(value: object) -> int | None:
    if pd.isna(value):
        return None
    try:
        return int(pd.Timedelta(str(value)).days)
    except ValueError:
        try:
            return int(value)
        except (TypeError, ValueError):
            return None


def _near_frequency(left: object, right: object) -> bool:
    if str(left) == str(right):
        return True
    left_days = _duration_days(left)
    right_days = _duration_days(right)
    return left_days is not None and right_days is not None and abs(left_days - right_days) <= 7


def _optional_float(value: object) -> float | None:
    if pd.isna(value):
        return None
    numeric = _safe_float(value, default=math.nan)
    if math.isnan(numeric):
        return None
    return numeric


def _near_optional_number(left: object, right: object, *, tolerance: float) -> bool:
    left_number = _optional_float(left)
    right_number = _optional_float(right)
    if left_number is None or right_number is None:
        return left_number is None and right_number is None
    return abs(left_number - right_number) <= tolerance


def _matches_when_present(left: pd.Series, right: pd.Series, column: str) -> bool:
    if column not in left.index or column not in right.index:
        return True
    left_value = left.get(column)
    right_value = right.get(column)
    if pd.isna(left_value) or pd.isna(right_value):
        return pd.isna(left_value) and pd.isna(right_value)
    return left_value == right_value


def _candidate_surface_matches(candidate: pd.Series, neighbor: pd.Series) -> bool:
    exact_columns = (
        "strategy_kind",
        "score_family",
        "include_btc",
        "liquidity_label",
        "stop_kind",
        "risk_off_asset",
        "initial_asset",
        "stop_confirm_days",
    )
    if any(
        not _matches_when_present(neighbor, candidate, column) for column in exact_columns
    ):
        return False

    if "ma_window" in candidate.index and "ma_window" in neighbor.index:
        return _near_optional_number(
            neighbor.get("ma_window"),
            candidate.get("ma_window"),
            tolerance=1.0,
        )
    return True


def compute_stability_surface(
    summary: pd.DataFrame,
    *,
    candidate_ids: list[str],
    multiple_floor: float,
) -> pd.DataFrame:
    if summary.empty or not candidate_ids:
        return pd.DataFrame(columns=STABILITY_SURFACE_COLUMNS)

    missing_columns = sorted(set(STABILITY_REQUIRED_COLUMNS).difference(summary.columns))
    if missing_columns:
        missing = ", ".join(missing_columns)
        raise ValueError(f"summary is missing required column(s): {missing}")

    indexed = summary.drop_duplicates("candidate_id").set_index("candidate_id")
    rows: list[dict[str, object]] = []
    for candidate_id in candidate_ids:
        if candidate_id not in indexed.index:
            continue

        candidate = indexed.loc[candidate_id]
        neighbors: list[pd.Series] = []
        same_family = summary[summary["family_id"] == candidate["family_id"]]
        for _, neighbor in same_family.iterrows():
            if neighbor["candidate_id"] == candidate_id:
                continue
            if not _candidate_surface_matches(candidate, neighbor):
                continue
            if _safe_float(neighbor["multiple"]) < multiple_floor:
                continue
            if abs(_safe_float(neighbor["top_n"]) - _safe_float(candidate["top_n"])) > 1:
                continue
            if not _near_frequency(neighbor["frequency"], candidate["frequency"]):
                continue
            if not _near_optional_number(
                neighbor.get("stop_lookback"),
                candidate.get("stop_lookback"),
                tolerance=1.0,
            ):
                continue
            neighbors.append(neighbor)

        neighbor_count = len(neighbors)
        if neighbor_count:
            neighbor_multiples = pd.Series(
                [_safe_float(neighbor["multiple"]) for neighbor in neighbors]
            )
            median_neighbor_multiple = float(neighbor_multiples.median())
        else:
            median_neighbor_multiple = 0.0

        base_multiple = _safe_float(candidate["multiple"])
        stability_score = (
            min(median_neighbor_multiple / base_multiple, 1.0)
            if neighbor_count and base_multiple > 0.0
            else 0.0
        )
        rows.append(
            {
                "candidate_id": candidate_id,
                "neighbor_count": neighbor_count,
                "median_neighbor_multiple": median_neighbor_multiple,
                "stability_score": stability_score,
            }
        )
    return pd.DataFrame(rows, columns=STABILITY_SURFACE_COLUMNS)


def compute_contribution_summary(
    results: dict[str, BacktestResult],
    market: MarketDataBundle,
) -> pd.DataFrame:
    if not results:
        return pd.DataFrame(columns=CONTRIBUTION_SUMMARY_COLUMNS)

    rows: list[dict[str, object]] = []
    for candidate_id, result in results.items():
        weights = result.weights.reindex(columns=market.returns.columns).fillna(0.0)
        if weights.empty:
            rows.append(
                {
                    "candidate_id": candidate_id,
                    "top_coin_id": "",
                    "top1_contribution_share": 0.0,
                    "top3_contribution_share": 0.0,
                    "top5_contribution_share": 0.0,
                }
            )
            continue

        asset_returns = market.returns.reindex(
            index=weights.index,
            columns=weights.columns,
        ).fillna(0.0)
        contribution = (
            weights.shift(1).fillna(0.0).mul(asset_returns).sum(axis=0).sort_values(
                ascending=False,
                kind="mergesort",
            )
        )
        positive_contribution = contribution[contribution > 0.0]
        total_positive = float(positive_contribution.sum())
        if total_positive <= 0.0:
            rows.append(
                {
                    "candidate_id": candidate_id,
                    "top_coin_id": "",
                    "top1_contribution_share": 0.0,
                    "top3_contribution_share": 0.0,
                    "top5_contribution_share": 0.0,
                }
            )
            continue

        rows.append(
            {
                "candidate_id": candidate_id,
                "top_coin_id": str(positive_contribution.index[0]),
                "top1_contribution_share": float(
                    positive_contribution.head(1).sum() / total_positive
                ),
                "top3_contribution_share": float(
                    positive_contribution.head(3).sum() / total_positive
                ),
                "top5_contribution_share": float(
                    positive_contribution.head(5).sum() / total_positive
                ),
            }
        )
    return pd.DataFrame(rows, columns=CONTRIBUTION_SUMMARY_COLUMNS)


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
        row["median_rolling_start_multiple"] = multiple
        row["cost_survival_100bps"] = 0.0
        row["stability_score"] = 0.0
        row["trial_count_estimate"] = len(candidates)
        rows.append(row)

    if not rows:
        return pd.DataFrame(columns=FULL_WINDOW_SCREEN_COLUMNS), results

    summary = pd.DataFrame(rows)
    rolling_summary, _ = compute_rolling_window_summary(
        {
            candidate_id: result.daily_returns
            for candidate_id, result in results.items()
        }
    )
    if not rolling_summary.empty:
        summary = summary.merge(rolling_summary, on="candidate_id", how="left")
    for column in _rolling_window_summary_columns((365 * 3, 365 * 5)):
        if column == "candidate_id":
            continue
        if column not in summary.columns:
            summary[column] = 0.0
        summary[column] = pd.to_numeric(summary[column], errors="coerce").fillna(0.0)

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


def _candidate_ids_from_frame(frame: pd.DataFrame) -> set[str]:
    if frame.empty or "candidate_id" not in frame.columns:
        return set()
    return set(frame["candidate_id"].dropna().astype(str))


def _assign_diagnostic_columns(
    summary: pd.DataFrame,
    diagnostics: pd.DataFrame,
    columns: list[str],
) -> None:
    if diagnostics.empty or "candidate_id" not in diagnostics.columns:
        return

    indexed = diagnostics.drop_duplicates("candidate_id").copy()
    indexed["candidate_id"] = indexed["candidate_id"].astype(str)
    indexed = indexed.set_index("candidate_id")
    candidate_ids = summary["candidate_id"].astype(str)
    for column in columns:
        if column not in indexed.columns:
            continue
        if column not in summary.columns:
            summary[column] = math.nan
        mapped = candidate_ids.map(indexed[column])
        present = mapped.notna()
        summary.loc[present, column] = mapped[present]


def _cost_survival_at_100bps(cost_sensitivity: pd.DataFrame) -> pd.DataFrame:
    if cost_sensitivity.empty or "candidate_id" not in cost_sensitivity.columns:
        return pd.DataFrame(columns=["candidate_id", "cost_survival_100bps"])
    required_columns = {"total_cost_bps", "survival_ratio"}
    if not required_columns.issubset(cost_sensitivity.columns):
        return pd.DataFrame(columns=["candidate_id", "cost_survival_100bps"])

    frame = cost_sensitivity.copy()
    frame["_total_cost_bps"] = pd.to_numeric(frame["total_cost_bps"], errors="coerce")
    frame = frame[(frame["_total_cost_bps"] - 100.0).abs() <= 1e-9]
    if frame.empty:
        return pd.DataFrame(columns=["candidate_id", "cost_survival_100bps"])
    frame = frame.drop_duplicates("candidate_id", keep="last")
    return frame[["candidate_id", "survival_ratio"]].rename(
        columns={"survival_ratio": "cost_survival_100bps"}
    )


def build_validated_candidate_summary(
    candidate_summary: pd.DataFrame,
    *,
    rolling_start_summary: pd.DataFrame,
    cost_sensitivity: pd.DataFrame,
    stability_surface: pd.DataFrame,
) -> pd.DataFrame:
    summary = candidate_summary.copy()
    if summary.empty:
        return summary
    if "candidate_id" not in summary.columns:
        raise ValueError("candidate_summary is missing required column: candidate_id")

    if "raw_convexity_score" in summary.columns and "screening_raw_convexity_score" not in summary:
        summary["screening_raw_convexity_score"] = summary["raw_convexity_score"]
    if (
        "robust_convexity_score" in summary.columns
        and "screening_robust_convexity_score" not in summary
    ):
        summary["screening_robust_convexity_score"] = summary["robust_convexity_score"]

    validation_ids = (
        _candidate_ids_from_frame(rolling_start_summary)
        | _candidate_ids_from_frame(cost_sensitivity)
        | _candidate_ids_from_frame(stability_surface)
    )

    _assign_diagnostic_columns(
        summary,
        rolling_start_summary,
        [
            "start_count",
            "median_rolling_start_multiple",
            "min_rolling_start_multiple",
            "max_rolling_start_multiple",
            "max_rolling_start_drawdown",
            "median_rolling_start_drawdown",
        ],
    )
    _assign_diagnostic_columns(
        summary,
        _cost_survival_at_100bps(cost_sensitivity),
        ["cost_survival_100bps"],
    )
    _assign_diagnostic_columns(
        summary,
        stability_surface,
        ["neighbor_count", "median_neighbor_multiple", "stability_score"],
    )

    candidate_ids = summary["candidate_id"].astype(str)
    if "validation_diagnostics_available" not in summary.columns:
        summary["validation_diagnostics_available"] = False
    summary["validation_diagnostics_available"] = (
        summary["validation_diagnostics_available"].fillna(False).astype(bool)
        | candidate_ids.isin(validation_ids)
    )

    if "robust_convexity_score" not in summary.columns:
        summary["robust_convexity_score"] = summary.apply(
            compute_robust_convexity_score,
            axis=1,
        )

    validation_mask = candidate_ids.isin(validation_ids)
    if validation_mask.any():
        summary.loc[validation_mask, "robust_convexity_score"] = summary.loc[
            validation_mask
        ].apply(compute_robust_convexity_score, axis=1)
    summary["validated_robust_convexity_score"] = math.nan
    summary.loc[
        validation_mask,
        "validated_robust_convexity_score",
    ] = summary.loc[validation_mask, "robust_convexity_score"]
    return summary


def _sort_candidates(
    frame: pd.DataFrame,
    score_column: str,
    *,
    limit: int | None = None,
) -> pd.DataFrame:
    if frame.empty:
        return frame.copy()
    if score_column not in frame.columns:
        return frame.head(limit).copy() if limit is not None else frame.copy()

    sortable = frame.copy()
    sortable["_sort_score"] = pd.to_numeric(sortable[score_column], errors="coerce").fillna(
        -math.inf
    )
    if "multiple" in sortable.columns:
        sortable["_sort_multiple"] = pd.to_numeric(
            sortable["multiple"],
            errors="coerce",
        ).fillna(-math.inf)
        sort_columns = ["_sort_score", "_sort_multiple"]
    else:
        sort_columns = ["_sort_score"]
    sorted_frame = sortable.sort_values(
        sort_columns,
        ascending=[False] * len(sort_columns),
        kind="mergesort",
    ).drop(columns=[column for column in ("_sort_score", "_sort_multiple") if column in sortable])
    return sorted_frame.head(limit).copy() if limit is not None else sorted_frame.copy()


def _screening_raw_score_column(frame: pd.DataFrame) -> str:
    if "screening_raw_convexity_score" in frame.columns:
        return "screening_raw_convexity_score"
    return "raw_convexity_score"


def _screening_robust_score_column(frame: pd.DataFrame) -> str:
    if "screening_robust_convexity_score" in frame.columns:
        return "screening_robust_convexity_score"
    return "robust_convexity_score"


def _write_csv(path: Path, frame: pd.DataFrame) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(path, index=False)


def _markdown_table(
    frame: pd.DataFrame,
    columns: list[str],
    *,
    max_rows: int = 10,
) -> str:
    if frame.empty:
        return "No rows."
    available_columns = [column for column in dict.fromkeys(columns) if column in frame.columns]
    if not available_columns:
        return "No matching columns."
    return dataframe_to_markdown(
        frame.head(max_rows)[available_columns].reset_index(drop=True),
        percent_columns={
            "cagr",
            "max_drawdown",
            "monthly_win_rate",
            "hundred_x_hit_rate_3y",
            "hundred_x_hit_rate_5y",
            "cost_survival_100bps",
            "stability_score",
            "survival_ratio",
            "top1_contribution_share",
            "top3_contribution_share",
            "top5_contribution_share",
        },
        number_columns={
            "multiple",
            "best_rolling_3y_multiple",
            "best_rolling_5y_multiple",
            "median_rolling_3y_multiple",
            "median_rolling_5y_multiple",
            "median_rolling_start_multiple",
            "min_rolling_start_multiple",
            "max_rolling_start_multiple",
            "base_multiple",
            "stressed_multiple",
            "median_neighbor_multiple",
            "annualized_turnover",
            "avg_turnover_per_rebalance",
            "average_holdings",
            "sharpe",
            "sortino",
            "calmar",
            "raw_convexity_score",
            "robust_convexity_score",
            "screening_raw_convexity_score",
            "screening_robust_convexity_score",
            "validated_robust_convexity_score",
            "start_count",
            "neighbor_count",
            "total_cost_bps",
        },
    )


def _append_markdown_section(
    lines: list[str],
    title: str,
    frame: pd.DataFrame,
    columns: list[str],
    *,
    max_rows: int = 10,
) -> None:
    lines.extend(
        [
            f"## {title}",
            "",
            _markdown_table(frame, columns, max_rows=max_rows),
            "",
        ]
    )


def _validated_rows(candidate_summary: pd.DataFrame) -> pd.DataFrame:
    if candidate_summary.empty or "validation_diagnostics_available" not in candidate_summary:
        return pd.DataFrame(columns=candidate_summary.columns)
    return candidate_summary[candidate_summary["validation_diagnostics_available"].fillna(False)].copy()


def write_validation_outputs(
    report_dir: Path,
    *,
    candidate_summary: pd.DataFrame,
    champion_ablation: pd.DataFrame,
    rolling_start_summary: pd.DataFrame,
    rolling_start_by_candidate: pd.DataFrame,
    rolling_window_summary: pd.DataFrame,
    hundred_x_windows: pd.DataFrame,
    stability_surface: pd.DataFrame,
    cost_sensitivity: pd.DataFrame,
    liquidity_sensitivity: pd.DataFrame,
    contribution_summary: pd.DataFrame,
    trial_log: pd.DataFrame,
) -> None:
    report_dir.mkdir(parents=True, exist_ok=True)

    raw_top50 = _sort_candidates(
        candidate_summary,
        _screening_raw_score_column(candidate_summary),
        limit=50,
    )
    robust_top50 = _sort_candidates(
        candidate_summary,
        _screening_robust_score_column(candidate_summary),
        limit=50,
    )

    outputs = {
        "candidate_summary.csv": candidate_summary,
        "candidate_top50_raw.csv": raw_top50,
        "candidate_top50_robust.csv": robust_top50,
        "champion_ablation.csv": champion_ablation,
        "rolling_start_summary.csv": rolling_start_summary,
        "rolling_start_by_candidate.csv": rolling_start_by_candidate,
        "rolling_window_summary.csv": rolling_window_summary,
        "hundred_x_windows.csv": hundred_x_windows,
        "stability_surface.csv": stability_surface,
        "cost_sensitivity.csv": cost_sensitivity,
        "liquidity_sensitivity.csv": liquidity_sensitivity,
        "contribution_summary.csv": contribution_summary,
        "trial_log.csv": trial_log,
    }
    for filename, frame in outputs.items():
        _write_csv(report_dir / filename, frame)

    validated_summary = _sort_candidates(
        _validated_rows(candidate_summary),
        "robust_convexity_score",
    )
    markdown_lines: list[str] = [
        "# Top20 Convex Leader Validation",
        "",
        "## Notes",
        "",
        "- Raw and robust screening rankings are full-screen rankings from the full-window screen.",
        "- Full-window screening scores are separate from validated subset diagnostics.",
        "- Validated robustness is only shown after merging rolling-start, 100 bps cost, "
        "and stability diagnostics for selected validation candidates.",
        "- This report is research output only and does not execute trades.",
        "",
    ]
    _append_markdown_section(
        markdown_lines,
        "Best Raw Convexity Candidate",
        raw_top50.head(1),
        [
            "candidate_id",
            "family_id",
            "strategy_kind",
            "top_n",
            "frequency",
            "liquidity_label",
            "multiple",
            "cagr",
            "sharpe",
            "max_drawdown",
            "screening_raw_convexity_score",
            "raw_convexity_score",
        ],
        max_rows=1,
    )
    _append_markdown_section(
        markdown_lines,
        "Best Screening Robust Candidate",
        robust_top50.head(1),
        [
            "candidate_id",
            "family_id",
            "strategy_kind",
            "top_n",
            "frequency",
            "liquidity_label",
            "multiple",
            "cagr",
            "sharpe",
            "max_drawdown",
            "screening_robust_convexity_score",
            "robust_convexity_score",
        ],
        max_rows=1,
    )
    _append_markdown_section(
        markdown_lines,
        "Validated Candidate Diagnostics",
        validated_summary,
        [
            "candidate_id",
            "family_id",
            "multiple",
            "screening_robust_convexity_score",
            "validated_robust_convexity_score",
            "median_rolling_start_multiple",
            "cost_survival_100bps",
            "stability_score",
            "start_count",
            "neighbor_count",
        ],
    )
    _append_markdown_section(
        markdown_lines,
        "100x Rolling Windows",
        hundred_x_windows,
        ["candidate_id", "window_label", "window_end", "multiple"],
        max_rows=25,
    )
    _append_markdown_section(
        markdown_lines,
        "Rolling-Start Diagnostics",
        rolling_start_summary,
        [
            "candidate_id",
            "start_count",
            "median_rolling_start_multiple",
            "min_rolling_start_multiple",
            "max_rolling_start_multiple",
            "max_rolling_start_drawdown",
            "median_rolling_start_drawdown",
        ],
    )
    _append_markdown_section(
        markdown_lines,
        "Cost Sensitivity",
        cost_sensitivity,
        [
            "candidate_id",
            "total_cost_bps",
            "base_multiple",
            "stressed_multiple",
            "survival_ratio",
        ],
    )
    _append_markdown_section(
        markdown_lines,
        "Stability Surface",
        stability_surface,
        [
            "candidate_id",
            "neighbor_count",
            "median_neighbor_multiple",
            "stability_score",
        ],
    )
    _append_markdown_section(
        markdown_lines,
        "Contribution Concentration",
        contribution_summary,
        [
            "candidate_id",
            "top_coin_id",
            "top1_contribution_share",
            "top3_contribution_share",
            "top5_contribution_share",
        ],
    )
    _append_markdown_section(
        markdown_lines,
        "Champion Ablation",
        champion_ablation,
        [
            "candidate_id",
            "overlay_set",
            "stop_lookback",
            "multiple",
            "cagr",
            "sharpe",
            "max_drawdown",
            "raw_convexity_score",
            "robust_convexity_score",
        ],
    )
    (report_dir / "top20_convex_validation_report.md").write_text(
        "\n".join(markdown_lines),
        encoding="utf-8",
    )


def _all_rebalance_dates(
    index: pd.DatetimeIndex,
    config: ResearchConfig,
    *,
    start_anchors: list[pd.Timestamp] | None = None,
) -> list[pd.Timestamp]:
    dates: set[pd.Timestamp] = set()
    anchors = (
        [config.start_timestamp]
        if start_anchors is None
        else list(dict.fromkeys(pd.Timestamp(anchor).normalize() for anchor in start_anchors))
    )
    for start_anchor in anchors:
        for frequency_name, frequency_value in config.rebalancing.frequencies.items():
            dates.update(
                get_rebalance_dates(
                    index,
                    start_anchor,
                    frequency_name,
                    frequency_value,
                )
            )
        for frequency in ("7D", "14D", "21D", "28D"):
            dates.update(
                get_rebalance_dates(
                    index,
                    start_anchor,
                    frequency,
                    frequency,
                )
            )
    return sorted(dates)


def _rolling_start_schedule_anchors(
    market: MarketDataBundle,
    config: ResearchConfig,
    *,
    min_days_after_start: int = 365,
) -> list[pd.Timestamp]:
    anchors = [config.start_timestamp]
    if market.price.empty:
        return anchors

    max_market_date = pd.Timestamp(market.price.index.max())
    max_validation_date = min(max_market_date, config.end_timestamp)
    max_start = max_validation_date - pd.Timedelta(days=min_days_after_start)
    anchors.extend(
        start_date
        for start_date in _monthly_start_dates(config.start_timestamp, max_validation_date)
        if start_date <= max_start
    )
    return list(dict.fromkeys(pd.Timestamp(anchor).normalize() for anchor in anchors))


def _build_universe_variants(
    market: MarketDataBundle,
    config: ResearchConfig,
) -> dict[str, pd.DataFrame]:
    if market.price.empty:
        rebalance_index = market.price.index
    else:
        max_market_date = pd.Timestamp(market.price.index.max())
        max_validation_date = min(max_market_date, config.end_timestamp)
        rebalance_index = market.price.index[market.price.index <= max_validation_date]
    rebalance_dates = _all_rebalance_dates(
        rebalance_index,
        config,
        start_anchors=_rolling_start_schedule_anchors(market, config),
    )
    universe_by_liquidity: dict[str, pd.DataFrame] = {}
    for liquidity_label, (
        min_history_days,
        min_daily_dollar_volume,
    ) in LIQUIDITY_SETS.items():
        local_config = config.model_copy(deep=True)
        local_config.universe.min_history_days = min_history_days
        local_config.universe.min_daily_dollar_volume = min_daily_dollar_volume
        universe_by_liquidity[liquidity_label] = build_rebalance_universe(
            market,
            rebalance_dates,
            local_config,
        )
    return universe_by_liquidity


def _matching_liquidity_rows(
    summary: pd.DataFrame,
    candidate: pd.Series,
) -> pd.DataFrame:
    match_columns = [
        "family_id",
        "strategy_kind",
        "score_family",
        "include_btc",
        "top_n",
        "frequency",
        "overlay_set",
        "stop_kind",
        "stop_lookback",
        "stop_confirm_days",
        "ma_window",
        "risk_off_asset",
        "initial_asset",
    ]
    mask = pd.Series(True, index=summary.index)
    for column in match_columns:
        if column not in summary.columns or column not in candidate.index:
            continue
        value = candidate[column]
        if pd.isna(value):
            mask &= summary[column].isna()
        else:
            mask &= summary[column] == value
    return summary.loc[mask].copy()


def _build_liquidity_sensitivity(
    candidate_summary: pd.DataFrame,
    validation_ids: list[str],
) -> pd.DataFrame:
    columns = [
        "validation_candidate_id",
        "candidate_id",
        "family_id",
        "strategy_kind",
        "score_family",
        "liquidity_label",
        "top_n",
        "frequency",
        "multiple",
        "max_drawdown",
        "annualized_turnover",
        "screening_raw_convexity_score",
        "screening_robust_convexity_score",
        "robust_convexity_score",
    ]
    if candidate_summary.empty or not validation_ids or "candidate_id" not in candidate_summary:
        return pd.DataFrame(columns=columns)

    indexed = candidate_summary.drop_duplicates("candidate_id").copy()
    indexed["candidate_id"] = indexed["candidate_id"].astype(str)
    indexed = indexed.set_index("candidate_id")
    rows: list[pd.DataFrame] = []
    for validation_id in validation_ids:
        if validation_id not in indexed.index:
            continue
        matches = _matching_liquidity_rows(candidate_summary, indexed.loc[validation_id])
        if matches.empty:
            continue
        matches.insert(0, "validation_candidate_id", validation_id)
        rows.append(matches)
    if not rows:
        return pd.DataFrame(columns=columns)

    result = pd.concat(rows, ignore_index=True)
    available_columns = [column for column in columns if column in result.columns]
    return (
        result[available_columns]
        .drop_duplicates(["validation_candidate_id", "candidate_id"])
        .sort_values(["validation_candidate_id", "liquidity_label"], kind="mergesort")
        .reset_index(drop=True)
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Top20 convex leader validation.")
    parser.add_argument(
        "--config",
        default="config/bear_bottom_to_current_2022_11_21_2026_04_22.yaml",
    )
    parser.add_argument("--max-validation-candidates", type=int, default=60)
    parser.add_argument("--min-multiple-for-validation", type=float, default=25.0)
    args = parser.parse_args()

    config = load_config(args.config)
    configure_logging(config.logging.level)
    sector_config = load_sector_config(config.resolve_path("config/sectors.yaml"))
    panel, metadata = build_processed_datasets(config, sector_config)
    market = prepare_market_data(panel, metadata, config)
    universe_by_liquidity = _build_universe_variants(market, config)
    candidates = build_candidate_definitions()

    candidate_summary, results = run_full_window_screen(
        market,
        universe_by_liquidity,
        config,
        candidates,
    )
    candidate_by_id = {candidate.candidate_id: candidate for candidate in candidates}
    validation_ids = select_validation_candidates(
        candidate_summary,
        champion_candidate_id=CHAMPION_CANDIDATE_ID,
        max_validation_candidates=args.max_validation_candidates,
        min_multiple_for_validation=args.min_multiple_for_validation,
    )

    daily_returns_by_candidate = {
        candidate_id: results[candidate_id].daily_returns
        for candidate_id in validation_ids
        if candidate_id in results
    }
    rolling_window_summary, hundred_x_windows = compute_rolling_window_summary(
        daily_returns_by_candidate
    )
    rolling_start_summary, rolling_start_by_candidate = compute_rolling_start_validation(
        market,
        universe_by_liquidity,
        config,
        candidate_by_id,
        validation_ids,
    )
    stability_surface = compute_stability_surface(
        candidate_summary,
        candidate_ids=validation_ids,
        multiple_floor=args.min_multiple_for_validation,
    )

    stressed_multiples: dict[float, dict[str, float]] = {}
    for total_cost_bps in (20.0, 50.0, 100.0, 150.0):
        stressed_multiples[total_cost_bps] = {}
        for candidate_id in validation_ids:
            if candidate_id not in candidate_by_id:
                continue
            stressed_result = run_one_candidate(
                market,
                universe_by_liquidity,
                config,
                candidate_by_id[candidate_id],
                total_cost_bps=total_cost_bps,
            )
            stressed_metrics = compute_summary_metrics(
                stressed_result,
                config.annualization_days,
            )
            stressed_multiples[total_cost_bps][candidate_id] = (
                float(stressed_metrics["total_return"]) + 1.0
            )
    cost_sensitivity = compute_cost_sensitivity(candidate_summary, stressed_multiples)

    validation_results = {
        candidate_id: results[candidate_id]
        for candidate_id in validation_ids
        if candidate_id in results
    }
    contribution_summary = compute_contribution_summary(validation_results, market)
    validated_candidate_summary = build_validated_candidate_summary(
        candidate_summary,
        rolling_start_summary=rolling_start_summary,
        cost_sensitivity=cost_sensitivity,
        stability_surface=stability_surface,
    )
    champion_ablation = validated_candidate_summary[
        validated_candidate_summary["family_id"] == "champion_ablation"
    ].copy()
    liquidity_sensitivity = _build_liquidity_sensitivity(
        validated_candidate_summary,
        validation_ids,
    )
    trial_log = candidate_records(candidates)
    if not trial_log.empty:
        trial_log["selected_for_validation"] = trial_log["candidate_id"].isin(validation_ids)

    report_dir = ensure_dir(
        config.resolve_path(config.paths.reports_dir) / "top20_convex_validation"
    )
    write_validation_outputs(
        report_dir,
        candidate_summary=validated_candidate_summary,
        champion_ablation=champion_ablation,
        rolling_start_summary=rolling_start_summary,
        rolling_start_by_candidate=rolling_start_by_candidate,
        rolling_window_summary=rolling_window_summary,
        hundred_x_windows=hundred_x_windows,
        stability_surface=stability_surface,
        cost_sensitivity=cost_sensitivity,
        liquidity_sensitivity=liquidity_sensitivity,
        contribution_summary=contribution_summary,
        trial_log=trial_log,
    )
    print(f"Wrote Top20 convex validation outputs to {report_dir}")


if __name__ == "__main__":
    main()
