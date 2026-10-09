from __future__ import annotations

import pandas as pd
import pytest

from atlas20.derivatives.engine import (
    DerivativeBacktestConfig,
    run_derivative_backtest,
)


def _candles(
    prices: dict[str, float],
    *,
    start: str = "2026-01-01T00:00:00Z",
    periods: int = 30,
    freq: str = "1h",
) -> dict[str, pd.DataFrame]:
    index = pd.date_range(start, periods=periods, freq=freq, tz="UTC")
    return {
        asset: pd.DataFrame(
            {
                "open": price,
                "high": price,
                "low": price,
                "close": price,
            },
            index=index,
        )
        for asset, price in prices.items()
    }


def _flat_frame(index: pd.DatetimeIndex, value: float = 100.0) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "open": value,
            "high": value,
            "low": value,
            "close": value,
        },
        index=index,
    )


def test_long_funding_is_deducted_from_isolated_margin() -> None:
    index = pd.date_range("2026-01-01T00:00:00Z", "2026-01-02T05:00:00Z", freq="1h", tz="UTC")
    candles = {"BTC": _flat_frame(index)}
    funding = pd.DataFrame({"BTC": [0.001]}, index=pd.DatetimeIndex(["2026-01-02T04:00:00Z"]))
    targets = {
        pd.Timestamp("2026-01-01T00:00:00Z"): pd.Series({"BTC": 1.0}),
    }

    result = run_derivative_backtest(
        candles,
        targets,
        funding_rates=funding,
        config=DerivativeBacktestConfig(
            initial_capital=1_000.0,
            taker_fee_bps=0.0,
            slippage_bps=0.0,
            liquidation_slippage_bps=0.0,
            fee_buffer=0.0,
        ),
    )

    assert result.trades.iloc[0]["timestamp"] == pd.Timestamp("2026-01-02T03:00:00Z")
    assert result.funding.iloc[0]["amount"] == pytest.approx(-1.0)
    assert result.equity_curve.iloc[-1] == pytest.approx(999.0)


def test_funding_timestamp_jitter_is_normalised_to_the_settlement_hour() -> None:
    index = pd.date_range("2026-01-01T00:00:00Z", "2026-01-02T05:00:00Z", freq="1h")
    candles = {"BTC": _flat_frame(index)}
    funding = pd.DataFrame(
        {"BTC": [0.001]},
        index=pd.DatetimeIndex(["2026-01-02T04:00:00.006Z"]),
    )
    targets = {pd.Timestamp("2026-01-01T00:00:00Z"): pd.Series({"BTC": 1.0})}

    result = run_derivative_backtest(
        candles,
        targets,
        funding_rates=funding,
        config=DerivativeBacktestConfig(
            initial_capital=1_000.0,
            taker_fee_bps=0.0,
            slippage_bps=0.0,
            liquidation_slippage_bps=0.0,
            fee_buffer=0.0,
        ),
    )

    assert result.funding.iloc[0]["timestamp"] == pd.Timestamp("2026-01-02T04:00:00Z")
    assert result.equity_curve.iloc[-1] == pytest.approx(999.0)


def test_long_position_liquidates_on_hourly_low_using_mark_price() -> None:
    index = pd.date_range("2026-01-01T00:00:00Z", "2026-01-02T05:00:00Z", freq="1h", tz="UTC")
    candles = {"BTC": _flat_frame(index)}
    candles["BTC"].loc[pd.Timestamp("2026-01-02T04:00:00Z"), ["open", "high", "low", "close"]] = [
        100.0,
        100.0,
        60.0,
        60.0,
    ]
    targets = {pd.Timestamp("2026-01-01T00:00:00Z"): pd.Series({"BTC": 1.0})}

    result = run_derivative_backtest(
        candles,
        targets,
        funding_rates=pd.DataFrame(index=pd.DatetimeIndex([], tz="UTC")),
        config=DerivativeBacktestConfig(
            initial_capital=1_000.0,
            taker_fee_bps=0.0,
            slippage_bps=0.0,
            liquidation_slippage_bps=0.0,
            fee_buffer=0.0,
        ),
    )

    assert len(result.liquidations) == 1
    event = result.liquidations.iloc[0]
    assert event["side"] == "long"
    assert event["trigger_timestamp"] == pd.Timestamp("2026-01-02T04:00:00Z")
    assert event["bad_debt"] == pytest.approx(0.0)
    assert result.equity_curve.iloc[-1] == pytest.approx(697.0, abs=0.5)


