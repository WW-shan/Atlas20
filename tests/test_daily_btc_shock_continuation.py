from __future__ import annotations

import numpy as np
import pandas as pd
import pytest


def test_continuation_book_longs_high_gap_and_shorts_low_gap() -> None:
    from scripts.run_daily_btc_shock_continuation import continuation_book

    gap = pd.Series(
        {
            "a": -0.10,
            "b": -0.05,
            "c": 0.01,
            "d": 0.02,
            "e": 0.06,
            "f": 0.10,
            "g": 0.12,
            "h": 0.20,
        }
    )
    eligible = pd.Series(True, index=gap.index)

    book = continuation_book(gap, eligible, tail_fraction=0.25)

    assert book is not None
    assert book.loc[["g", "h"]].tolist() == pytest.approx([0.25, 0.25])
    assert book.loc[["a", "b"]].tolist() == pytest.approx([-0.25, -0.25])
    assert float(book.sum()) == pytest.approx(0.0)
    assert float(book.abs().sum()) == pytest.approx(1.0)


def test_continuation_book_rejects_small_cross_section() -> None:
    from scripts.run_daily_btc_shock_continuation import continuation_book

    gap = pd.Series({"a": -0.1, "b": 0.0, "c": 0.1})

    assert continuation_book(gap, pd.Series(True, index=gap.index), 0.2) is None


def test_held_phase_weights_enter_after_next_close_and_stay_capped() -> None:
    from scripts.run_daily_btc_shock_continuation import held_phase_weights

    index = pd.date_range("2022-01-01", periods=6, freq="D", tz="UTC")
    targets = pd.DataFrame(
        {"a": [0.5, 0.5, 0.5, 0.5, 0.5, 0.5], "b": [-0.5] * 6},
        index=index,
    )

    weights = held_phase_weights(index, targets, horizon=2)

    # Signal on day 0 executes at day 1's close, so it first earns day 2's return.
    assert weights.loc[index[1]].abs().sum() == pytest.approx(0.0)
    assert weights.loc[index[2], "a"] == pytest.approx(0.25)
    assert weights.loc[index[3], "a"] == pytest.approx(0.5)
    assert (weights.abs().sum(axis=1) <= 1.0 + 1e-12).all()
    # The final tranche is still marked at the last close; backtest explicitly
    # charges its liquidation rather than pretending it disappeared for free.
    assert weights.loc[index[-1]].abs().sum() == pytest.approx(0.5)


def test_continuation_backtest_charges_entry_and_exit_turnover() -> None:
    from scripts.run_daily_btc_shock_continuation import backtest_continuation

    index = pd.date_range("2022-01-01", periods=6, freq="D", tz="UTC")
    returns = pd.DataFrame(0.0, index=index, columns=["a", "b"])
    targets = pd.DataFrame(
        {"a": [0.5, 0.5, 0.5, 0.5, 0.5, 0.5], "b": [-0.5] * 6},
        index=index,
    )

    result = backtest_continuation(
        index=index,
        returns=returns,
        targets=targets,
        horizon=2,
        cost_bps=10.0,
    )

    # Each 1/h tranche has gross 0.5 and two overlapping tranches reach gross
    # 1.0; four entry/exit notional crossings total 2.0 of one-way turnover.
    assert result.turnover.sum() == pytest.approx(2.0)
    assert result.daily_returns.sum() == pytest.approx(-0.002)
    assert result.gross_exposure.max() == pytest.approx(1.0)


def test_continuation_backtest_can_normalize_active_gross_to_one() -> None:
    from scripts.run_daily_btc_shock_continuation import backtest_continuation

    index = pd.date_range("2022-01-01", periods=6, freq="D", tz="UTC")
    returns = pd.DataFrame(0.0, index=index, columns=["a", "b"])
    targets = pd.DataFrame(0.0, index=index, columns=returns.columns)
    targets.loc[index[0], ["a", "b"]] = [0.5, -0.5]

    result = backtest_continuation(
        index=index,
        returns=returns,
        targets=targets,
        horizon=2,
        cost_bps=0.0,
        normalize_gross=True,
    )

    assert result.gross_exposure.max() == pytest.approx(1.0)
    assert result.gross_exposure.loc[index[2:4]].tolist() == pytest.approx([1.0, 1.0])


def test_select_candidate_uses_only_discovery_metrics() -> None:
    from scripts.run_daily_btc_shock_continuation import select_candidate

    summary = pd.DataFrame(
        [
            {
                "variant_id": "good",
                "discovery_sharpe_20": 1.0,
                "discovery_sharpe_50": 0.4,
                "validation_sharpe_20": -9.0,
                "turnover_20": 10.0,
            },
            {
                "variant_id": "high-validation-low-discovery",
                "discovery_sharpe_20": 0.2,
                "discovery_sharpe_50": 0.1,
                "validation_sharpe_20": 9.0,
                "turnover_20": 1.0,
            },
            {
                "variant_id": "cost-fragile",
                "discovery_sharpe_20": 2.0,
                "discovery_sharpe_50": -0.1,
                "validation_sharpe_20": 9.0,
                "turnover_20": 20.0,
            },
        ]
    )

    assert select_candidate(summary) == "good"


def test_parse_shock_bucket() -> None:
    from scripts.run_daily_btc_shock_continuation import shock_gate_passes

    z = pd.Series([-2.4, -1.0, 0.0, 2.1, np.nan])

    assert shock_gate_passes(z, "all").tolist() == [True, True, True, True, False]
    assert shock_gate_passes(z, "abs_z_ge_2_0").tolist() == [
        True,
        False,
        False,
        True,
        False,
    ]
