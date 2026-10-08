from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from atlas20.config import load_config
from atlas20.strategies.phase_momentum import MomentumSignalSpec, PhaseMomentumSpec
from atlas20.universe.builder import MarketDataBundle
from scripts.run_phase_momentum import _monthly_start_sensitivity


def _market(price: pd.DataFrame) -> MarketDataBundle:
    return MarketDataBundle(
        raw_price=price,
        price=price,
        returns=price.pct_change().fillna(0.0),
        market_cap=price * 1_000_000.0,
        volume=pd.DataFrame(1_000_000.0, index=price.index, columns=price.columns),
        history_count=pd.DataFrame(200, index=price.index, columns=price.columns),
        metadata=pd.DataFrame({"sector": ["Other"] * len(price.columns)}, index=price.columns),
    )


def test_monthly_start_rebuilds_the_strategy_from_each_start() -> None:
    dates = pd.date_range("2024-01-01", periods=200, freq="D")
    price = pd.DataFrame(
        {"a": 100.0 * 1.01 ** np.arange(len(dates)), "bitcoin": [100.0] * len(dates)},
        index=dates,
    )
    universe = pd.DataFrame({"rebalance_date": dates, "coin_id": "a"})
    spec = PhaseMomentumSpec(
        rebalance_days=1,
        phase_offsets=(0,),
        btc_ma_window=2,
        btc_confirm_days=1,
        target_volatility=10.0,
        vol_window=2,
    )

    table = _monthly_start_sensitivity(
        load_config("config/base.yaml"),
        _market(price),
        universe,
        dates,
        cost_bps=0.0,
        spec=spec,
        signal_specs=(MomentumSignalSpec(name="one_day", window_weights=((1, 1.0),)),),
    )

    march = table.set_index("start").loc[pd.Timestamp("2024-03-01")]
    slice_days = int((dates >= pd.Timestamp("2024-03-01")).sum())
    # Invested from the day after the start rather than parked in cash until
    # an event that the 2024-01-01 build never produces again.
    assert march["multiple"] == pytest.approx(1.01 ** (slice_days - 1), rel=1e-9)