def test_short_position_liquidates_on_hourly_high() -> None:
    index = pd.date_range("2026-01-01T00:00:00Z", "2026-01-02T05:00:00Z", freq="1h", tz="UTC")
    candles = {"BTC": _flat_frame(index)}
    candles["BTC"].loc[pd.Timestamp("2026-01-02T04:00:00Z"), ["open", "high", "low", "close"]] = [
        100.0,
        160.0,
        100.0,
        160.0,
    ]
    targets = {pd.Timestamp("2026-01-01T00:00:00Z"): pd.Series({"BTC": -1.0})}

    result = run_derivative_backtest(
        candles,
        targets,
        funding_rates=pd.DataFrame(index=pd.DatetimeIndex([], tz="UTC")),
        config=DerivativeBacktestConfig(
            initial_capital=1_000.0,
            taker_fee_bps=0.0,
            slippage_bps=0.0,
            liquidation_slippage_bps=0.0,
            fee_buffer=0.0,
        ),
    )

    assert len(result.liquidations) == 1
    event = result.liquidations.iloc[0]
    assert event["side"] == "short"
    assert event["trigger_timestamp"] == pd.Timestamp("2026-01-02T04:00:00Z")
    assert result.equity_curve.iloc[-1] == pytest.approx(505.0, abs=0.5)


def test_margin_utilization_caps_requested_gross_exposure() -> None:
    index = pd.date_range("2026-01-01T00:00:00Z", "2026-01-02T05:00:00Z", freq="1h", tz="UTC")
    candles = {"BTC": _flat_frame(index)}
    targets = {pd.Timestamp("2026-01-01T00:00:00Z"): pd.Series({"BTC": 3.0})}

    result = run_derivative_backtest(
        candles,
        targets,
        funding_rates=pd.DataFrame(index=pd.DatetimeIndex([], tz="UTC")),
        config=DerivativeBacktestConfig(
            initial_capital=1_000.0,
            max_gross_exposure=3.0,
            max_margin_utilization=0.85,
            taker_fee_bps=0.0,
            slippage_bps=0.0,
            liquidation_slippage_bps=0.0,
            fee_buffer=0.0,
        ),
    )

    assert result.positions.iloc[0]["notional"] == pytest.approx(1_000.0 * 0.85 / 0.31)


def test_missing_funding_for_a_held_asset_fails_closed() -> None:
    index = pd.date_range("2026-01-01T00:00:00Z", "2026-01-02T05:00:00Z", freq="1h", tz="UTC")
    candles = {"BTC": _flat_frame(index)}
    funding = pd.DataFrame({"BTC": [float("nan")]}, index=pd.DatetimeIndex(["2026-01-02T04:00:00Z"]))
    targets = {pd.Timestamp("2026-01-01T00:00:00Z"): pd.Series({"BTC": 1.0})}

    with pytest.raises(ValueError, match="missing funding"):
        run_derivative_backtest(
            candles,
            targets,
            funding_rates=funding,
            config=DerivativeBacktestConfig(
                initial_capital=1_000.0,
                taker_fee_bps=0.0,
                slippage_bps=0.0,
                liquidation_slippage_bps=0.0,
            ),
        )


def test_funding_gap_for_a_held_asset_fails_closed() -> None:
    index = pd.date_range("2026-01-01T00:00:00Z", "2026-01-03T05:00:00Z", freq="1h")
    candles = {"BTC": _flat_frame(index)}
    funding = pd.DataFrame(
        {"BTC": [0.001]},
        index=pd.DatetimeIndex(["2026-01-03T00:00:00Z"]),
    )
    targets = {pd.Timestamp("2026-01-01T00:00:00Z"): pd.Series({"BTC": 1.0})}

    with pytest.raises(ValueError, match="funding gap"):
        run_derivative_backtest(
            candles,
            targets,
            funding_rates=funding,
            funding_intervals_hours={"BTC": 8.0},
            config=DerivativeBacktestConfig(
                initial_capital=1_000.0,
                taker_fee_bps=0.0,
                slippage_bps=0.0,
                liquidation_slippage_bps=0.0,
            ),
        )


