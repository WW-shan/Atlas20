from __future__ import annotations

import pandas as pd
import pytest

from atlas20.derivatives.engine import (
    DerivativeBacktestConfig,
    run_derivative_backtest,
)
from atlas20.derivatives.execution import ContractSpec


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


def test_short_adverse_funding_multiplier_is_applied_only_to_short_positions() -> None:
    index = pd.date_range("2026-01-01T00:00:00Z", "2026-01-02T05:00:00Z", freq="1h", tz="UTC")
    candles = {"BTC": _flat_frame(index)}
    funding = pd.DataFrame({"BTC": [-0.001]}, index=pd.DatetimeIndex(["2026-01-02T04:00:00Z"]))
    targets = {pd.Timestamp("2026-01-01T00:00:00Z"): pd.Series({"BTC": -1.0})}

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
            funding_stress="short-adverse",
            funding_multiplier=3.0,
        ),
    )

    assert result.funding.iloc[0]["amount"] == pytest.approx(-3.0)
    assert result.equity_curve.iloc[-1] == pytest.approx(997.0)


def test_short_adverse_does_not_let_long_funding_income_offset_the_stress() -> None:
    index = pd.date_range("2026-01-01T00:00:00Z", "2026-01-02T05:00:00Z", freq="1h", tz="UTC")
    candles = {"BTC": _flat_frame(index)}
    funding = pd.DataFrame({"BTC": [-0.001]}, index=pd.DatetimeIndex(["2026-01-02T04:00:00Z"]))
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
            funding_stress="short-adverse",
            funding_multiplier=3.0,
        ),
    )

    assert result.funding.iloc[0]["amount"] == pytest.approx(0.0)


def test_two_sided_adverse_funding_charges_long_and_short_positions() -> None:
    index = pd.date_range("2026-01-01T00:00:00Z", "2026-01-02T05:00:00Z", freq="1h", tz="UTC")
    candles = {"BTC": _flat_frame(index), "ETH": _flat_frame(index)}
    funding = pd.DataFrame(
        {"BTC": [0.001], "ETH": [-0.001]},
        index=pd.DatetimeIndex(["2026-01-02T04:00:00Z"]),
    )
    targets = {
        pd.Timestamp("2026-01-01T00:00:00Z"): pd.Series({"BTC": 0.5, "ETH": -0.5})
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
            funding_stress="two-sided-adverse",
            funding_multiplier=3.0,
        ),
    )

    assert result.funding["amount"].sum() == pytest.approx(-3.0)
    assert result.equity_curve.iloc[-1] == pytest.approx(997.0)


@pytest.mark.parametrize("stress", ["unknown", "long_adverse", ""])
def test_funding_stress_rejects_unknown_values(stress: str) -> None:
    with pytest.raises(ValueError, match="funding_stress"):
        DerivativeBacktestConfig(funding_stress=stress)


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


def test_short_stop_loss_closes_before_isolated_liquidation() -> None:
    index = pd.date_range("2026-01-01T00:00:00Z", "2026-01-02T05:00:00Z", freq="1h", tz="UTC")
    candles = {"BTC": _flat_frame(index)}
    candles["BTC"].loc[pd.Timestamp("2026-01-02T04:00:00Z"), ["open", "high", "low", "close"]] = [
        100.0,
        125.0,
        100.0,
        125.0,
    ]
    targets = {pd.Timestamp("2026-01-01T00:00:00Z"): pd.Series({"BTC": -1.0})}

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
            short_stop_loss_pct=0.20,
        ),
    )

    assert result.liquidations.empty
    stops = result.trades[result.trades["reason"] == "stop_loss"]
    assert len(stops) == 1
    assert stops.iloc[0]["side"] == "short"
    assert stops.iloc[0]["price"] == pytest.approx(120.0)
    assert result.equity_curve.iloc[-1] == pytest.approx(800.0)


