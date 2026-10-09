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
