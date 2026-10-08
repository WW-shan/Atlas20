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
    stop_loss_kind: str = "none"
    stop_loss_pct: float = 0.30
    use_asset_trend_filter: bool = False
    asset_ma_window: int = 100
    # Opt-in rules of the 2026-10 pre-registered hypotheses
    # (docs/research/literature_review_2026-09.md, section 4).  The defaults
    # reproduce the champion exactly.
    #
    # H2: equal-weight ensemble of BTC moving-average gates.  Each window keeps
    # the champion's confirmation and fail-closed-after-warm-up rule; the gate
    # exposure g(D) is the share of gates that are on and multiplies the sleeve
    # weight.  ``btc_ma_window`` is ignored when this is set.
    btc_ma_windows: tuple[int, ...] | None = None
    # H4: coins held per sleeve.  ``hold_rank`` is the hold band; each coin gets
    # 1/N of the sleeve's capital times its own volatility scaling.
    holdings_per_sleeve: int = 1
    # H3: extra risk-on condition, Top20 breadth(D) >= threshold, where breadth
    # is the share of the day's Top20 above its own ``breadth_ma_window``-day
    # moving average (see ``top20_breadth``).
    breadth_threshold: float | None = None
    breadth_ma_window: int = 50
    # H5: cross-sectional dispersion overlay.  When set, every sleeve's weight
    # is multiplied by min(1, rolling ``dispersion_target_percentile`` of the
    # Top20 trailing-return dispersion / the current dispersion).  The
    # mechanism (dispersion predicts momentum breakdowns) is Makgolo and Zhang
    # (2026, SSRN 6648082); the construction mirrors volatility targeting.
    dispersion_target_percentile: float | None = None
    dispersion_window: int = 21
    dispersion_lookback: int = 252

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
        if self.stop_loss_kind not in {"none", "fixed", "trailing"}:
            raise ValueError("stop_loss_kind must be 'none', 'fixed', or 'trailing'")
        if not 0.0 < self.stop_loss_pct < 1.0:
            raise ValueError("stop_loss_pct must be in (0, 1)")
        if self.asset_ma_window < 2:
            raise ValueError("asset_ma_window must be at least 2")
        if self.btc_ma_windows is not None:
            windows = tuple(self.btc_ma_windows)
            if not windows:
                raise ValueError("btc_ma_windows must list at least one window")
            if any(int(window) != window or window < 2 for window in windows):
                raise ValueError("btc_ma_windows must be integers of at least 2")
            if len(set(windows)) != len(windows):
                raise ValueError("btc_ma_windows must not repeat a window")
            if not self.use_btc_gate:
                raise ValueError("btc_ma_windows requires use_btc_gate")
        if self.holdings_per_sleeve < 1:
            raise ValueError("holdings_per_sleeve must be at least 1")
        if self.holdings_per_sleeve > 1:
            if self.hold_rank < self.holdings_per_sleeve:
                raise ValueError("hold_rank must be at least holdings_per_sleeve")
            if self.stop_loss_kind != "none" or self.use_asset_trend_filter:
                raise ValueError(
                    "multi-asset sleeves support neither stop-losses nor the asset trend filter"
                )
        if self.breadth_threshold is not None and not 0.0 < self.breadth_threshold <= 1.0:
            raise ValueError("breadth_threshold must be in (0, 1]")
        if self.breadth_ma_window < 2:
            raise ValueError("breadth_ma_window must be at least 2")
        if self.dispersion_target_percentile is not None and not (
            0.0 < self.dispersion_target_percentile <= 1.0
        ):
            raise ValueError("dispersion_target_percentile must be in (0, 1]")
        if self.dispersion_window < 2:
            raise ValueError("dispersion_window must be at least 2")
        if self.dispersion_lookback < 2:
            raise ValueError("dispersion_lookback must be at least 2")