def test_short_stop_trigger_uses_the_venue_price_grid() -> None:
    index = pd.date_range("2026-01-01T00:00:00Z", "2026-01-02T05:00:00Z", freq="1h", tz="UTC")
    candles = {"BTC": _flat_frame(index)}
    candles["BTC"].loc[pd.Timestamp("2026-01-02T04:00:00Z"), ["open", "high", "low", "close"]] = [
        100.0,
        125.0,
        100.0,
        125.0,
    ]
    targets = {pd.Timestamp("2026-01-01T00:00:00Z"): pd.Series({"BTC": -1.0})}

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
            short_stop_loss_pct=0.2005,
            contract_specs={
                "BTC": ContractSpec(
                    symbol="BTCUSDT",
                    min_order_qty=0.001,
                    quantity_multiplier=0.001,
                    min_order_usdt=5.0,
                    quantity_precision=3,
                    price_multiplier=0.1,
                    price_precision=1,
                )
            },
        ),
    )

    stop = result.trades.loc[result.trades["reason"] == "stop_loss"].iloc[0]
    assert stop["price"] == pytest.approx(120.1)


def test_short_stop_loss_rejects_invalid_percentage() -> None:
    with pytest.raises(ValueError, match="short_stop_loss_pct"):
        DerivativeBacktestConfig(short_stop_loss_pct=1.0)


def test_short_stop_does_not_reopen_within_explicit_reversal_window() -> None:
    index = pd.date_range("2026-01-01T00:00:00Z", periods=96, freq="1h", tz="UTC")
    candles = {
        "A": _flat_frame(index),
        "B": _flat_frame(index),
    }
    candles["A"].loc[pd.Timestamp("2026-01-02T04:00:00Z"), ["open", "high", "low", "close"]] = [
        100.0,
        125.0,
        100.0,
        125.0,
    ]
    targets = {
        pd.Timestamp("2026-01-01T00:00:00Z"): pd.Series({"A": -0.50}),
        pd.Timestamp("2026-01-02T00:00:00Z"): pd.Series({"A": -0.50, "B": 0.01}),
    }
    config = DerivativeBacktestConfig(
        initial_capital=1_000.0,
        taker_fee_bps=0.0,
        slippage_bps=0.0,
        liquidation_slippage_bps=0.0,
        fee_buffer=0.0,
        short_stop_loss_pct=0.20,
        short_stop_reentry_block_windows=(
            ("A", pd.Timestamp("2026-01-02T03:00:00Z"), pd.Timestamp("2026-01-10T03:00:00Z")),
        ),
    )

    result = run_derivative_backtest(candles, targets, config=config)

    a_trades = result.trades[result.trades["asset"] == "A"]
    assert list(a_trades["action"]) == ["open", "close"]
    assert list(a_trades["reason"]) == ["rebalance", "stop_loss"]
    b_trades = result.trades[result.trades["asset"] == "B"]
    assert list(b_trades["action"]) == ["open"]


def test_short_reentry_block_window_validation() -> None:
    with pytest.raises(ValueError, match="start must precede end"):
        DerivativeBacktestConfig(
            short_stop_reentry_block_windows=(
                ("A", pd.Timestamp("2026-01-02T03:00:00Z"), pd.Timestamp("2026-01-01T03:00:00Z")),
            )
        )


