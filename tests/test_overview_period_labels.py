"""Overview period labels must reflect the real last observation date.

`resample("ME")` labels a partial final period with the period end (e.g.
2026-09-30) even when the last observation is 2026-09-19. Presenting that
label as a data date overstates how current the data is.
"""

from __future__ import annotations

import pandas as pd

from atlas20.api.data_access.overview import _build_daily_returns, _build_equity_curve


def _series(values: list[float], dates: list[str]) -> pd.Series:
    return pd.Series(values, index=pd.to_datetime(dates), name="ALPHA")


def test_equity_curve_labels_partial_month_with_last_observation() -> None:
    series = _series(
        [100.0, 110.0, 120.0],
        ["2026-07-31", "2026-08-31", "2026-09-19"],
    )

    points = _build_equity_curve(series)

    assert points[-1]["date"] == "2026-09-19", "partial month must not be labelled 2026-09-30"
    assert points[-1]["value"] == 120.0


def test_equity_curve_keeps_complete_month_end_label() -> None:
    series = _series(
        [100.0, 110.0],
        ["2026-07-31", "2026-08-31"],
    )

    points = _build_equity_curve(series)

    assert points[-1]["date"] == "2026-08-31"


def test_daily_returns_labels_partial_month_with_last_observation() -> None:
    series = _series(
        [0.01, 0.02, 0.03],
        ["2026-07-31", "2026-08-31", "2026-09-19"],
    )

    points = _build_daily_returns(series)

    assert points[-1]["date"] == "2026-09-19"
