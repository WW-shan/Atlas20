from __future__ import annotations

import pandas as pd
import pytest

from scripts.run_phase_momentum_robustness import _best_year_removal


def test_best_year_removal_drops_exactly_one_calendar_year() -> None:
    index = pd.to_datetime(["2022-06-01", "2022-06-02", "2023-06-01", "2023-06-02"])
    returns = {"s": pd.Series([0.10, 0.10, 1.00, -0.50], index=index)}

    table = _best_year_removal(returns).set_index("removed_year")

    assert table.loc[2022, "days"] == 2
    assert table.loc[2022, "multiple"] == pytest.approx(2.0 * 0.5)
    assert table.loc[2023, "multiple"] == pytest.approx(1.1 * 1.1)