def test_short_stop_reentry_can_rearm_after_daily_ma_confirmation() -> None:
    index = pd.date_range("2026-01-01T00:00:00Z", periods=30 * 24, freq="1h", tz="UTC")
    candles = {
        "A": _flat_frame(index),
        "B": _flat_frame(index),
    }
    # Stop on day 22, then keep the close above MA21 for one day and finally
    # close below it on day 24.  The next target change can then re-arm A.
    candles["A"].loc["2026-01-22T04:00:00Z", ["open", "high", "low", "close"]] = [
        100.0,
        125.0,
        100.0,
        110.0,
    ]
    candles["A"].loc["2026-01-23T00:00:00Z":"2026-01-24T23:00:00Z", ["open", "high", "low", "close"]] = 105.0
    candles["A"].loc["2026-01-24T00:00:00Z":"2026-01-24T23:00:00Z", ["open", "high", "low", "close"]] = 90.0
    targets = {
        pd.Timestamp("2026-01-01T00:00:00Z"): pd.Series({"A": -0.50}),
        pd.Timestamp("2026-01-22T00:00:00Z"): pd.Series({"A": -0.50, "B": 0.01}),
        pd.Timestamp("2026-01-24T00:00:00Z"): pd.Series({"A": -0.50, "B": 0.02}),
    }
    config = DerivativeBacktestConfig(
        initial_capital=1_000.0,
        taker_fee_bps=0.0,
        slippage_bps=0.0,
        liquidation_slippage_bps=0.0,
        fee_buffer=0.0,
        short_stop_loss_pct=0.20,
        short_stop_reentry_block_windows=(
            ("A", pd.Timestamp("2026-01-22T03:00:00Z"), pd.Timestamp("2026-02-10T03:00:00Z")),
        ),
        short_stop_reentry_rearm_ma_days=21,
    )

    result = run_derivative_backtest(candles, targets, config=config)

    a_trades = result.trades[result.trades["asset"] == "A"]
    assert list(a_trades["action"]) == ["open", "close", "open"]
    assert list(a_trades["reason"]) == ["rebalance", "stop_loss", "rebalance"]


def test_short_stop_reentry_can_rearm_after_close_falls_below_stop_price() -> None:
    index = pd.date_range("2026-01-01T00:00:00Z", periods=30 * 24, freq="1h", tz="UTC")
    candles = {
        "A": _flat_frame(index),
        "B": _flat_frame(index),
    }
    candles["A"].loc["2026-01-22T04:00:00Z", ["open", "high", "low", "close"]] = [
        100.0,
        130.0,
        100.0,
        126.0,
    ]
    candles["A"].loc["2026-01-22T05:00:00Z":"2026-01-22T23:00:00Z", ["open", "high", "low", "close"]] = 126.0
    candles["A"].loc["2026-01-23T00:00:00Z":"2026-01-23T23:00:00Z", ["open", "high", "low", "close"]] = 126.0
    candles["A"].loc["2026-01-24T00:00:00Z":"2026-01-24T23:00:00Z", ["open", "high", "low", "close"]] = 110.0
    targets = {
        pd.Timestamp("2026-01-01T00:00:00Z"): pd.Series({"A": -0.50}),
        pd.Timestamp("2026-01-22T00:00:00Z"): pd.Series({"A": -0.50, "B": 0.01}),
        pd.Timestamp("2026-01-24T00:00:00Z"): pd.Series({"A": -0.50, "B": 0.02}),
    }
    config = DerivativeBacktestConfig(
        initial_capital=1_000.0,
        taker_fee_bps=0.0,
        slippage_bps=0.0,
        liquidation_slippage_bps=0.0,
        fee_buffer=0.0,
        short_stop_loss_pct=0.20,
        short_stop_reentry_block_windows=(
            ("A", pd.Timestamp("2026-01-22T03:00:00Z"), pd.Timestamp("2026-02-10T03:00:00Z")),
        ),
        short_stop_reentry_rearm_below_stop=True,
    )

    result = run_derivative_backtest(candles, targets, config=config)

    a_trades = result.trades[result.trades["asset"] == "A"]
    assert list(a_trades["action"]) == ["open", "close", "open"]
    assert list(a_trades["reason"]) == ["rebalance", "stop_loss", "rebalance"]


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


