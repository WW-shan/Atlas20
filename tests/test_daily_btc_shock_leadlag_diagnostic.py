from __future__ import annotations

import numpy as np
import pandas as pd
import pytest


def test_future_close_return_starts_at_next_close() -> None:
    from scripts.run_daily_btc_shock_leadlag_diagnostic import _future_close_return

    close = pd.DataFrame({"A": [100.0, 110.0, 121.0, 133.1, 146.41]})

    result = _future_close_return(close, horizon=2)

    assert result.iloc[0, 0] == pytest.approx(np.log(133.1 / 110.0))
    assert result.iloc[1, 0] == pytest.approx(np.log(146.41 / 121.0))
    assert np.isnan(result.iloc[-1, 0])


def test_cell_tier_requires_cost_buffer_and_sign_stability() -> None:
    from scripts.run_daily_btc_shock_leadlag_diagnostic import _cell_tier

    assert (
        _cell_tier(
            discovery_ic=-0.05,
            validation_ic=-0.04,
            discovery_spread=60.0,
            validation_spread=55.0,
        )
        == "candidate-for-backtest"
    )
    assert (
        _cell_tier(
            discovery_ic=-0.05,
            validation_ic=-0.04,
            discovery_spread=30.0,
            validation_spread=25.0,
        )
        == "watch"
    )
    assert (
        _cell_tier(
            discovery_ic=-0.05,
            validation_ic=0.01,
            discovery_spread=80.0,
            validation_spread=80.0,
        )
        == "rejected-now"
    )
