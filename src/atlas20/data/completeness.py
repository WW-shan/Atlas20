"""Is the newest panel day a finished provider day?

CoinMarketCap publishes a day's candles asset by asset and finalizes them some
time after 00:00 UTC. The processor drops a newest day only when too few
*assets* have it (``data_quality.min_daily_coverage``). A day every asset has,
but only partially - every volume at 30-50% because the provider had not
finalized it - passes that gate untouched, and it moves the Top 20 through the
liquidity gate: scaling the 2026-09-23 panel that way drops Monero and admits
Bittensor. This module compares the last day with the trailing week and
refuses a day that looks partial, so the audit and, later, the live-signal
script can both ask before trading on it.

Calibration (``data/processed/panel_daily.csv``, 2,078 real days from
2021-01-15 to 2026-09-23; partial days simulated by scaling each asset's
volume by U(0.3, 0.5)):

* The per-asset ratio ``last-day volume / trailing-7-day median`` has a
  strong weekend effect: its cross-asset median never fell below 0.517 on a
  weekday but reached 0.438 on a Saturday (2025-10-18). A single floor is
  therefore either blind on weekdays or noisy on weekends.
* Weekday floor 0.60 and weekend floor 0.43 catch ~92% of simulated partial
  days. They would have refused 4 real days: 2022-05-16/17 (the LUNA
  collapse), 2022-11-15 (FTX) and 2024-12-25.
* The motivating case - the 2026-09-23 panel (a Wednesday that traded 1.38x
  its trailing median) scaled to 30-50% - lands at a median of 0.52-0.60x,
  right at the weekday floor: 49 of 50 end-to-end draws are refused. Those
  draws do move the Top 20 (seed 0: Monero and Toncoin out, Shiba Inu and
  Sui in).
* The share of trailing-week-live assets that still carry a market cap on
  the next day never fell below 97.2%; the floor is 95%.

A partial day that follows an unusually heavy day can still clear the volume
floor (a 2x day scaled to 40% looks like an ordinary day), so this is a
guard against a uniformly unfinished day, not proof that a day is final.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

TRAILING_DAYS = 7
# Cross-asset median of last-day volume / trailing-7-day median volume.
WEEKDAY_VOLUME_FLOOR = 0.60
WEEKEND_VOLUME_FLOOR = 0.43
MIN_MARKET_CAP_COVERAGE = 0.95
# Below this many assets with a full trailing week the median means little.
MIN_ASSETS = 10
# Reported per asset, not decisive on its own.
LOW_VOLUME_RATIO = 0.60


@dataclass(frozen=True)
class LastDayCompleteness:
    """The verdict on the panel's newest day, with the evidence behind it."""

    date: pd.Timestamp | None
    complete: bool
    assets: int
    median_volume_ratio: float
    low_volume_share: float
    market_cap_coverage: float
    volume_floor: float
    reasons: tuple[str, ...]
    low_volume_assets: tuple[str, ...]

    def describe(self) -> str:
        day = self.date.date().isoformat() if self.date is not None else "none"
        text = (
            f"last day {day}: {self.assets} asset(s) with a full trailing {TRAILING_DAYS}-day week; "
            f"volume vs trailing median: median {self.median_volume_ratio:.2f}x (floor {self.volume_floor:.2f}x), "
            f"{self.low_volume_share:.0%} of assets below {LOW_VOLUME_RATIO:.2f}x; "
            f"market-cap coverage {self.market_cap_coverage:.1%} (floor {MIN_MARKET_CAP_COVERAGE:.0%})"
        )
        if self.reasons:
            text += "; PARTIAL: " + "; ".join(self.reasons)
            if self.low_volume_assets:
                text += f" (e.g. {', '.join(self.low_volume_assets)})"
        return text


def _incomplete(date: pd.Timestamp | None, reason: str, floor: float = float("nan")) -> LastDayCompleteness:
    return LastDayCompleteness(date, False, 0, float("nan"), float("nan"), float("nan"), floor, (reason,), ())