def test_contract_quantity_is_floored_to_the_venue_step() -> None:
    index = pd.date_range("2026-11-13T00:00:00Z", "2026-11-15T03:00:00Z", freq="1h")
    candles = {"BTC": _flat_frame(index, value=101.0)}
    targets = {pd.Timestamp("2026-11-13T00:00:00Z"): pd.Series({"BTC": 0.5})}

    result = run_derivative_backtest(
        candles,
        targets,
        config=DerivativeBacktestConfig(
            initial_capital=1_000.0,
            taker_fee_bps=0.0,
            slippage_bps=0.0,
            liquidation_slippage_bps=0.0,
            execution_hour=1,
            execution_minute=5,
            execution_price_snap="floor",
            contract_specs={
                "BTC": ContractSpec(
                    "BTCUSDT",
                    min_order_qty=1.0,
                    quantity_multiplier=1.0,
                )
            },
        ),
    )

    trade = result.trades.iloc[0]
    quantization = result.order_quantizations.iloc[0]
    assert trade["quantity"] == pytest.approx(4.0)
    assert quantization["requested_quantity"] == pytest.approx(500.0 / 101.0)
    assert quantization["quantized_quantity"] == pytest.approx(4.0)
    assert quantization["quantity_error"] == pytest.approx(500.0 / 101.0 - 4.0)


def test_open_below_the_venue_minimum_is_skipped_and_audited() -> None:
    index = pd.date_range("2026-11-13T00:00:00Z", "2026-11-15T03:00:00Z", freq="1h")
    candles = {"BTC": _flat_frame(index, value=100.0)}
    targets = {pd.Timestamp("2026-11-13T00:00:00Z"): pd.Series({"BTC": 0.1})}

    result = run_derivative_backtest(
        candles,
        targets,
        config=DerivativeBacktestConfig(
            initial_capital=1_000.0,
            taker_fee_bps=0.0,
            slippage_bps=0.0,
            liquidation_slippage_bps=0.0,
            fee_buffer=0.0,
            execution_hour=1,
            execution_minute=5,
            execution_price_snap="floor",
            contract_specs={
                "BTC": ContractSpec(
                    "BTCUSDT",
                    min_order_qty=0.0,
                    quantity_multiplier=0.0,
                    min_order_usdt=500.0,
                )
            },
        ),
    )

    assert result.trades.empty
    assert len(result.order_skips) == 1
    assert result.order_skips.iloc[0]["reason"] == "below_venue_minimum"


def test_full_close_is_allowed_below_the_venue_minimum() -> None:
    index = pd.date_range("2026-11-13T00:00:00Z", "2026-11-17T03:00:00Z", freq="1h")
    candles = {"BTC": _flat_frame(index, value=100.0)}
    candles["BTC"].loc[index >= pd.Timestamp("2026-11-15T00:00:00Z"), ["open", "high", "low", "close"]] = 80.0
    targets = {
        pd.Timestamp("2026-11-13T00:00:00Z"): pd.Series({"BTC": 0.5}),
        pd.Timestamp("2026-11-15T00:00:00Z"): pd.Series(dtype=float),
    }

    result = run_derivative_backtest(
        candles,
        targets,
        config=DerivativeBacktestConfig(
            initial_capital=1_000.0,
            taker_fee_bps=0.0,
            slippage_bps=0.0,
            liquidation_slippage_bps=0.0,
            fee_buffer=0.0,
            long_buffer=0.50,
            execution_hour=1,
            execution_minute=5,
            execution_price_snap="floor",
            contract_specs={
                "BTC": ContractSpec(
                    "BTCUSDT",
                    min_order_qty=0.0,
                    quantity_multiplier=0.0,
                    min_order_usdt=500.0,
                )
            },
        ),
    )

    assert list(result.trades["action"]) == ["open", "close"]


