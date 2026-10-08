"""Intraday fill timing for daily backtests.

The production engine applies a target from signal date D to D+1's
close-to-close return, which means it fills at D's close.  Live orders can
only go out after the provider has published that close, hours into the next
UTC day.  This module measures the move between the prior close and the fill
hour from hourly candles, so a backtest can credit that part of the day to
the book it held before trading.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd


def load_hourly_bars(directory: Path) -> dict[str, pd.DataFrame]:
    """Hourly candles per coin, as listed in ``coverage.json``.

    ``scripts/download_hourly_prices.py`` writes one CSV per pair plus the
    manifest mapping each coin to its pair (and, for Gate.io candles, its
    file) and availability.  Unavailable coins are simply absent, and
    ``pre_fill_returns`` treats them as unobserved.
    """
    coverage = json.loads((directory / "coverage.json").read_text(encoding="utf-8"))
    bars: dict[str, pd.DataFrame] = {}
    for coin, info in coverage.items():
        if not info.get("available"):
            continue
        frame = pd.read_csv(directory / str(info.get("file", f"{info['pair']}.csv")))
        frame["open_time"] = pd.to_datetime(frame["open_time"], utc=True)
        bars[str(coin)] = frame
    return bars


MISSING_FILL_POLICIES = ("day_close", "prior_close")


def _candle_pre_fill(
    daily_returns: pd.DataFrame,
    hourly: dict[str, pd.DataFrame],
    *,
    fill_hours: int,
    reference_close: pd.DataFrame | None,
    max_open_gap: float,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """(pre-fill return, observed mask) measured from the candles alone."""
    pre_fill = pd.DataFrame(np.nan, index=daily_returns.index, columns=daily_returns.columns)
    observed = pd.DataFrame(False, index=daily_returns.index, columns=daily_returns.columns)
    day_start = pd.DatetimeIndex(daily_returns.index).tz_localize("UTC")
    fill_bar = day_start + pd.Timedelta(hours=fill_hours - 1)
    prior_close = None
    if reference_close is not None:
        prior_close = reference_close.reindex(index=daily_returns.index).shift(1)
    for coin in daily_returns.columns:
        bars = hourly.get(str(coin))
        if bars is None or bars.empty:
            continue
        times = pd.DatetimeIndex(pd.to_datetime(bars["open_time"], utc=True))
        opens = pd.Series(pd.to_numeric(bars["open"], errors="coerce").to_numpy(), index=times)
        closes = pd.Series(pd.to_numeric(bars["close"], errors="coerce").to_numpy(), index=times)
        start_price = opens.reindex(day_start).to_numpy(dtype=float)
        fill_price = closes.reindex(fill_bar).to_numpy(dtype=float)
        with np.errstate(divide="ignore", invalid="ignore"):
            pre = fill_price / start_price - 1.0
        daily = daily_returns[coin].to_numpy(dtype=float)
        valid = np.isfinite(pre) & (start_price > 0.0) & np.isfinite(daily)
        if prior_close is not None and coin in prior_close.columns:
            reference = prior_close[coin].to_numpy(dtype=float)
            with np.errstate(divide="ignore", invalid="ignore"):
                open_gap = np.abs(start_price / reference - 1.0)
            valid &= np.isfinite(open_gap) & (open_gap <= max_open_gap)
        pre_fill[coin] = pre
        observed[coin] = valid
    return pre_fill, observed


def observed_fill_mask(
    daily_returns: pd.DataFrame,
    hourly: dict[str, pd.DataFrame],
    *,
    fill_hours: int,
    reference_close: pd.DataFrame | None = None,
    max_open_gap: float = 0.05,
) -> pd.DataFrame:
    """True where the candles show the fill hour (see ``pre_fill_returns``)."""
    if not 0 <= fill_hours <= 24:
        raise ValueError("fill_hours must be within [0, 24]")
    if fill_hours == 0:
        return daily_returns.notna()
    return _candle_pre_fill(
        daily_returns,
        hourly,
        fill_hours=fill_hours,
        reference_close=reference_close,
        max_open_gap=max_open_gap,
    )[1]


def pre_fill_returns(
    daily_returns: pd.DataFrame,
    hourly: dict[str, pd.DataFrame],
    *,
    fill_hours: int,
    missing_fill: str = "day_close",
    reference_close: pd.DataFrame | None = None,
    max_open_gap: float = 0.05,
) -> pd.DataFrame:
    """Return from the prior daily close to the fill time, per date and coin.

    ``daily_returns`` holds close-to-close returns indexed by UTC date D (the
    close of D-1 to the close of D).  A signal taken at the close of D-1 is
    filled ``fill_hours`` into UTC day D, at the close of the hourly bar that
    opens at D + (fill_hours - 1) hours; the prior close is the open of the
    bar at D 00:00.  ``hourly`` maps a coin to bars with ``open_time`` (UTC),
    ``open`` and ``close`` columns.

    Where either candle is missing, the fill time is unobserved and has to be
    assumed.  The default ``missing_fill="day_close"`` lets the whole day pass
    before the fill (the pre-fill return equals the daily return);
    ``"prior_close"`` fills at the prior close, as the engine does without
    intraday timing.  Neither end is reliably conservative - a later fill
    helps or hurts depending on the path - so callers should run both and
    report the bracket.

    With ``reference_close`` (the panel's daily closes), a day whose hourly
    open is more than ``max_open_gap`` away from the panel's prior close is
    treated as unobserved: the candles then describe a different listing or a
    bad print, not the asset the daily returns measure.
    """
    if not 0 <= fill_hours <= 24:
        raise ValueError("fill_hours must be within [0, 24]")
    if missing_fill not in MISSING_FILL_POLICIES:
        raise ValueError(f"missing_fill must be one of {MISSING_FILL_POLICIES}, got {missing_fill!r}")
    result = daily_returns.astype(float).copy()
    if fill_hours == 0:
        return result.where(result.isna(), 0.0)
    if missing_fill == "prior_close":
        result = result.where(result.isna(), 0.0)
    pre_fill, observed = _candle_pre_fill(
        daily_returns.astype(float),
        hourly,
        fill_hours=fill_hours,
        reference_close=reference_close,
        max_open_gap=max_open_gap,
    )
    return result.mask(observed, pre_fill)
