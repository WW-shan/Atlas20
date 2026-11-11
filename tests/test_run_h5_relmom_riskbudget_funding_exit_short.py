from __future__ import annotations

import pandas as pd
import pytest


def test_runner_freezes_relmom_candidate() -> None:
    from scripts.run_h5_relmom_riskbudget_funding_exit_short import (
        CANDIDATE_ID,
        FROZEN_CONFIG,
    )

    assert CANDIDATE_ID == "PR2026-11-LS10-H5-RELMOM14-RISKBUDGET-FUNDING-EXIT"
    assert FROZEN_CONFIG["base_short_per_asset_weight_at_zero_long"] == 0.05
    assert FROZEN_CONFIG["relative_lookback_days"] == 14
    assert FROZEN_CONFIG["relative_benchmark"] == "bitcoin"
    assert FROZEN_CONFIG["funding_lookback_days"] == 7
    assert FROZEN_CONFIG["funding_rank_min"] == pytest.approx(2 / 3)
    assert FROZEN_CONFIG["funding_min_assets"] == 5
    assert FROZEN_CONFIG["short_stop_loss_pct"] == 0.20
    assert FROZEN_CONFIG["max_total_gross"] == 0.95
    assert FROZEN_CONFIG["hard_gross"] == 1.00


def test_relative_momentum_uses_no_future_price_and_normalizes_utc() -> None:
    from scripts.run_h5_relmom_riskbudget_funding_exit_short import (
        _relative_momentum_allows,
    )

    index = pd.date_range("2022-01-01", periods=17, freq="D")
    prices = pd.DataFrame(
        {
            "asset": [100.0] + [100.0] * 14 + [90.0, 1000.0],
            "bitcoin": [100.0] + [100.0] * 14 + [110.0, 1000.0],
        },
        index=index,
    )

    assert _relative_momentum_allows(
        prices,
        "asset",
        pd.Timestamp("2022-01-16", tz="UTC"),
        lookback_days=14,
        benchmark="bitcoin",
    )


def test_relative_momentum_fails_closed_when_history_is_missing() -> None:
    from scripts.run_h5_relmom_riskbudget_funding_exit_short import (
        _relative_momentum_allows,
    )

    index = pd.date_range("2022-01-01", periods=5, freq="D", tz="UTC")
    prices = pd.DataFrame({"asset": [100.0] * 5, "bitcoin": [100.0] * 5}, index=index)

    assert not _relative_momentum_allows(
        prices,
        "asset",
        pd.Timestamp("2022-01-03", tz="UTC"),
        lookback_days=14,
        benchmark="bitcoin",
    )