def test_daily_margin_normalization_adds_and_removes_without_changing_equity() -> None:
    index = pd.date_range("2026-11-13T00:00:00Z", "2026-11-18T03:00:00Z", freq="1h")
    candles = {"BTC": _flat_frame(index, value=100.0)}
    candles["BTC"].loc[index >= pd.Timestamp("2026-11-15T00:00:00Z"), ["open", "high", "low", "close"]] = 120.0
    candles["BTC"].loc[index >= pd.Timestamp("2026-11-16T00:00:00Z"), ["open", "high", "low", "close"]] = 80.0
    targets = {
        pd.Timestamp(day): pd.Series({"BTC": 0.5})
        for day in ("2026-11-13", "2026-11-14", "2026-11-15", "2026-11-16")
    }

    result = run_derivative_backtest(
        candles,
        targets,
        config=DerivativeBacktestConfig(
            initial_capital=1_000.0,
            taker_fee_bps=0.0,
            slippage_bps=0.0,
            liquidation_slippage_bps=0.0,
            long_buffer=0.50,
            execution_hour=1,
            execution_minute=5,
            execution_price_snap="floor",
            normalize_isolated_margin="daily",
        ),
    )

    assert list(result.margin_events["operation"]) == ["add", "remove"]
    assert result.margin_events["amount"].tolist() == pytest.approx([51.5, 103.0])
    for row in result.margin_events.itertuples(index=False):
        assert row.equity_before == pytest.approx(row.equity_after)
        expected_cash_delta = -row.amount if row.operation == "add" else row.amount
        assert row.cash_after - row.cash_before == pytest.approx(expected_cash_delta)


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
                execution_price_snap="ceil",
            ),
            start_time=pd.Timestamp("2026-01-01T00:00:00Z"),
            end_time=pd.Timestamp("2026-01-05T00:00:00Z"),
        )


def test_0105_execution_floors_to_the_containing_hourly_mark_bar() -> None:
    index = pd.date_range("2026-11-13T00:00:00Z", "2026-11-15T03:00:00Z", freq="1h")
    candles = {"BTC": _flat_frame(index)}
    targets = {pd.Timestamp("2026-11-13T00:00:00Z"): pd.Series({"BTC": 1.0})}

    result = run_derivative_backtest(
        candles,
        targets,
        config=DerivativeBacktestConfig(
            initial_capital=1_000.0,
            taker_fee_bps=0.0,
            slippage_bps=0.0,
            liquidation_slippage_bps=0.0,
            fee_buffer=0.0,
            execution_hour=1,
            execution_minute=5,
            execution_price_snap="floor",
        ),
    )

    assert result.trades.iloc[0]["timestamp"] == pd.Timestamp("2026-11-14T01:00:00Z")


def test_0105_exact_execution_requires_an_exact_minute_bar() -> None:
    index = pd.date_range("2026-11-13T00:00:00Z", "2026-11-15T03:00:00Z", freq="1h")
    candles = {"BTC": _flat_frame(index)}
    targets = {pd.Timestamp("2026-11-13T00:00:00Z"): pd.Series({"BTC": 1.0})}

    with pytest.raises(ValueError, match="no exact mark candle"):
        run_derivative_backtest(
            candles,
            targets,
            config=DerivativeBacktestConfig(
                initial_capital=1_000.0,
                taker_fee_bps=0.0,
                slippage_bps=0.0,
                liquidation_slippage_bps=0.0,
                fee_buffer=0.0,
                execution_hour=1,
                execution_minute=5,
                execution_price_snap="exact",
            ),
        )


