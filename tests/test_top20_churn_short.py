from __future__ import annotations

import numpy as np
import pandas as pd
import pytest


def test_churn_targets_are_market_neutral_and_gross_one(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    import scripts.run_top20_churn_short as module

    index = pd.date_range("2022-01-01", periods=5, freq="D", tz="UTC")
    present = pd.DataFrame(True, index=index, columns=["a", "b", "c"])
    events = pd.DataFrame(
        [
            {"coin_id": "a", "event_date": index[1], "event_type": "entry", "confirmation_days": 3},
            {"coin_id": "b", "event_date": index[1], "event_type": "exit", "confirmation_days": 3},
        ]
    )
    monkeypatch.setattr(module, "detect_membership_events", lambda *_args, **_kwargs: events)

    targets = module.build_churn_targets(
        present=present,
        confirmation_days=3,
        assets=["a", "b", "c"],
    )

    row = targets.loc[index[1]]
    assert row.sum() == pytest.approx(0.0)
    assert row.abs().sum() == pytest.approx(1.0)
    assert row["bitcoin"] == pytest.approx(0.5)
    assert row[["a", "b"]].tolist() == pytest.approx([-0.25, -0.25])


def test_churn_backtest_keeps_gross_at_one() -> None:
    from scripts.run_daily_btc_shock_continuation import backtest_continuation

    index = pd.date_range("2022-01-01", periods=8, freq="D", tz="UTC")
    returns = pd.DataFrame(0.0, index=index, columns=["bitcoin", "a", "b"])
    targets = pd.DataFrame(0.0, index=index, columns=returns.columns)
    targets.loc[index[1], ["bitcoin", "a", "b"]] = [0.5, -0.25, -0.25]

    result = backtest_continuation(
        index=index,
        returns=returns,
        targets=targets,
        horizon=3,
        cost_bps=0.0,
    )

    assert result.gross_exposure.max() == pytest.approx(1.0 / 3.0)
    assert np.isfinite(result.daily_returns).all()