def test_complete_funding_schedule_for_a_held_asset_passes() -> None:
    index = pd.date_range("2026-01-01T00:00:00Z", "2026-01-03T05:00:00Z", freq="1h")
    candles = {"BTC": _flat_frame(index)}
    funding_index = pd.date_range("2026-01-01T00:00:00Z", "2026-01-03T00:00:00Z", freq="8h")
    funding = pd.DataFrame({"BTC": [0.0] * len(funding_index)}, index=funding_index)
    targets = {pd.Timestamp("2026-01-01T00:00:00Z"): pd.Series({"BTC": 1.0})}

    result = run_derivative_backtest(
        candles,
        targets,
        funding_rates=funding,
        funding_intervals_hours={"BTC": 8.0},
        config=DerivativeBacktestConfig(
            initial_capital=1_000.0,
            taker_fee_bps=0.0,
            slippage_bps=0.0,
            liquidation_slippage_bps=0.0,
            fee_buffer=0.0,
        ),
    )

    assert result.equity_curve.iloc[-1] == pytest.approx(1_000.0)


def test_missing_mark_exit_last_closes_position_instead_of_carrying_it() -> None:
    btc_index = pd.date_range("2026-01-01T00:00:00Z", "2026-01-02T03:00:00Z", freq="1h", tz="UTC")
    eth_index = pd.date_range("2026-01-01T00:00:00Z", "2026-01-02T04:00:00Z", freq="1h", tz="UTC")
    candles = {"BTC": _flat_frame(btc_index), "ETH": _flat_frame(eth_index)}
    targets = {pd.Timestamp("2026-01-01T00:00:00Z"): pd.Series({"BTC": 1.0})}

    result = run_derivative_backtest(
        candles,
        targets,
        funding_rates=None,
        config=DerivativeBacktestConfig(
            initial_capital=1_000.0,
            taker_fee_bps=0.0,
            slippage_bps=0.0,
            liquidation_slippage_bps=0.0,
            fee_buffer=0.0,
            missing_mark_policy="exit_last",
        ),
    )

    exits = result.trades[result.trades["reason"] == "missing_mark_exit"]
    assert len(exits) == 1
    assert exits.iloc[0]["timestamp"] == pd.Timestamp("2026-01-02T04:00:00Z")
    assert result.equity_curve.iloc[-1] == pytest.approx(1_000.0)


def test_rebalance_reduces_existing_position_without_full_close() -> None:
    index = pd.date_range("2026-01-01T00:00:00Z", "2026-01-03T05:00:00Z", freq="1h", tz="UTC")
    candles = {"BTC": _flat_frame(index)}
    targets = {
        pd.Timestamp("2026-01-01T00:00:00Z"): pd.Series({"BTC": 1.0}),
        pd.Timestamp("2026-01-02T00:00:00Z"): pd.Series({"BTC": 0.5}),
    }

    result = run_derivative_backtest(
        candles,
        targets,
        funding_rates=None,
        config=DerivativeBacktestConfig(
            initial_capital=1_000.0,
            taker_fee_bps=0.0,
            slippage_bps=0.0,
            liquidation_slippage_bps=0.0,
            fee_buffer=0.0,
        ),
    )

    actions = result.trades["action"].tolist()
    assert actions == ["open", "reduce"]
    assert result.positions.iloc[0]["notional"] == pytest.approx(1_000.0)
    assert result.equity_curve.iloc[-1] == pytest.approx(1_000.0)


def test_rebalance_increases_existing_position_without_full_close() -> None:
    index = pd.date_range("2026-01-01T00:00:00Z", "2026-01-03T05:00:00Z", freq="1h", tz="UTC")
    candles = {"BTC": _flat_frame(index)}
    targets = {
        pd.Timestamp("2026-01-01T00:00:00Z"): pd.Series({"BTC": 0.5}),
        pd.Timestamp("2026-01-02T00:00:00Z"): pd.Series({"BTC": 1.0}),
    }

    result = run_derivative_backtest(
        candles,
        targets,
        funding_rates=None,
        config=DerivativeBacktestConfig(
            initial_capital=1_000.0,
            taker_fee_bps=0.0,
            slippage_bps=0.0,
            liquidation_slippage_bps=0.0,
            fee_buffer=0.0,
        ),
    )

    assert result.trades["action"].tolist() == ["open", "increase"]
    assert result.positions.iloc[0]["notional"] == pytest.approx(500.0)
    assert result.equity_curve.iloc[-1] == pytest.approx(1_000.0)