def test_missing_execution_hour_does_not_silently_use_a_multi_hour_carry() -> None:
    index = pd.DatetimeIndex(["2026-11-13T23:00:00Z"])
    candles = {"BTC": _flat_frame(index)}
    targets = {pd.Timestamp("2026-11-13T00:00:00Z"): pd.Series({"BTC": 1.0})}

    with pytest.raises(ValueError, match="within one hour"):
        run_derivative_backtest(
            candles,
            targets,
            config=DerivativeBacktestConfig(
                initial_capital=1_000.0,
                taker_fee_bps=0.0,
                slippage_bps=0.0,
                liquidation_slippage_bps=0.0,
                fee_buffer=0.0,
                execution_hour=1,
                execution_minute=5,
                execution_price_snap="floor",
                missing_mark_policy="carry",
                missing_mark_max_carry_hours=3,
            ),
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


def test_fill_hour_hole_slides_to_the_next_candle_within_one_hour() -> None:
    """A missing candle at the fill hour is filled one hour later, explicitly."""

    import pandas as pd

    from atlas20.derivatives.engine import (
        DerivativeBacktestConfig,
        run_derivative_backtest,
    )

    # 03:00 is missing (a provider hole) but 04:00 exists, so the 09-01 fill for
    # the 08-31 signal must land at 04:00 and be visible in the trade ledger.
    index = pd.date_range("2026-08-31 00:00", periods=48, freq="1h", tz="UTC").drop(
        pd.Timestamp("2026-09-01 03:00", tz="UTC")
    )
    frame = pd.DataFrame({"open": 1.0, "high": 1.0, "low": 1.0, "close": 1.0}, index=index)
    targets = {pd.Timestamp("2026-08-31 00:00", tz="UTC"): pd.Series({"a": 1.0})}

    result = run_derivative_backtest(
        {"a": frame},
        targets,
        config=DerivativeBacktestConfig(
            missing_mark_policy="carry",
            execution_price_snap="ceil",
        ),
    )

    opens = result.trades.loc[result.trades["action"] == "open"]
    assert len(opens) == 1
    assert pd.Timestamp(opens["timestamp"].iloc[0]) == pd.Timestamp("2026-09-01 04:00", tz="UTC")


def test_hard_gross_guard_reduces_on_the_next_bar_after_a_mark_drift() -> None:
    index = pd.date_range("2026-01-01T00:00:00Z", periods=8, freq="1h", tz="UTC")
    candles = {"BTC": _flat_frame(index)}
    candles["BTC"].loc[pd.Timestamp("2026-01-01T02:00:00Z"), ["open", "high", "low", "close"]] = [
        100.0,
        130.0,
        100.0,
        130.0,
    ]
    candles["BTC"].loc[index >= pd.Timestamp("2026-01-01T03:00:00Z"), ["open", "high", "low", "close"]] = 130.0
    targets = {pd.Timestamp("2026-01-01T00:00:00Z"): pd.Series({"BTC": -0.95})}

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
            execution_lag_days=0,
            execution_hour=0,
            max_gross_exposure=0.90,
            hard_gross_exposure=1.00,
        ),
    )

    assert result.gross_exposure.loc[pd.Timestamp("2026-01-01T02:00:00Z")] > 1.0
    guard = result.trades[result.trades["reason"] == "gross_guard"]
    assert len(guard) == 1
    assert guard.iloc[0]["timestamp"] == pd.Timestamp("2026-01-01T03:00:00Z")
    assert guard.iloc[0]["side"] == "short"
    assert result.gross_exposure.loc[pd.Timestamp("2026-01-01T03:00:00Z")] <= 0.91


def test_hard_gross_guard_must_not_be_below_target_gross() -> None:
    with pytest.raises(ValueError, match="hard_gross_exposure"):
        DerivativeBacktestConfig(max_gross_exposure=0.95, hard_gross_exposure=0.90)

    config = DerivativeBacktestConfig(max_gross_exposure=0.95, hard_gross_exposure=0.95)
    assert config.hard_gross_exposure == config.max_gross_exposure


def test_no_trade_band_skips_small_same_side_rebalance() -> None:
    index = pd.date_range("2026-01-01T00:00:00Z", "2026-01-04T05:00:00Z", freq="1h", tz="UTC")
    candles = {"BTC": _flat_frame(index)}
    targets = {
        pd.Timestamp("2026-01-01T00:00:00Z"): pd.Series({"BTC": 0.10}),
        pd.Timestamp("2026-01-02T00:00:00Z"): pd.Series({"BTC": 0.12}),
        pd.Timestamp("2026-01-03T00:00:00Z"): pd.Series({"BTC": 0.16}),
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
            max_margin_utilization=1.0,
            rebalance_no_trade_band=0.05,
        ),
    )

    assert result.trades["action"].tolist() == ["open", "increase"]
    assert result.positions.iloc[-1]["notional"] == pytest.approx(110.0)