def assess_last_day(
    panel: pd.DataFrame,
    *,
    trailing_days: int = TRAILING_DAYS,
    weekday_volume_floor: float = WEEKDAY_VOLUME_FLOOR,
    weekend_volume_floor: float = WEEKEND_VOLUME_FLOOR,
    min_market_cap_coverage: float = MIN_MARKET_CAP_COVERAGE,
    min_assets: int = MIN_ASSETS,
) -> LastDayCompleteness:
    """Judge whether the newest day of a long panel is a finished provider day.

    ``panel`` needs ``date``, ``coin_id``, ``volume_usd`` and ``market_cap``
    (the persisted ``panel_daily.csv`` layout; string dates are fine). Only
    assets that traded and carried a market cap on *every* one of the
    trailing days are scored - a new listing or an ended feed has no baseline.
    A scored asset that is missing on the last day counts as zero volume and
    no market cap, so a vanished row cannot make the day look healthier.
    """
    if panel.empty:
        return _incomplete(None, "cannot assess: the panel is empty")
    frame = panel[["date", "coin_id", "volume_usd", "market_cap"]].copy()
    frame["date"] = pd.to_datetime(frame["date"]).dt.normalize()
    frame["volume_usd"] = pd.to_numeric(frame["volume_usd"], errors="coerce")
    frame["market_cap"] = pd.to_numeric(frame["market_cap"], errors="coerce")
    last_day = pd.Timestamp(frame["date"].max())
    floor = weekend_volume_floor if last_day.dayofweek >= 5 else weekday_volume_floor

    window = pd.date_range(end=last_day, periods=trailing_days + 1, freq="D")
    frame = frame[frame["date"].isin(window)].drop_duplicates(["date", "coin_id"], keep="last")
    volume = frame.pivot(index="date", columns="coin_id", values="volume_usd").reindex(window)
    market_cap = frame.pivot(index="date", columns="coin_id", values="market_cap").reindex(window)

    trailing_volume = volume.iloc[:-1]
    trailing_cap = market_cap.iloc[:-1]
    live = (trailing_volume > 0).all() & (trailing_cap > 0).all()
    assets = int(live.sum())
    if assets < min_assets:
        return _incomplete(
            last_day,
            f"cannot assess: only {assets} asset(s) traded with a market cap on each of the "
            f"{trailing_days} trailing days (need {min_assets})",
            floor,
        )

    baseline = trailing_volume.loc[:, live].median()
    last_volume = volume.iloc[-1][live].fillna(0.0).clip(lower=0.0)
    ratio = last_volume / baseline
    median_ratio = float(ratio.median())
    low = ratio[ratio < LOW_VOLUME_RATIO].sort_values()
    coverage = float((market_cap.iloc[-1][live] > 0).mean())

    reasons: list[str] = []
    if median_ratio < floor:
        kind = "weekend" if last_day.dayofweek >= 5 else "weekday"
        reasons.append(
            f"median last-day volume is {median_ratio:.2f}x the trailing {trailing_days}-day median, "
            f"below the {kind} floor {floor:.2f}x"
        )
    if coverage < min_market_cap_coverage:
        missing = int(assets - round(coverage * assets))
        reasons.append(
            f"{missing} of {assets} asset(s) that carried a market cap all week have none on the last day "
            f"({coverage:.1%} < {min_market_cap_coverage:.0%})"
        )
    return LastDayCompleteness(
        date=last_day,
        complete=not reasons,
        assets=assets,
        median_volume_ratio=median_ratio,
        low_volume_share=float(len(low) / assets),
        market_cap_coverage=coverage,
        volume_floor=floor,
        reasons=tuple(reasons),
        low_volume_assets=tuple(f"{coin} {value:.2f}x" for coin, value in low.head(5).items()),
    )


__all__ = [
    "LastDayCompleteness",
    "MIN_MARKET_CAP_COVERAGE",
    "TRAILING_DAYS",
    "WEEKDAY_VOLUME_FLOOR",
    "WEEKEND_VOLUME_FLOOR",
    "assess_last_day",
]
