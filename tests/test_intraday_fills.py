from __future__ import annotations

import pandas as pd
import pytest

from atlas20.backtest.intraday import load_hourly_bars, observed_fill_mask, pre_fill_returns


def test_load_hourly_bars_follows_the_coverage_manifest(tmp_path) -> None:
    pd.DataFrame(
        {"open_time": ["2024-01-02T00:00:00+00:00"], "open": [100.0], "close": [101.0]}
    ).to_csv(tmp_path / "AUSDT.csv", index=False)
    pd.DataFrame(
        {"open_time": ["2024-01-02T00:00:00+00:00"], "open": [5.0], "close": [6.0]}
    ).to_csv(tmp_path / "gate_C_USDT.csv", index=False)
    (tmp_path / "coverage.json").write_text(
        '{"a": {"pair": "AUSDT", "available": true}, "b": {"pair": "BUSDT", "available": false},'
        ' "c": {"venue": "gate", "pair": "C_USDT", "file": "gate_C_USDT.csv", "available": true}}',
        encoding="utf-8",
    )

    bars = load_hourly_bars(tmp_path)

    assert set(bars) == {"a", "c"}
    assert bars["c"]["close"].tolist() == [6.0]
    assert bars["a"]["close"].tolist() == [101.0]
    assert str(bars["a"]["open_time"].dt.tz) == "UTC"


def _hourly(day: str, closes: list[float], opening: float) -> pd.DataFrame:
    """Hourly bars for one UTC day, indexed by bar open time."""
    start = pd.Timestamp(day, tz="UTC")
    return pd.DataFrame(
        {
            "open_time": [start + pd.Timedelta(hours=hour) for hour in range(len(closes))],
            "open": [opening] + closes[:-1],
            "close": closes,
        }
    )


def test_pre_fill_return_runs_from_the_prior_close_to_the_fill_hour() -> None:
    dates = pd.to_datetime(["2024-01-01", "2024-01-02"])
    daily = pd.DataFrame({"a": [0.0, 0.10]}, index=dates)
    # Day 2 opens at 100 (the 2024-01-01 close) and trades up through the morning.
    hourly = {"a": _hourly("2024-01-02", [101.0, 102.0, 104.0, 105.0], opening=100.0)}

    result = pre_fill_returns(daily, hourly, fill_hours=3)

    # Fill at the close of the 02:00 bar: 104 / 100 - 1.
    assert result.loc[dates[1], "a"] == pytest.approx(0.04)


def test_fill_at_the_close_itself_has_no_pre_fill_move() -> None:
    dates = pd.to_datetime(["2024-01-01", "2024-01-02"])
    daily = pd.DataFrame({"a": [0.0, 0.10]}, index=dates)
    hourly = {"a": _hourly("2024-01-02", [101.0, 102.0], opening=100.0)}

    result = pre_fill_returns(daily, hourly, fill_hours=0)

    assert result.loc[dates[1], "a"] == 0.0


def test_missing_candles_assume_the_fill_waits_for_the_next_close() -> None:
    dates = pd.to_datetime(["2024-01-01", "2024-01-02"])
    daily = pd.DataFrame({"a": [0.0, 0.10], "unlisted": [0.0, -0.05]}, index=dates)
    hourly = {"a": _hourly("2024-01-02", [101.0], opening=100.0)}

    result = pre_fill_returns(daily, hourly, fill_hours=3)

    # "a" lacks the 02:00 bar and "unlisted" has no candles at all: by default
    # both take the whole day's move before the fill.
    assert result.loc[dates[1], "a"] == pytest.approx(0.10)
    assert result.loc[dates[1], "unlisted"] == pytest.approx(-0.05)


def test_prior_close_policy_brackets_coins_without_candles() -> None:
    dates = pd.to_datetime(["2024-01-01", "2024-01-02"])
    daily = pd.DataFrame({"a": [0.0, 0.10], "unlisted": [0.0, -0.05]}, index=dates)
    hourly = {"a": _hourly("2024-01-02", [101.0, 102.0, 104.0], opening=100.0)}

    result = pre_fill_returns(daily, hourly, fill_hours=3, missing_fill="prior_close")

    # Observed coins still use their candles; an unobserved coin is assumed
    # to fill at the prior close, the other end of the bracket.
    assert result.loc[dates[1], "a"] == pytest.approx(0.04)
    assert result.loc[dates[1], "unlisted"] == 0.0


def test_unknown_missing_fill_policy_is_rejected() -> None:
    dates = pd.to_datetime(["2024-01-01", "2024-01-02"])
    daily = pd.DataFrame({"a": [0.0, 0.10]}, index=dates)

    with pytest.raises(ValueError, match="missing_fill"):
        pre_fill_returns(daily, {}, fill_hours=3, missing_fill="guess")


def test_candles_that_disagree_with_the_prior_close_are_not_trusted() -> None:
    dates = pd.to_datetime(["2024-01-01", "2024-01-02", "2024-01-03"])
    daily = pd.DataFrame({"a": [0.0, 0.10, 0.10]}, index=dates)
    closes = pd.DataFrame({"a": [100.0, 110.0, 121.0]}, index=dates)
    hourly = {
        "a": pd.concat(
            [
                # Opens at the panel's prior close (100): trusted.
                _hourly("2024-01-02", [101.0, 102.0, 104.0], opening=100.0),
                # Opens 20% away from the panel's prior close (110): a
                # different listing or a bad print, so the day is unobserved.
                _hourly("2024-01-03", [133.0, 134.0, 135.0], opening=132.0),
            ],
            ignore_index=True,
        )
    }

    result = pre_fill_returns(daily, hourly, fill_hours=3, reference_close=closes)

    assert result.loc[dates[1], "a"] == pytest.approx(0.04)
    assert result.loc[dates[2], "a"] == pytest.approx(0.10)


def test_observed_fill_mask_marks_cells_the_candles_can_show() -> None:
    dates = pd.to_datetime(["2024-01-01", "2024-01-02"])
    daily = pd.DataFrame({"a": [0.0, 0.10], "unlisted": [0.0, -0.05]}, index=dates)
    hourly = {"a": _hourly("2024-01-02", [101.0, 102.0, 104.0], opening=100.0)}

    mask = observed_fill_mask(daily, hourly, fill_hours=3)

    assert mask.loc[dates[1], "a"]
    assert not mask.loc[dates[0], "a"]
    assert not mask.loc[dates[1], "unlisted"]