def test_no_trade_band_reduces_only_to_the_lower_boundary() -> None:
    index = pd.date_range("2026-01-01T00:00:00Z", "2026-01-03T05:00:00Z", freq="1h", tz="UTC")
    candles = {"BTC": _flat_frame(index)}
    targets = {
        pd.Timestamp("2026-01-01T00:00:00Z"): pd.Series({"BTC": 0.10}),
        pd.Timestamp("2026-01-02T00:00:00Z"): pd.Series({"BTC": 0.02}),
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
            max_margin_utilization=1.0,
            rebalance_no_trade_band=0.05,
        ),
    )

    reduction = result.trades[result.trades["action"] == "reduce"].iloc[0]
    assert reduction["notional"] == pytest.approx(30.0)


def test_no_trade_band_never_blocks_a_full_exit() -> None:
    index = pd.date_range("2026-01-01T00:00:00Z", "2026-01-03T05:00:00Z", freq="1h", tz="UTC")
    candles = {"BTC": _flat_frame(index)}
    targets = {
        pd.Timestamp("2026-01-01T00:00:00Z"): pd.Series({"BTC": 0.10}),
        pd.Timestamp("2026-01-02T00:00:00Z"): pd.Series(dtype=float),
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
            max_margin_utilization=1.0,
            rebalance_no_trade_band=0.05,
        ),
    )

    assert result.trades["action"].tolist() == ["open", "close"]


def test_no_trade_band_falls_back_to_exact_targets_before_a_gross_breach() -> None:
    index = pd.date_range("2026-01-01T00:00:00Z", "2026-01-03T05:00:00Z", freq="1h", tz="UTC")
    candles = {"A": _flat_frame(index), "B": _flat_frame(index)}
    targets = {
        pd.Timestamp("2026-01-01T00:00:00Z"): pd.Series({"A": 0.60}),
        pd.Timestamp("2026-01-02T00:00:00Z"): pd.Series({"A": 0.10, "B": 0.90}),
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
            max_margin_utilization=1.0,
            max_gross_exposure=1.0,
            rebalance_no_trade_band=0.05,
        ),
    )

    at_second_target = pd.Timestamp("2026-01-03T03:00:00Z")
    assert result.gross_exposure.loc[at_second_target] == pytest.approx(1.0)
    assert result.trades.loc[result.trades["asset"] == "A", "action"].tolist() == [
        "open",
        "reduce",
    ]
    a_reduction = result.trades[
        (result.trades["timestamp"] == at_second_target) & (result.trades["action"] == "reduce")
    ].iloc[0]
    assert a_reduction["notional"] == pytest.approx(500.0)


def test_no_trade_band_must_be_below_one_hundred_percent() -> None:
    with pytest.raises(ValueError, match="rebalance_no_trade_band"):
        DerivativeBacktestConfig(rebalance_no_trade_band=1.0)


def test_long_stop_loss_closes_before_isolated_liquidation() -> None:
    index = pd.date_range("2026-01-01 00:00:00Z", "2026-01-02 05:00:00Z", freq="1h", tz="UTC")
    candles = {"BTC": _flat_frame(index)}
    candles["BTC"].loc[pd.Timestamp("2026-01-02T04:00:00Z"), ["open", "high", "low", "close"]] = [
        100.0,
        100.0,
        75.0,
        75.0,
    ]
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
            long_buffer=0.50,
            long_stop_loss_pct=0.20,
        ),
    )

    assert result.liquidations.empty
    stops = result.trades[result.trades["reason"] == "stop_loss"]
    assert len(stops) == 1
    assert stops.iloc[0]["side"] == "long"
    assert stops.iloc[0]["price"] == pytest.approx(80.0)
    assert result.equity_curve.iloc[-1] == pytest.approx(800.0)


def test_long_stop_loss_rejects_invalid_percentage() -> None:
    with pytest.raises(ValueError, match="long_stop_loss_pct"):
        DerivativeBacktestConfig(long_stop_loss_pct=1.0)