CORE_PARAMETER_SPECS: tuple[PhaseMomentumSpec, ...] = (
    PhaseMomentumSpec(),
    PhaseMomentumSpec(rebalance_days=1, phase_offsets=(0,)),
    PhaseMomentumSpec(rebalance_days=2, phase_offsets=(0, 1)),
    PhaseMomentumSpec(rebalance_days=5, phase_offsets=(0, 1, 2, 3, 4)),
    PhaseMomentumSpec(hold_rank=1),
    PhaseMomentumSpec(hold_rank=3),
    PhaseMomentumSpec(target_volatility=0.60),
    PhaseMomentumSpec(target_volatility=0.70),
    PhaseMomentumSpec(target_volatility=0.90),
    PhaseMomentumSpec(target_volatility=1.00),
    PhaseMomentumSpec(btc_ma_window=50),
    PhaseMomentumSpec(btc_ma_window=150),
    PhaseMomentumSpec(btc_ma_window=200),
)


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
    """Sparse target events for one signal/phase sleeve.

    A single-asset sleeve names its coin (or ``"__cash__"``) in ``assets`` and
    the coin's share of the sleeve's capital in ``weights``.  A multi-asset
    sleeve (``holdings_per_sleeve > 1``) marks its events with ``"__multi__"``
    (or ``"__cash__"``), puts its total exposure in ``weights`` and the coins
    in ``holdings``: one ``{coin: share of the sleeve's capital}`` mapping per
    event date.
    """

    signal_name: str
    phase_offset: int
    assets: pd.Series
    weights: pd.Series
    selection_history: pd.DataFrame
    holdings: pd.Series | None = None


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
        return 0.0
    daily_vol = float(volatility.at[signal_date, asset])
    if not np.isfinite(daily_vol):
        # A position whose risk cannot be measured is not sized: fail closed.
        return 0.0
    if daily_vol <= 0.0:
        return 1.0
    # realized_volatility returns annualized volatility.  A target below the
    # realized level reduces exposure; a target above it never creates leverage.
    return min(1.0, float(target_volatility) / daily_vol)


def top20_breadth(
    market: MarketDataBundle,
    universe: pd.DataFrame,
    index: pd.DatetimeIndex,
    *,
    ma_window: int = 50,
) -> pd.Series:
    """Share of each day's point-in-time Top20 above its own moving average.

    Copied verbatim from ``_breadth_signal`` in
    ``scripts/run_momentum_event_breadth_overlay.py`` (the RESEARCH.md
    section 0.8 study that H3 re-tests) so the strategy package does not import
    a research script; ``tests/test_phase_momentum_hypotheses.py`` checks that
    the two agree.  A coin without ``ma_window`` days of prices counts as not
    above its average.
    """
    if ma_window < 2:
        raise ValueError("ma_window must be at least 2")
    moving_average = market.price.rolling(ma_window, min_periods=ma_window).mean()
    above = market.price > moving_average
    by_date = {pd.Timestamp(date): group for date, group in universe.groupby("rebalance_date")}
    values: dict[pd.Timestamp, float] = {}
    for date in index:
        snapshot = by_date.get(pd.Timestamp(date))
        if snapshot is None or snapshot.empty:
            values[pd.Timestamp(date)] = float("nan")
            continue
        coin_ids = snapshot["coin_id"].astype(str).tolist()
        usable = above.loc[pd.Timestamp(date), coin_ids].dropna()
        values[pd.Timestamp(date)] = float(usable.mean()) if not usable.empty else float("nan")
    return pd.Series(values, dtype=float).sort_index()


def top20_dispersion(
    market: MarketDataBundle,
    universe: pd.DataFrame,
    index: pd.DatetimeIndex,
    *,
    window: int = 21,
) -> pd.Series:
    """Cross-sectional std of the point-in-time Top20's trailing ``window``-day returns.

    The dispersion of crypto returns across coins predicts momentum
    breakdowns (Makgolo and Zhang, 2026, SSRN 6648082); this is the series the
    H5 overlay scales exposure by.  A day with fewer than five usable members
    has no dispersion reading.
    """
    if window < 2:
        raise ValueError("window must be at least 2")
    trailing = market.price / market.price.shift(window) - 1.0
    by_date = {pd.Timestamp(date): group for date, group in universe.groupby("rebalance_date")}
    values: dict[pd.Timestamp, float] = {}
    for date in index:
        snapshot = by_date.get(pd.Timestamp(date))
        if snapshot is None or snapshot.empty:
            values[pd.Timestamp(date)] = float("nan")
            continue
        coin_ids = snapshot["coin_id"].astype(str).tolist()
        row = (
            pd.to_numeric(trailing.loc[pd.Timestamp(date), coin_ids], errors="coerce")
            .replace([np.inf, -np.inf], np.nan)
            .dropna()
        )
        values[pd.Timestamp(date)] = float(row.std(ddof=1)) if len(row) >= 5 else float("nan")
    return pd.Series(values, dtype=float).sort_index()