def test_evaluation_window_excludes_prestart_marks_and_postend_targets() -> None:
    index = pd.date_range("2026-01-01T00:00:00Z", "2026-01-10T00:00:00Z", freq="1h")
    candles = {"BTC": _flat_frame(index)}
    targets = {
        pd.Timestamp("2026-01-01T00:00:00Z"): pd.Series({"BTC": 1.0}),
        pd.Timestamp("2026-01-05T00:00:00Z"): pd.Series({"BTC": 0.5}),
        pd.Timestamp("2026-01-07T00:00:00Z"): pd.Series({"BTC": 0.0}),
    }

    result = run_derivative_backtest(
        candles,
        targets,
        funding_rates=None,
        config=DerivativeBacktestConfig(
            initial_capital=1_000.0,
            taker_fee_bps=0.0,
            slippage_bps=0.0,
            liquidation_slippage_bps=0.0,
            fee_buffer=0.0,
        ),
        start_time=pd.Timestamp("2026-01-02T00:00:00Z"),
        end_time=pd.Timestamp("2026-01-08T00:00:00Z"),
    )

    assert result.equity_curve.index.min() == pd.Timestamp("2026-01-02T00:00:00Z")
    assert result.equity_curve.index.max() == pd.Timestamp("2026-01-07T23:00:00Z")
    assert result.daily_returns.index.min() == pd.Timestamp("2026-01-02T00:00:00Z")
    assert result.daily_returns.index.max() == pd.Timestamp("2026-01-07T00:00:00Z")
    assert result.trades["timestamp"].tolist() == [
        pd.Timestamp("2026-01-02T03:00:00Z"),
        pd.Timestamp("2026-01-06T03:00:00Z"),
    ]


def test_missing_mark_carry_uses_last_close_within_limit() -> None:
    btc_index = pd.date_range("2026-01-01T00:00:00Z", "2026-01-02T03:00:00Z", freq="1h", tz="UTC")
    eth_index = pd.date_range("2026-01-01T00:00:00Z", "2026-01-02T04:00:00Z", freq="1h", tz="UTC")
    candles = {"BTC": _flat_frame(btc_index), "ETH": _flat_frame(eth_index)}
    targets = {pd.Timestamp("2026-01-01T00:00:00Z"): pd.Series({"BTC": 1.0})}

    result = run_derivative_backtest(
        candles,
        targets,
        funding_rates=None,
        config=DerivativeBacktestConfig(
            initial_capital=1_000.0,
            taker_fee_bps=0.0,
            slippage_bps=0.0,
            liquidation_slippage_bps=0.0,
            fee_buffer=0.0,
            missing_mark_policy="carry",
            missing_mark_max_carry_hours=1,
        ),
    )

    assert result.trades["action"].tolist() == ["open"]
    assert result.equity_curve.iloc[-1] == pytest.approx(1_000.0)


def test_missing_mark_carry_exits_after_limit() -> None:
    btc_index = pd.date_range("2026-01-01T00:00:00Z", "2026-01-02T03:00:00Z", freq="1h", tz="UTC")
    eth_index = pd.date_range("2026-01-01T00:00:00Z", "2026-01-02T06:00:00Z", freq="1h", tz="UTC")
    candles = {"BTC": _flat_frame(btc_index), "ETH": _flat_frame(eth_index)}
    targets = {pd.Timestamp("2026-01-01T00:00:00Z"): pd.Series({"BTC": 1.0})}

    result = run_derivative_backtest(
        candles,
        targets,
        funding_rates=None,
        config=DerivativeBacktestConfig(
            initial_capital=1_000.0,
            taker_fee_bps=0.0,
            slippage_bps=0.0,
            liquidation_slippage_bps=0.0,
            fee_buffer=0.0,
            missing_mark_policy="carry",
            missing_mark_max_carry_hours=1,
        ),
    )

    exits = result.trades[result.trades["reason"] == "missing_mark_exit"]
    assert len(exits) == 1
    assert exits.iloc[0]["timestamp"] == pd.Timestamp("2026-01-02T05:00:00Z")


def test_funding_carry_last_reuses_the_last_settlement_and_flags_the_event() -> None:
    """A missing settlement must be an explicit carried stress rate, not a zero."""

    index = pd.date_range("2026-01-01T00:00:00Z", "2026-01-02T09:00:00Z", freq="1h")
    candles = {"BTC": _flat_frame(index)}
    funding = pd.DataFrame(
        {"BTC": [0.001, float("nan")], "ETH": [0.0005, 0.0005]},
        index=pd.DatetimeIndex(["2026-01-02T00:00:00Z", "2026-01-02T08:00:00Z"]),
    )
    targets = {pd.Timestamp("2026-01-01T00:00:00Z"): pd.Series({"BTC": 1.0})}

    result = run_derivative_backtest(
        candles,
        targets,
        funding_rates=funding,
        funding_intervals_hours={"BTC": 8.0},
        config=DerivativeBacktestConfig(
            initial_capital=1_000.0,
            taker_fee_bps=0.0,
            slippage_bps=0.0,
            liquidation_slippage_bps=0.0,
            fee_buffer=0.0,
            funding_missing_policy="carry_last",
        ),
    )

    assert list(result.funding["timestamp"]) == [pd.Timestamp("2026-01-02T08:00:00Z")]
    assert list(result.funding["carried"]) == [True]
    assert result.funding["amount"].sum() == pytest.approx(-1.0)
    assert result.equity_curve.iloc[-1] == pytest.approx(999.0)


