"""Phase-invariant multi-horizon momentum leader rotation.

The strategy intentionally uses simple, transparent trailing-return signals
rather than one optimized factor score.  Each signal is run in several
calendar phases, and the sleeves are equal-weighted.  This removes the
single-start-date sensitivity that invalidated the earlier fixed-calendar
champion while keeping the portfolio inside the point-in-time Top20.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from atlas20.signals.risk import btc_above_moving_average, realized_volatility
from atlas20.universe.builder import MarketDataBundle


@dataclass(frozen=True)
class MomentumSignalSpec:
    """A simple weighted trailing-return signal."""

    name: str
    window_weights: tuple[tuple[int, float], ...]

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("signal name must be non-empty")
        if not self.window_weights:
            raise ValueError("at least one return window is required")
        if any(window <= 0 for window, _ in self.window_weights):
            raise ValueError("return windows must be positive")
        if any(weight < 0.0 for _, weight in self.window_weights):
            raise ValueError("signal weights must be non-negative")
        if sum(weight for _, weight in self.window_weights) <= 0.0:
            raise ValueError("signal weights must sum to a positive value")


@dataclass(frozen=True)
class PhaseMomentumSpec:
    """Portfolio construction rules for one phase-invariant momentum ensemble."""

    rebalance_days: int = 3
    phase_offsets: tuple[int, ...] = (0, 1, 2)
    hold_rank: int = 2
    btc_ma_window: int = 100
    btc_confirm_days: int = 2
    target_volatility: float = 0.80
    vol_window: int = 60
    weight_tolerance: float = 0.05
    use_btc_gate: bool = True
    use_volatility_target: bool = True

    def __post_init__(self) -> None:
        if self.rebalance_days < 1:
            raise ValueError("rebalance_days must be at least 1")
        if not self.phase_offsets:
            raise ValueError("at least one phase offset is required")
        if any(offset < 0 or offset >= self.rebalance_days for offset in self.phase_offsets):
            raise ValueError("phase offsets must be in [0, rebalance_days)")
        if self.hold_rank < 1:
            raise ValueError("hold_rank must be at least 1")
        if self.btc_ma_window < 2:
            raise ValueError("btc_ma_window must be at least 2")
        if self.btc_confirm_days < 1:
            raise ValueError("btc_confirm_days must be at least 1")
        if self.target_volatility <= 0.0:
            raise ValueError("target_volatility must be positive")
        if self.vol_window < 2:
            raise ValueError("vol_window must be at least 2")
        if self.weight_tolerance < 0.0:
            raise ValueError("weight_tolerance must be non-negative")


PRIMARY_SIGNAL_SPECS: tuple[MomentumSignalSpec, ...] = (
    MomentumSignalSpec(
        name="weighted_multi_horizon",
        window_weights=((7, 0.10), (14, 0.15), (21, 0.20), (28, 0.25), (42, 0.15), (60, 0.15)),
    ),
    MomentumSignalSpec(name="ret21", window_weights=((21, 1.0),)),
    MomentumSignalSpec(
        name="equal_7_14_28_60",
        window_weights=((7, 0.25), (14, 0.25), (28, 0.25), (60, 0.25)),
    ),
    MomentumSignalSpec(
        name="equal_14_21_28",
        window_weights=((14, 1.0 / 3.0), (21, 1.0 / 3.0), (28, 1.0 / 3.0)),
    ),
)


@dataclass(frozen=True)
class SleeveTargets:
    """Sparse target events for one signal/phase sleeve."""

    signal_name: str
    phase_offset: int
    assets: pd.Series
    weights: pd.Series
    selection_history: pd.DataFrame


@dataclass(frozen=True)
class PhaseMomentumBuildResult:
    """Aggregate target events and audit history for all sleeves."""

    targets: dict[pd.Timestamp, pd.Series]
    exposures: dict[pd.Timestamp, float]
    selection_history: pd.DataFrame
    sleeve_targets: tuple[SleeveTargets, ...]


def _trailing_return(
    price: pd.DataFrame,
    signal_date: pd.Timestamp,
    coin_ids: list[str],
    window: int,
) -> pd.Series:
    current = pd.to_numeric(price.loc[signal_date].reindex(coin_ids), errors="coerce")
    base = pd.to_numeric(price.shift(window).loc[signal_date].reindex(coin_ids), errors="coerce")
    return (current / base - 1.0).replace([np.inf, -np.inf], np.nan)


def build_signal_panel(
    market: MarketDataBundle,
    universe: pd.DataFrame,
    signal_spec: MomentumSignalSpec,
    *,
    include_btc: bool = True,
) -> pd.DataFrame:
    """Compute a signal for every point-in-time universe snapshot."""
    if universe.empty:
        return pd.DataFrame(dtype=float)

    universe = universe.copy()
    universe["rebalance_date"] = pd.to_datetime(universe["rebalance_date"]).dt.normalize()
    rows: list[pd.Series] = []
    index: list[pd.Timestamp] = []

    for signal_date, snapshot in universe.groupby("rebalance_date", sort=True):
        coin_ids = list(dict.fromkeys(snapshot["coin_id"].astype(str).tolist()))
        if not include_btc:
            coin_ids = [coin_id for coin_id in coin_ids if coin_id != "bitcoin"]
        if not coin_ids:
            continue

        score = pd.Series(0.0, index=coin_ids, dtype=float)
        valid = pd.Series(True, index=coin_ids, dtype=bool)
        for window, weight in signal_spec.window_weights:
            trailing = _trailing_return(market.price, pd.Timestamp(signal_date), coin_ids, int(window))
            score = score.add(trailing.fillna(0.0) * float(weight), fill_value=0.0)
            # A new entrant must have every signal window available.  Using a
            # partial history would let a just-listed coin rank on a shorter
            # horizon alone and would violate the point-in-time completeness
            # requirement for newly admitted Top20 members.
            valid &= trailing.notna()
        score = score.where(valid)
        rows.append(score.rename(pd.Timestamp(signal_date)))
        index.append(pd.Timestamp(signal_date))

    if not rows:
        return pd.DataFrame(dtype=float)
    return pd.DataFrame(rows, index=pd.DatetimeIndex(index)).sort_index()


def _desired_exposure(
    volatility: pd.DataFrame,
    signal_date: pd.Timestamp,
    asset: str | None,
    *,
    target_volatility: float,
) -> float:
    if asset is None:
        return 0.0
    if asset not in volatility.columns or signal_date not in volatility.index:
        return 1.0
    daily_vol = float(volatility.at[signal_date, asset])
    if not np.isfinite(daily_vol) or daily_vol <= 0.0:
        return 1.0
    # realized_volatility returns annualized volatility.  A target below the
    # realized level reduces exposure; a target above it never creates leverage.
    return min(1.0, float(target_volatility) / daily_vol)


def build_sleeve_targets(
    market: MarketDataBundle,
    signal_panel: pd.DataFrame,
    index: pd.DatetimeIndex,
    spec: PhaseMomentumSpec,
    *,
    signal_name: str,
    phase_offset: int,
) -> SleeveTargets:
    """Build sparse target events for one signal and one phase offset."""
    if phase_offset not in spec.phase_offsets:
        raise ValueError("phase_offset must be present in spec.phase_offsets")
    if index.empty:
        empty = pd.Series(dtype=float)
        return SleeveTargets(signal_name, phase_offset, empty, empty, pd.DataFrame())

    start = pd.Timestamp(index[0]).normalize()
    if spec.use_btc_gate:
        gate = btc_above_moving_average(
            market.price,
            ma_window=spec.btc_ma_window,
            confirm_days=spec.btc_confirm_days,
        ).reindex(index).fillna(False)
    else:
        gate = pd.Series(True, index=index, dtype=bool)
    volatility = (
        realized_volatility(market.price, window=spec.vol_window).reindex(index)
        if spec.use_volatility_target
        else None
    )
    assets = pd.Series(pd.NA, index=index, dtype="object")
    weights = pd.Series(np.nan, index=index, dtype=float)
    history: list[dict[str, object]] = []
    selected: str | None = None
    previous_asset: str | None = None
    previous_weight = 0.0

    for signal_date in index:
        signal_date = pd.Timestamp(signal_date)
        scores = (
            pd.to_numeric(signal_panel.loc[signal_date], errors="coerce")
            .replace([np.inf, -np.inf], np.nan)
            .dropna()
            if signal_date in signal_panel.index
            else pd.Series(dtype=float)
        )
        risk_on = bool(gate.get(signal_date, False))
        selected_rank: int | None = None
        selected_score: float | None = None

        if scores.empty or not risk_on:
            selected = None
        else:
            ranked = scores.sort_values(ascending=False, kind="mergesort").index.tolist()
            scheduled = ((signal_date - start).days % spec.rebalance_days) == phase_offset
            if selected is None:
                # Re-entry follows the already-confirmed risk gate.  The phase
                # offsets diversify ranking switches, but adding an extra
                # cash delay after risk-on has no external evidence and only
                # introduces implementation drag.
                selected = str(ranked[0])
            elif selected not in scores.index:
                # Strict point-in-time membership: never keep a holding after it
                # leaves the current Top20.
                selected = str(ranked[0])
            elif scheduled and selected not in ranked[: spec.hold_rank]:
                selected = str(ranked[0])

        if selected is None:
            desired_weight = 0.0
        elif not spec.use_volatility_target:
            desired_weight = 1.0
        else:
            assert volatility is not None
            desired_weight = _desired_exposure(
                volatility,
                signal_date,
                selected,
                target_volatility=spec.target_volatility,
            )
        event = selected != previous_asset or abs(desired_weight - previous_weight) > spec.weight_tolerance
        if event:
            assets.loc[signal_date] = selected if selected is not None else "__cash__"
            weights.loc[signal_date] = desired_weight
            previous_asset = selected
            previous_weight = desired_weight

        if selected is not None and not scores.empty and selected in scores.index:
            selected_rank = int(scores.index.get_loc(selected)) + 1
            selected_score = float(scores.loc[selected])
        history.append(
            {
                "signal_date": signal_date,
                "signal_name": signal_name,
                "phase_offset": phase_offset,
                "selected_asset": selected or "",
                "selected_rank": selected_rank,
                "selected_score": selected_score,
                "risk_on": risk_on,
                "target_weight": desired_weight,
                "event": event,
            }
        )

    return SleeveTargets(
        signal_name=signal_name,
        phase_offset=phase_offset,
        assets=assets,
        weights=weights,
        selection_history=pd.DataFrame(history),
    )


def aggregate_sleeve_targets(
    sleeve_targets: tuple[SleeveTargets, ...],
    columns: pd.Index,
) -> tuple[dict[pd.Timestamp, pd.Series], dict[pd.Timestamp, float], pd.DataFrame]:
    """Equal-weight sleeve targets into sparse portfolio target events."""
    if not sleeve_targets:
        return {}, {}, pd.DataFrame()

    event_dates = sorted(
        {
            pd.Timestamp(date)
            for sleeve in sleeve_targets
            for date in sleeve.assets.dropna().index
        }
    )
    if not event_dates:
        return {}, {}, pd.concat([sleeve.selection_history for sleeve in sleeve_targets], ignore_index=True)

    sleeve_count = float(len(sleeve_targets))
    targets: dict[pd.Timestamp, pd.Series] = {}
    exposures: dict[pd.Timestamp, float] = {}
    for signal_date in event_dates:
        total = pd.Series(0.0, index=columns, dtype=float)
        for sleeve in sleeve_targets:
            history = sleeve.assets.loc[:signal_date].dropna()
            if history.empty:
                continue
            last_date = history.index[-1]
            asset = str(history.iloc[-1])
            if asset in {"", "__cash__"}:
                continue
            weight = float(sleeve.weights.loc[last_date])
            if asset not in total.index or weight <= 0.0:
                continue
            total.loc[asset] += weight / sleeve_count
        positive = total[total > 0.0]
        targets[pd.Timestamp(signal_date)] = positive
        exposures[pd.Timestamp(signal_date)] = float(positive.sum())

    selection_history = pd.concat(
        [sleeve.selection_history for sleeve in sleeve_targets],
        ignore_index=True,
    )
    return targets, exposures, selection_history


def build_phase_momentum_targets(
    market: MarketDataBundle,
    universe: pd.DataFrame,
    index: pd.DatetimeIndex,
    *,
    signal_specs: tuple[MomentumSignalSpec, ...] = PRIMARY_SIGNAL_SPECS,
    spec: PhaseMomentumSpec | None = None,
    include_btc: bool = True,
) -> PhaseMomentumBuildResult:
    """Build all signal/phase sleeves and aggregate them into one portfolio."""
    spec = spec or PhaseMomentumSpec()
    sleeve_targets: list[SleeveTargets] = []
    for signal_spec in signal_specs:
        panel = build_signal_panel(market, universe, signal_spec, include_btc=include_btc)
        for offset in spec.phase_offsets:
            sleeve_targets.append(
                build_sleeve_targets(
                    market,
                    panel,
                    index,
                    spec,
                    signal_name=signal_spec.name,
                    phase_offset=offset,
                )
            )

    columns = market.returns.columns
    targets, exposures, history = aggregate_sleeve_targets(tuple(sleeve_targets), columns)
    return PhaseMomentumBuildResult(
        targets=targets,
        exposures=exposures,
        selection_history=history,
        sleeve_targets=tuple(sleeve_targets),
    )
