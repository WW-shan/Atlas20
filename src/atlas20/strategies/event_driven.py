"""Daily event-driven leader rotation with hysteresis and minimum holding.

The fixed-calendar rotation used by the original champion only asks the
cross-sectional score for a new leader every 21 days.  A daily strategy can
react faster, but a naive daily top-1 rule also creates enormous turnover and
turns small rank changes into trades.  This module implements the middle
ground used in the research:

* score the point-in-time universe every day;
* keep the current leader while it remains inside a hold-rank band;
* switch only after a confirmation window, or when the challenger's score
  exceeds the incumbent by a no-trade gap;
* enforce a minimum holding period before any discretionary switch.

Signals are emitted on close ``t`` and the backtest engine executes them on
``t+1``.  No leverage or shorting is introduced here.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from atlas20.config import ResearchConfig
from atlas20.strategies.convex_leader import (
    CTREND_LITE_SCORE_FAMILIES,
    compute_ctrend_lite_scores,
)
from atlas20.strategies.momentum_lead import MomentumLeadBuildResult
from atlas20.universe.builder import MarketDataBundle


@dataclass(frozen=True)
class DailyEventSpec:
    """Parameters controlling the daily leader hysteresis rule."""

    min_hold_days: int = 5
    hold_rank: int = 3
    switch_score_gap: float = 0.05
    confirm_days: int = 1
    exit_on_universe_drop: bool = False

    def __post_init__(self) -> None:
        if self.min_hold_days < 0:
            raise ValueError("min_hold_days must be non-negative")
        if self.hold_rank < 1:
            raise ValueError("hold_rank must be at least 1")
        if self.switch_score_gap < 0:
            raise ValueError("switch_score_gap must be non-negative")
        if self.confirm_days < 1:
            raise ValueError("confirm_days must be at least 1")


def compute_daily_score_panel(
    market: MarketDataBundle,
    universe: pd.DataFrame,
    *,
    score_family: str = "ctrend_lite_breakout",
    include_btc: bool = False,
) -> pd.DataFrame:
    """Compute CTREND scores for every point-in-time universe snapshot.

    ``universe`` may contain daily snapshots or a coarser schedule.  Each row
    in the returned frame is indexed by signal date and contains only coins
    eligible on that date, so a new Top-20 entrant is available immediately
    when the caller supplies a daily universe.
    """
    if score_family not in CTREND_LITE_SCORE_FAMILIES:
        known = ", ".join(sorted(CTREND_LITE_SCORE_FAMILIES))
        raise ValueError(f"Unknown score_family {score_family!r}; expected one of: {known}")
    if universe.empty:
        return pd.DataFrame(dtype=float)

    universe = universe.copy()
    universe["rebalance_date"] = pd.to_datetime(universe["rebalance_date"]).dt.normalize()
    weights = CTREND_LITE_SCORE_FAMILIES[score_family]
    rows: list[pd.Series] = []
    index: list[pd.Timestamp] = []

    for date, snapshot in universe.groupby("rebalance_date", sort=True):
        signal_date = pd.Timestamp(date)
        coin_ids = snapshot["coin_id"].astype(str).tolist()
        if not include_btc:
            coin_ids = [coin_id for coin_id in coin_ids if coin_id != "bitcoin"]
        scores = compute_ctrend_lite_scores(market, signal_date, coin_ids, weights)
        index.append(signal_date)
        rows.append(scores.rename(signal_date))

    if not rows:
        return pd.DataFrame(dtype=float)
    return pd.DataFrame(rows, index=pd.DatetimeIndex(index)).sort_index()


def _ranked_scores(scores: pd.Series) -> pd.Series:
    clean = pd.to_numeric(scores, errors="coerce").replace([np.inf, -np.inf], np.nan).dropna()
    if clean.empty:
        return clean
    return clean.sort_values(ascending=False, kind="mergesort")


def build_daily_event_targets_from_scores(
    market: MarketDataBundle,
    score_panel: pd.DataFrame,
    config: ResearchConfig,
    spec: DailyEventSpec,
) -> MomentumLeadBuildResult:
    """Build daily targets from a precomputed score panel.

    A target is emitted for every date, including unchanged days.  The
    backtest engine sees a zero-turnover target when the holding is unchanged;
    emitting the full path makes the daily risk overlay and T+1 semantics
    explicit and prevents stale re-entry targets.
    """
    start = pd.Timestamp(config.start_timestamp).normalize()
    end = pd.Timestamp(config.end_timestamp).normalize()
    signal_dates = market.price.index[(market.price.index >= start) & (market.price.index <= end)]

    current_asset: str | None = None
    held_days = 0
    weak_days = 0
    targets: dict[pd.Timestamp, pd.Series] = {}
    rows: list[dict[str, object]] = []

    for date in signal_dates:
        signal_date = pd.Timestamp(date)
        if signal_date in score_panel.index:
            scores = _ranked_scores(score_panel.loc[signal_date])
        else:
            scores = pd.Series(dtype=float)

        top_asset: str | None = None
        top_score = np.nan
        current_rank = np.nan
        current_score = np.nan
        event = "hold"

        if not scores.empty:
            top_asset = str(scores.index[0])
            top_score = float(scores.iloc[0])

            if current_asset is None:
                current_asset = top_asset
                held_days = 0
                weak_days = 0
                event = "enter"
            else:
                missing_from_universe = current_asset not in scores.index
                if not missing_from_universe:
                    current_score = float(scores.loc[current_asset])
                    current_rank = int(scores.index.get_loc(current_asset)) + 1
                    weak_days = weak_days + 1 if current_rank > spec.hold_rank else 0
                else:
                    weak_days += 1

                can_switch = held_days >= spec.min_hold_days or (
                    spec.exit_on_universe_drop and missing_from_universe
                )
                gap = top_score - current_score if np.isfinite(current_score) else np.inf
                gap_trigger = top_asset != current_asset and gap >= spec.switch_score_gap
                rank_trigger = weak_days >= spec.confirm_days
                if can_switch and (gap_trigger or rank_trigger):
                    current_asset = top_asset
                    held_days = 0
                    weak_days = 0
                    event = "switch"
        else:
            # No eligible asset on this signal date.  The only safe target is
            # cash; do not silently retain an asset that has left the universe.
            if current_asset is not None:
                event = "universe_empty"
            current_asset = None
            held_days = 0
            weak_days = 0

        if current_asset is None:
            target = pd.Series(dtype=float)
        else:
            target = pd.Series({current_asset: 1.0}, dtype=float)
        targets[signal_date] = target

        rows.append(
            {
                "rebalance_date": signal_date,
                "coin_id": current_asset or "",
                "coin_rank": current_rank,
                "coin_score": current_score,
                "coin_weight": 1.0 if current_asset is not None else 0.0,
                "event": event,
                "held_days": held_days,
                "top_candidate": top_asset or "",
                "top_score": top_score,
                "switch_gap": (
                    float(top_score - current_score)
                    if np.isfinite(top_score) and np.isfinite(current_score)
                    else np.nan
                ),
                "weak_days": weak_days,
            }
        )

        if current_asset is not None:
            held_days += 1

    return MomentumLeadBuildResult(
        targets=targets,
        selection_history=pd.DataFrame(rows),
    )