def dispersion_exposure(
    dispersion: pd.Series,
    *,
    percentile: float = 0.75,
    lookback: int = 252,
    min_periods: int | None = None,
) -> pd.Series:
    """Exposure multiplier ``min(1, rolling Pxx(dispersion) / dispersion(D))``.

    Analogous to volatility targeting: scale the book down when dispersion is
    above its recent ``percentile`` and leave it at 1 otherwise (gross exposure
    is capped at 1, so the overlay can only de-risk).  A missing or non-positive
    reading leaves the multiplier at 1 (no overlay) rather than forcing cash.
    """
    if not 0.0 < percentile <= 1.0:
        raise ValueError("percentile must be in (0, 1]")
    if lookback < 2:
        raise ValueError("lookback must be at least 2")
    if min_periods is None:
        min_periods = max(2, lookback // 2)
    series = pd.to_numeric(dispersion, errors="coerce").replace([np.inf, -np.inf], np.nan)
    target = series.rolling(lookback, min_periods=min_periods).quantile(percentile)
    with np.errstate(divide="ignore", invalid="ignore"):
        multiplier = target / series.where(series > 0.0)
    return multiplier.clip(upper=1.0).fillna(1.0)


def _risk_gate(
    market: MarketDataBundle,
    index: pd.DatetimeIndex,
    spec: PhaseMomentumSpec,
    breadth: pd.Series | None,
) -> tuple[pd.Series, pd.Series | None]:
    """Risk-on state per date and, for a gate ensemble (H2), the exposure g(D)."""
    gate_exposure: pd.Series | None = None
    if spec.use_btc_gate and spec.btc_ma_windows is not None:
        confirmed = [
            btc_above_moving_average(
                market.price,
                ma_window=int(window),
                confirm_days=spec.btc_confirm_days,
            )
            .reindex(index)
            .fillna(False)
            .astype(bool)
            for window in spec.btc_ma_windows
        ]
        on_count = sum((state.astype(float) for state in confirmed), pd.Series(0.0, index=index))
        gate_exposure = on_count / float(len(confirmed))
        gate = gate_exposure > 0.0
    elif spec.use_btc_gate:
        gate = btc_above_moving_average(
            market.price,
            ma_window=spec.btc_ma_window,
            confirm_days=spec.btc_confirm_days,
        ).reindex(index).fillna(False)
    else:
        gate = pd.Series(True, index=index, dtype=bool)
    if spec.breadth_threshold is not None:
        if breadth is None:
            raise ValueError("breadth_threshold needs the Top20 breadth series (see top20_breadth)")
        # A day without a breadth reading fails the condition (NaN >= x is False).
        condition = pd.to_numeric(breadth, errors="coerce").reindex(index) >= float(spec.breadth_threshold)
        gate = gate.astype(bool) & condition
        if gate_exposure is not None:
            gate_exposure = gate_exposure.where(condition, 0.0)
    return gate, gate_exposure


def _build_multi_asset_sleeve_targets(
    signal_panel: pd.DataFrame,
    index: pd.DatetimeIndex,
    spec: PhaseMomentumSpec,
    *,
    signal_name: str,
    phase_offset: int,
    gate: pd.Series,
    gate_exposure: pd.Series | None,
    breadth: pd.Series | None,
    volatility: pd.DataFrame | None,
    dispersion_multiplier: pd.Series | None = None,
) -> SleeveTargets:
    """H4: hold the top ``holdings_per_sleeve`` coins of one signal and phase.

    Incumbents are kept while they rank inside ``hold_rank`` at a scheduled
    check.  A holding that leaves the day's Top20 (no score today) is sold at
    once.  Empty slots - at entry, after a risk-off reset or after an exit -
    are filled at once from the best-ranked coins not already held, as the
    champion fills an empty sleeve.  Each coin gets 1/N of the sleeve's
    capital times min(1, target / its realized volatility); the champion's
    weight tolerance applies to each coin's share of the sleeve's capital.
    """
    count = spec.holdings_per_sleeve
    start = pd.Timestamp(index[0]).normalize()
    assets = pd.Series(pd.NA, index=index, dtype="object")
    weights = pd.Series(np.nan, index=index, dtype=float)
    event_holdings: dict[pd.Timestamp, dict[str, float]] = {}
    history: list[dict[str, object]] = []
    held: list[str] = []
    previous: dict[str, float] = {}

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
        ranked: list[str] = []
        scheduled = ((signal_date - start).days % spec.rebalance_days) == phase_offset
        if scores.empty or not risk_on:
            held = []
        else:
            ranked = [str(asset) for asset in scores.sort_values(ascending=False, kind="mergesort").index]
            # Strict point-in-time membership: sold the day it leaves the Top20.
            held = [asset for asset in held if asset in scores.index]
            if scheduled:
                band = set(ranked[: spec.hold_rank])
                held = [asset for asset in held if asset in band]
            for asset in ranked:
                if len(held) >= count:
                    break
                if asset not in held:
                    held.append(asset)

        scale = 1.0 if gate_exposure is None else float(gate_exposure.get(signal_date, 0.0))
        if dispersion_multiplier is not None:
            factor = float(dispersion_multiplier.get(signal_date, 1.0))
            scale *= factor if np.isfinite(factor) else 1.0
        desired: dict[str, float] = {}
        for asset in held:
            if not spec.use_volatility_target:
                exposure = 1.0
            else:
                assert volatility is not None
                exposure = _desired_exposure(
                    volatility,
                    signal_date,
                    asset,
                    target_volatility=spec.target_volatility,
                )
            desired[asset] = exposure * scale / count
        event = set(desired) != set(previous) or any(
            abs(desired[asset] - previous[asset]) > spec.weight_tolerance for asset in desired
        )
        if event:
            assets.loc[signal_date] = "__multi__" if desired else "__cash__"
            weights.loc[signal_date] = float(sum(desired.values()))
            event_holdings[signal_date] = dict(desired)
            previous = dict(desired)

        row: dict[str, object] = {
            "signal_date": signal_date,
            "signal_name": signal_name,
            "phase_offset": phase_offset,
            "selected_asset": "|".join(held),
            "selected_rank": None,
            "selected_score": None,
            "risk_on": risk_on,
            "target_weight": float(sum(desired.values())),
            "event": event,
            "selected_ranks": "|".join(str(ranked.index(asset) + 1) for asset in held if asset in ranked),
        }
        if gate_exposure is not None:
            row["gate_exposure"] = float(gate_exposure.get(signal_date, 0.0))
        if breadth is not None and spec.breadth_threshold is not None:
            row["breadth"] = float(pd.to_numeric(breadth, errors="coerce").get(signal_date, np.nan))
        if dispersion_multiplier is not None:
            row["dispersion_multiplier"] = float(dispersion_multiplier.get(signal_date, 1.0))
        history.append(row)

    holdings = pd.Series(
        list(event_holdings.values()),
        index=pd.DatetimeIndex(list(event_holdings.keys())),
        dtype="object",
    )
    return SleeveTargets(
        signal_name=signal_name,
        phase_offset=phase_offset,
        assets=assets,
        weights=weights,
        selection_history=pd.DataFrame(history),
        holdings=holdings,
    )


def build_sleeve_targets(
    market: MarketDataBundle,
    signal_panel: pd.DataFrame,
    index: pd.DatetimeIndex,
    spec: PhaseMomentumSpec,
    *,
    signal_name: str,
    phase_offset: int,
    breadth: pd.Series | None = None,
    dispersion_multiplier: pd.Series | None = None,
) -> SleeveTargets:
    """Build sparse target events for one signal and one phase offset.

    ``breadth`` (from ``top20_breadth``) is required when the spec sets
    ``breadth_threshold`` and ignored otherwise.  ``dispersion_multiplier``
    (from ``dispersion_exposure``) scales every sleeve weight when the spec
    sets ``dispersion_target_percentile`` and is ignored otherwise.
    """
    if phase_offset not in spec.phase_offsets:
        raise ValueError("phase_offset must be present in spec.phase_offsets")
    if spec.breadth_threshold is not None and breadth is None:
        raise ValueError("breadth_threshold needs the Top20 breadth series (see top20_breadth)")
    if index.empty:
        empty = pd.Series(dtype=float)
        return SleeveTargets(signal_name, phase_offset, empty, empty, pd.DataFrame())

    start = pd.Timestamp(index[0]).normalize()
    gate, gate_exposure = _risk_gate(market, index, spec, breadth)
    volatility = (
        realized_volatility(market.price, window=spec.vol_window).reindex(index)
        if spec.use_volatility_target
        else None
    )
    if spec.holdings_per_sleeve > 1:
        return _build_multi_asset_sleeve_targets(
            signal_panel,
            index,
            spec,
            signal_name=signal_name,
            phase_offset=phase_offset,
            gate=gate,
            gate_exposure=gate_exposure,
            breadth=breadth,
            volatility=volatility,
            dispersion_multiplier=dispersion_multiplier,
        )
    if spec.use_asset_trend_filter:
        asset_ma = market.price.rolling(
            spec.asset_ma_window,
            min_periods=spec.asset_ma_window,
        ).mean()
        asset_trend = (market.price > asset_ma).reindex(index, fill_value=False).astype(bool)
    else:
        asset_trend = None
    assets = pd.Series(pd.NA, index=index, dtype="object")
    weights = pd.Series(np.nan, index=index, dtype=float)
    history: list[dict[str, object]] = []
    selected: str | None = None
    previous_asset: str | None = None
    previous_weight = 0.0
    stop_active = False
    tracked_asset: str | None = None
    entry_price: float | None = None
    high_watermark: float | None = None

    def _price(asset: str, date: pd.Timestamp) -> float | None:
        if asset not in market.price.columns or date not in market.price.index:
            return None
        value = float(market.price.at[date, asset])
        return value if np.isfinite(value) and value > 0.0 else None

    for signal_date in index:
        signal_date = pd.Timestamp(signal_date)
        stopped_today = False
        scores = (
            pd.to_numeric(signal_panel.loc[signal_date], errors="coerce")
            .replace([np.inf, -np.inf], np.nan)
            .dropna()
            if signal_date in signal_panel.index
            else pd.Series(dtype=float)
        )
        risk_on = bool(gate.get(signal_date, False))
        ranked: list[str] = []
        selected_rank: int | None = None
        selected_score: float | None = None

        scheduled = ((signal_date - start).days % spec.rebalance_days) == phase_offset
        if scores.empty or not risk_on:
            selected = None
            stop_active = False
            tracked_asset = None
            entry_price = None
            high_watermark = None
        else:
            ranked = scores.sort_values(ascending=False, kind="mergesort").index.tolist()
            if asset_trend is not None and signal_date in asset_trend.index:
                eligible = asset_trend.loc[signal_date].reindex(ranked).fillna(False).astype(bool)
                ranked = [asset for asset in ranked if bool(eligible.get(asset, False))]

            # Stop-loss evaluation happens before selection changes, using the
            # current close.  The resulting target is still executed T+1 by
            # the production engine.  A stopped-out sleeve waits until its next
            # scheduled check before re-entering, otherwise the stop would be
            # immediately reversed on the following day.
            if selected is not None and spec.stop_loss_kind != "none":
                current_price = _price(selected, signal_date)
                if current_price is not None:
                    if tracked_asset != selected:
                        tracked_asset = selected
                        entry_price = current_price
                        high_watermark = current_price
                    else:
                        if high_watermark is None or current_price > high_watermark:
                            high_watermark = current_price
                    reference = entry_price if spec.stop_loss_kind == "fixed" else high_watermark
                    if reference is not None and current_price <= reference * (1.0 - spec.stop_loss_pct):
                        selected = None
                        stop_active = True
                        stopped_today = True
                        tracked_asset = None
                        entry_price = None
                        high_watermark = None

            if selected is not None and (
                selected not in scores.index
                or (
                    asset_trend is not None
                    # Row lookup: ``DataFrame.get(date)`` would look up a
                    # column and always report the holding as below trend.
                    and not bool(asset_trend.loc[signal_date].get(selected, False))
                )
            ):
                # Strict point-in-time membership and absolute-trend exit.
                selected = None
                tracked_asset = None
                entry_price = None
                high_watermark = None

            if not ranked:
                selected = None

            if selected is None:
                if not ranked:
                    pass
                elif stop_active:
                    if scheduled and not stopped_today:
                        stop_active = False
                        selected = str(ranked[0])
                else:
                    # Re-entry follows the already-confirmed risk gate.  The
                    # phase offsets diversify ranking switches, but adding an
                    # extra cash delay after risk-on has no external evidence.
                    selected = str(ranked[0])
            elif scheduled and selected not in ranked[: spec.hold_rank]:
                selected = str(ranked[0])
                tracked_asset = None
                entry_price = None
                high_watermark = None

            if selected is not None and tracked_asset != selected:
                tracked_asset = selected
                entry_price = _price(selected, signal_date)
                high_watermark = entry_price

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
        if gate_exposure is not None:
            # H2: the sleeve holds g(D) of its volatility-scaled weight.
            desired_weight *= float(gate_exposure.get(signal_date, 0.0))
        if dispersion_multiplier is not None:
            # H5: scale by the point-in-time dispersion-targeting factor.
            factor = float(dispersion_multiplier.get(signal_date, 1.0))
            desired_weight *= factor if np.isfinite(factor) else 1.0
        event = selected != previous_asset or abs(desired_weight - previous_weight) > spec.weight_tolerance
        if event:
            assets.loc[signal_date] = selected if selected is not None else "__cash__"
            weights.loc[signal_date] = desired_weight
            previous_asset = selected
            previous_weight = desired_weight

        if selected is not None and selected in ranked:
            # Rank within the score ordering the hold rule compares against
            # (after the optional absolute-trend filter), not the column order
            # of the signal panel.
            selected_rank = ranked.index(selected) + 1
            selected_score = float(scores.loc[selected])
        row: dict[str, object] = {
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
        # Opt-in audit columns; the champion's history keeps its columns.
        if gate_exposure is not None:
            row["gate_exposure"] = float(gate_exposure.get(signal_date, 0.0))
        if breadth is not None and spec.breadth_threshold is not None:
            row["breadth"] = float(pd.to_numeric(breadth, errors="coerce").get(signal_date, np.nan))
        if dispersion_multiplier is not None:
            row["dispersion_multiplier"] = float(dispersion_multiplier.get(signal_date, 1.0))
        history.append(row)

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
    sleeve_weights: tuple[float, ...] | None = None,
) -> tuple[dict[pd.Timestamp, pd.Series], dict[pd.Timestamp, float], pd.DataFrame]:
    """Combine sleeve targets into sparse portfolio target events.

    Sleeves are equal-weighted unless ``sleeve_weights`` gives one weight per
    sleeve (summing to at most 1.0, so gross exposure stays <= 1.0).
    """
    if not sleeve_targets:
        return {}, {}, pd.DataFrame()
    if sleeve_weights is None:
        sleeve_weights = tuple(1.0 / len(sleeve_targets) for _ in sleeve_targets)
    if len(sleeve_weights) != len(sleeve_targets):
        raise ValueError("sleeve_weights must have one weight per sleeve")
    if any(weight < 0.0 for weight in sleeve_weights) or sum(sleeve_weights) > 1.0 + 1e-12:
        raise ValueError("sleeve_weights must be non-negative and sum to at most 1.0")

    event_dates = sorted(
        {
            pd.Timestamp(date)
            for sleeve in sleeve_targets
            for date in sleeve.assets.dropna().index
        }
    )
    if not event_dates:
        return {}, {}, pd.concat([sleeve.selection_history for sleeve in sleeve_targets], ignore_index=True)

    targets: dict[pd.Timestamp, pd.Series] = {}
    exposures: dict[pd.Timestamp, float] = {}
    for signal_date in event_dates:
        total = pd.Series(0.0, index=columns, dtype=float)
        for sleeve, sleeve_weight in zip(sleeve_targets, sleeve_weights):
            history = sleeve.assets.loc[:signal_date].dropna()
            if history.empty:
                continue
            last_date = history.index[-1]
            if sleeve.holdings is not None:
                # Multi-asset sleeve: every coin of its latest event.
                for asset, weight in dict(sleeve.holdings.loc[last_date]).items():
                    if asset in total.index and float(weight) > 0.0:
                        total.loc[asset] += float(weight) * float(sleeve_weight)
                continue
            asset = str(history.iloc[-1])
            if asset in {"", "__cash__"}:
                continue
            weight = float(sleeve.weights.loc[last_date])
            if asset not in total.index or weight <= 0.0:
                continue
            total.loc[asset] += weight * float(sleeve_weight)
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
    breadth = (
        top20_breadth(market, universe, index, ma_window=spec.breadth_ma_window)
        if spec.breadth_threshold is not None
        else None
    )
    dispersion_multiplier = (
        dispersion_exposure(
            top20_dispersion(market, universe, index, window=spec.dispersion_window),
            percentile=spec.dispersion_target_percentile,
            lookback=spec.dispersion_lookback,
        )
        if spec.dispersion_target_percentile is not None
        else None
    )
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
                    breadth=breadth,
                    dispersion_multiplier=dispersion_multiplier,
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


def parameter_ensemble_sleeve_weights(
    parameter_specs: tuple[PhaseMomentumSpec, ...],
    *,
    signal_count: int,
) -> tuple[float, ...]:
    """Per-sleeve weights that give every parameter set the same share.

    Sleeves are built spec by spec, signal by signal, phase by phase.  A spec
    with five phase offsets must not carry five times the weight of a spec
    with one, so each sleeve gets 1 / (specs x signals x that spec's phases).
    """
    if not parameter_specs or signal_count < 1:
        raise ValueError("at least one parameter specification and one signal are required")
    weights: list[float] = []
    for spec in parameter_specs:
        per_sleeve = 1.0 / (len(parameter_specs) * signal_count * len(spec.phase_offsets))
        weights.extend([per_sleeve] * (signal_count * len(spec.phase_offsets)))
    return tuple(weights)


def build_parameter_ensemble_targets(
    market: MarketDataBundle,
    universe: pd.DataFrame,
    index: pd.DatetimeIndex,
    *,
    parameter_specs: tuple[PhaseMomentumSpec, ...] = CORE_PARAMETER_SPECS,
    signal_specs: tuple[MomentumSignalSpec, ...] = PRIMARY_SIGNAL_SPECS,
    include_btc: bool = True,
) -> PhaseMomentumBuildResult:
    """Equal-weight a fixed parameter grid, each set run as its own ensemble.

    The grid is defined before looking at the walk-forward results.  Every
    parameter set gets the same share of the book however many phase sleeves
    it has.  Combining all sleeves at the target level is implementable as one
    portfolio and avoids selecting the single best full-sample parameter set.
    The same construction blends pre-registered books (H3: the champion and
    the champion with the breadth condition, 50/50): the production engine
    then rebalances toward the mix at every target event and charges it.
    """
    if not parameter_specs:
        raise ValueError("at least one parameter specification is required")
    signal_panels = {
        signal_spec.name: build_signal_panel(
            market,
            universe,
            signal_spec,
            include_btc=include_btc,
        )
        for signal_spec in signal_specs
    }
    breadth_by_window = {
        spec.breadth_ma_window: top20_breadth(market, universe, index, ma_window=spec.breadth_ma_window)
        for spec in parameter_specs
        if spec.breadth_threshold is not None
    }
    dispersion_cache: dict[tuple[int, float, int], pd.Series] = {}
    dispersion_by_spec: dict[int, pd.Series | None] = {}
    for position, spec in enumerate(parameter_specs):
        if spec.dispersion_target_percentile is None:
            dispersion_by_spec[position] = None
            continue
        key = (spec.dispersion_window, spec.dispersion_target_percentile, spec.dispersion_lookback)
        if key not in dispersion_cache:
            dispersion_cache[key] = dispersion_exposure(
                top20_dispersion(market, universe, index, window=spec.dispersion_window),
                percentile=spec.dispersion_target_percentile,
                lookback=spec.dispersion_lookback,
            )
        dispersion_by_spec[position] = dispersion_cache[key]
    sleeve_targets: list[SleeveTargets] = []
    for position, spec in enumerate(parameter_specs):
        for signal_spec in signal_specs:
            panel = signal_panels[signal_spec.name]
            for offset in spec.phase_offsets:
                sleeve_targets.append(
                    build_sleeve_targets(
                        market,
                        panel,
                        index,
                        spec,
                        signal_name=signal_spec.name,
                        phase_offset=offset,
                        breadth=breadth_by_window.get(spec.breadth_ma_window)
                        if spec.breadth_threshold is not None
                        else None,
                        dispersion_multiplier=dispersion_by_spec[position],
                    )
                )

    columns = market.returns.columns
    targets, exposures, history = aggregate_sleeve_targets(
        tuple(sleeve_targets),
        columns,
        sleeve_weights=parameter_ensemble_sleeve_weights(
            parameter_specs,
            signal_count=len(signal_specs),
        ),
    )
    return PhaseMomentumBuildResult(
        targets=targets,
        exposures=exposures,
        selection_history=history,
        sleeve_targets=tuple(sleeve_targets),
    )