def test_funding_carry_last_fails_closed_past_the_carry_limit() -> None:
    index = pd.date_range("2026-01-01T00:00:00Z", "2026-01-03T09:00:00Z", freq="1h")
    candles = {"BTC": _flat_frame(index)}
    funding = pd.DataFrame(
        {"BTC": [0.001, float("nan")], "ETH": [0.0005, 0.0005]},
        index=pd.DatetimeIndex(["2026-01-02T00:00:00Z", "2026-01-03T08:00:00Z"]),
    )
    targets = {pd.Timestamp("2026-01-01T00:00:00Z"): pd.Series({"BTC": 1.0})}

    with pytest.raises(ValueError, match="carry limit"):
        run_derivative_backtest(
            candles,
            targets,
            funding_rates=funding,
            funding_intervals_hours={"BTC": 8.0},
            config=DerivativeBacktestConfig(
                initial_capital=1_000.0,
                taker_fee_bps=0.0,
                slippage_bps=0.0,
                liquidation_slippage_bps=0.0,
                fee_buffer=0.0,
                funding_missing_policy="carry_last",
                funding_carry_max_hours=12.0,
            ),
        )


def test_carry_last_does_not_charge_an_asset_that_settles_on_a_slower_clock() -> None:
    """Union funding timestamps must not double-charge an 8h asset on a 4h cadence."""

    index = pd.date_range("2026-01-01T00:00:00Z", "2026-01-02T09:00:00Z", freq="1h")
    candles = {"BTC": _flat_frame(index)}
    funding_index = pd.DatetimeIndex(
        [
            "2026-01-02T00:00:00Z",
            "2026-01-02T04:00:00Z",
            "2026-01-02T08:00:00Z",
        ]
    )
    # BTC only settles every 8h; the 04:00 row belongs to another contract.
    funding = pd.DataFrame(
        {"BTC": [0.001, float("nan"), float("nan")], "SOL": [0.0005, 0.0005, 0.0005]},
        index=funding_index,
    )
    targets = {pd.Timestamp("2026-01-01T00:00:00Z"): pd.Series({"BTC": 1.0})}

    result = run_derivative_backtest(
        candles,
        targets,
        funding_rates=funding,
        funding_intervals_hours={"BTC": 8.0, "SOL": 4.0},
        config=DerivativeBacktestConfig(
            initial_capital=1_000.0,
            taker_fee_bps=0.0,
            slippage_bps=0.0,
            liquidation_slippage_bps=0.0,
            fee_buffer=0.0,
            funding_missing_policy="carry_last",
        ),
    )

    assert list(result.funding["timestamp"]) == [pd.Timestamp("2026-01-02T08:00:00Z")]
    assert list(result.funding["carried"]) == [True]
    assert result.funding["amount"].sum() == pytest.approx(-1.0)


def test_stress_median_fills_an_asset_with_no_funding_history_at_all() -> None:
    index = pd.date_range("2026-01-01T00:00:00Z", "2026-01-02T09:00:00Z", freq="1h")
    candles = {"BTC": _flat_frame(index)}
    funding_index = pd.DatetimeIndex(["2026-01-02T00:00:00Z", "2026-01-02T08:00:00Z"])
    funding = pd.DataFrame({"SOL": [0.004, 0.004]}, index=funding_index)
    targets = {pd.Timestamp("2026-01-01T00:00:00Z"): pd.Series({"BTC": 1.0})}

    result = run_derivative_backtest(
        candles,
        targets,
        funding_rates=funding,
        funding_intervals_hours={"BTC": 8.0, "SOL": 8.0},
        config=DerivativeBacktestConfig(
            initial_capital=1_000.0,
            taker_fee_bps=0.0,
            slippage_bps=0.0,
            liquidation_slippage_bps=0.0,
            fee_buffer=0.0,
            funding_missing_policy="stress_median",
        ),
    )

    assert list(result.funding["timestamp"]) == [pd.Timestamp("2026-01-02T08:00:00Z")]
    assert list(result.funding["carried"]) == [True]
    assert result.funding["rate"].iloc[0] == pytest.approx(0.004)
    assert result.funding["amount"].sum() == pytest.approx(-4.0)


