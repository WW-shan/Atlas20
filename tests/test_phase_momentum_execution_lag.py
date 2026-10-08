from __future__ import annotations

import pandas as pd
import pytest

from atlas20.config import load_config
from atlas20.strategies.phase_momentum import PhaseMomentumBuildResult
from atlas20.universe.builder import MarketDataBundle
from scripts.run_phase_momentum import _production_result
from scripts.run_phase_momentum_execution_lag import _execution_lag_table, _fill_timing_table


def _market() -> MarketDataBundle:
    dates = pd.date_range("2024-01-01", periods=5, freq="D")
    # +10% on day 1 and +20% on day 2, flat afterwards.
    price = pd.DataFrame({"bitcoin": [100.0, 110.0, 132.0, 132.0, 132.0]}, index=dates)
    return MarketDataBundle(
        raw_price=price,
        price=price,
        returns=price.pct_change().fillna(0.0),
        market_cap=price * 1_000_000.0,
        volume=pd.DataFrame(1_000_000.0, index=dates, columns=price.columns),
        history_count=pd.DataFrame(200, index=dates, columns=price.columns),
        metadata=pd.DataFrame({"sector": ["Other"]}, index=price.columns),
    )


def _built(dates: pd.DatetimeIndex) -> PhaseMomentumBuildResult:
    return PhaseMomentumBuildResult(
        targets={dates[0]: pd.Series({"bitcoin": 1.0})},
        exposures={dates[0]: 1.0},
        selection_history=pd.DataFrame(),
        sleeve_targets=(),
    )


def test_production_result_can_fill_one_day_after_the_signal_close() -> None:
    market = _market()
    dates = market.price.index

    result = _production_result(
        load_config("config/base.yaml"),
        market,
        _built(dates),
        dates,
        cost_bps=0.0,
        execution_lag_days=1,
    )

    assert result.daily_returns.loc[dates[1]] == 0.0
    assert result.daily_returns.loc[dates[2]] == pytest.approx(0.20)


def test_execution_lag_table_reports_each_lag_and_cost() -> None:
    market = _market()
    dates = market.price.index

    table = _execution_lag_table(
        load_config("config/base.yaml"),
        market,
        _built(dates),
        dates,
        lags=(0, 1, 2),
        costs=(0.0,),
    )

    multiples = table.set_index("execution_lag_days")["multiple"]
    assert multiples.loc[0] == pytest.approx(1.32)
    assert multiples.loc[1] == pytest.approx(1.20)
    assert multiples.loc[2] == pytest.approx(1.00)
    assert set(table["cost_bps"]) == {0.0}


def test_production_result_can_fill_part_way_through_the_next_day() -> None:
    market = _market()
    dates = market.price.index
    # 4% of day 1's 10% happened between the signal close and the fill.
    pre_fill = pd.DataFrame({"bitcoin": [0.0, 0.04, 0.0, 0.0, 0.0]}, index=dates)

    result = _production_result(
        load_config("config/base.yaml"),
        market,
        _built(dates),
        dates,
        cost_bps=0.0,
        pre_fill=pre_fill,
    )

    assert result.daily_returns.loc[dates[1]] == pytest.approx(1.10 / 1.04 - 1.0)
    assert result.daily_returns.loc[dates[2]] == pytest.approx(0.20)


def test_fill_timing_table_reports_each_fill_hour_and_missing_candle_policy() -> None:
    market = _market()
    dates = market.price.index
    # Day 1 opens at 100 (day 0's close) and is up 4% by the 03:00 UTC fill.
    start = pd.Timestamp(dates[1], tz="UTC")
    hourly = {
        "bitcoin": pd.DataFrame(
            {
                "open_time": [start + pd.Timedelta(hours=hour) for hour in range(3)],
                "open": [100.0, 101.0, 102.0],
                "close": [101.0, 102.0, 104.0],
            }
        )
    }

    table = _fill_timing_table(
        load_config("config/base.yaml"),
        market,
        _built(dates),
        dates,
        hourly=hourly,
        fill_hours=(3,),
        costs=(0.0,),
    )

    rows = table.set_index("missing_hourly")
    assert set(rows.index) == {"day_close", "prior_close"}
    for policy in ("day_close", "prior_close"):
        assert rows.loc[policy, "fill_hours"] == 3
        assert rows.loc[policy, "multiple"] == pytest.approx(1.10 / 1.04 * 1.20)
        assert rows.loc[policy, "observed_weight_share"] == pytest.approx(1.0)
