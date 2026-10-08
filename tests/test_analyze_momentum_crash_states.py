from __future__ import annotations

import pandas as pd
import pytest

from scripts.analyze_momentum_crash_states import (
    STATE_COLUMNS,
    monthly_state_frame,
    separate_crashes,
)


def _daily() -> tuple[pd.Series, pd.DataFrame]:
    index = pd.date_range("2024-01-01", periods=120, freq="D")
    # Months 1 and 2 lose 10%, months 3 and 4 gain 5%; the losing months carry a
    # deliberately higher gate_open and a lower disp_ratio.
    port = pd.Series(0.0, index=index)
    for start, end, daily in (
        ("2024-01-01", "2024-01-31", -0.0035),
        ("2024-02-01", "2024-02-29", -0.0035),
        ("2024-03-01", "2024-03-31", 0.0016),
        ("2024-04-01", "2024-04-30", 0.0016),
    ):
        port.loc[start:end] = daily
    state = pd.DataFrame(
        {
            "gate": 0.0,
            "breadth": 0.5,
            "disp_ratio": 1.0,
            "mkt_vol": 0.6,
            "own63": 0.1,
            "gross": 0.3,
        },
        index=index,
    )
    state.loc["2024-01-01":"2024-02-29", "gate"] = 1.0
    state.loc["2024-01-01":"2024-02-29", "disp_ratio"] = 0.5
    return port, state


def test_monthly_state_frame_reads_crowding_at_the_start_of_the_month() -> None:
    port, state = _daily()
    state.loc["2024-03-31", "own63"] = 9.99

    monthly = monthly_state_frame(port, state)

    assert monthly.index[0].is_month_end
    # March's `own63_before` is February's last value, not March's own.
    assert monthly.loc["2024-03-31", "own63_before"] == pytest.approx(0.1)
    assert monthly.loc["2024-01-31", "ret"] < 0


def test_separate_crashes_reports_a_standardised_difference() -> None:
    port, state = _daily()
    monthly = monthly_state_frame(port, state)

    table = separate_crashes(monthly, -0.08)

    assert list(table.index) == list(STATE_COLUMNS)
    assert table.loc["gate_open", "crash_mean"] == pytest.approx(1.0)
    assert table.loc["gate_open", "rest_mean"] == pytest.approx(0.0)
    assert table.loc["disp_ratio", "difference"] < 0
    assert int(table.loc["gate_open", "months_of_data"]) == 2


def test_separate_crashes_refuses_a_threshold_that_leaves_one_group_empty() -> None:
    port, state = _daily()
    monthly = monthly_state_frame(port, state)

    with pytest.raises(ValueError):
        separate_crashes(monthly, -0.99)