def test_execution_past_the_last_mark_candle_fails_closed() -> None:
    """A signal the frozen window cannot fill must not be silently evaluated."""

    index = pd.date_range("2026-01-01T00:00:00Z", "2026-01-03T23:00:00Z", freq="1h")
    candles = {"BTC": _flat_frame(index)}
    targets = {
        pd.Timestamp("2026-01-01T00:00:00Z"): pd.Series({"BTC": 1.0}),
        pd.Timestamp("2026-01-03T00:00:00Z"): pd.Series({"BTC": 0.0}),
    }

    with pytest.raises(ValueError, match="no mark candle at or within one hour"):
        run_derivative_backtest(
            candles,
            targets,
            config=DerivativeBacktestConfig(
                initial_capital=1_000.0,
                taker_fee_bps=0.0,
                slippage_bps=0.0,
                liquidation_slippage_bps=0.0,
                fee_buffer=0.0,
            ),
            start_time=pd.Timestamp("2026-01-01T00:00:00Z"),
            end_time=pd.Timestamp("2026-01-05T00:00:00Z"),
        )


def test_market_candles_drive_the_fill_price_while_mark_drives_liquidation() -> None:
    index = pd.date_range("2026-01-01T00:00:00Z", "2026-01-02T09:00:00Z", freq="1h")
    marks = {"BTC": _flat_frame(index)}
    market = {"BTC": _flat_frame(index, value=101.0)}
    targets = {pd.Timestamp("2026-01-01T00:00:00Z"): pd.Series({"BTC": 1.0})}

    result = run_derivative_backtest(
        marks,
        targets,
        market_candles=market,
        config=DerivativeBacktestConfig(
            initial_capital=1_000.0,
            taker_fee_bps=0.0,
            slippage_bps=0.0,
            liquidation_slippage_bps=0.0,
            fee_buffer=0.0,
        ),
    )

    assert result.trades.iloc[0]["price"] == pytest.approx(101.0)
    # the mark path still values the book, so paying 101 for a 100 mark costs 1%
    assert result.equity_curve.iloc[-1] == pytest.approx(1_000.0 * 100.0 / 101.0)


def test_missing_market_candle_for_a_fill_fails_closed_by_default() -> None:
    index = pd.date_range("2026-01-01T00:00:00Z", "2026-01-02T09:00:00Z", freq="1h")
    marks = {"BTC": _flat_frame(index)}
    market_index = index[index < pd.Timestamp("2026-01-02T03:00:00Z")]
    market = {"BTC": _flat_frame(market_index, value=101.0)}
    targets = {pd.Timestamp("2026-01-01T00:00:00Z"): pd.Series({"BTC": 1.0})}

    with pytest.raises(ValueError, match="missing market candle for fill"):
        run_derivative_backtest(
            marks,
            targets,
            market_candles=market,
            config=DerivativeBacktestConfig(
                initial_capital=1_000.0,
                taker_fee_bps=0.0,
                slippage_bps=0.0,
                liquidation_slippage_bps=0.0,
                fee_buffer=0.0,
            ),
        )


def test_missing_market_candle_can_downgrade_to_mark_with_an_explicit_policy() -> None:
    index = pd.date_range("2026-01-01T00:00:00Z", "2026-01-02T09:00:00Z", freq="1h")
    marks = {"BTC": _flat_frame(index)}
    market_index = index[index < pd.Timestamp("2026-01-02T03:00:00Z")]
    market = {"BTC": _flat_frame(market_index, value=101.0)}
    targets = {pd.Timestamp("2026-01-01T00:00:00Z"): pd.Series({"BTC": 1.0})}

    result = run_derivative_backtest(
        marks,
        targets,
        market_candles=market,
        config=DerivativeBacktestConfig(
            initial_capital=1_000.0,
            taker_fee_bps=0.0,
            slippage_bps=0.0,
            liquidation_slippage_bps=0.0,
            fee_buffer=0.0,
            fill_missing_policy="downgrade_to_mark",
        ),
    )

    assert result.trades.iloc[0]["price"] == pytest.approx(100.0)
    assert result.fill_downgrades.iloc[0]["asset"] == "BTC"
