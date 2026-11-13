from __future__ import annotations

import pandas as pd
import pytest


def test_variant_specs_are_the_frozen_twelve_cell_grid() -> None:
    from scripts.run_residual_horizon_scan import variant_specs

    variants = variant_specs()

    assert len(variants) == 12
    assert len({variant.variant_id for variant in variants}) == 12
    assert {(variant.lookback_days, variant.skip_days, variant.direction) for variant in variants} == {
        (lookback, skip, direction)
        for lookback in (63, 126, 252)
        for skip in (0, 21)
        for direction in (1, -1)
    }


def test_slice_returns_is_inclusive_and_timezone_aware() -> None:
    from scripts.run_residual_horizon_scan import slice_returns

    index = pd.date_range("2026-01-01", periods=5, freq="D", tz="UTC")
    returns = pd.Series(range(5), index=index, dtype=float)

    sliced = slice_returns(returns, "2026-01-02", "2026-01-04")

    assert sliced.index.tolist() == list(index[1:4])


def test_tier_for_variant_requires_discovery_and_validation_strength() -> None:
    from scripts.run_residual_horizon_scan import tier_for_variant

    passing = tier_for_variant(
        full_20={"multiple": 1.5, "sharpe": 1.0},
        discovery_20={"multiple": 1.2, "sharpe": 0.7},
        validation_20={"multiple": 1.1, "sharpe": 0.6},
        full_50={"multiple": 1.05},
    )
    watch = tier_for_variant(
        full_20={"multiple": 1.1, "sharpe": 0.4},
        discovery_20={"multiple": 1.2, "sharpe": 0.3},
        validation_20={"multiple": 1.1, "sharpe": 0.2},
        full_50={"multiple": 1.05},
    )
    rejected = tier_for_variant(
        full_20={"multiple": 0.9, "sharpe": 0.2},
        discovery_20={"multiple": 1.1, "sharpe": 0.2},
        validation_20={"multiple": 0.8, "sharpe": 0.1},
        full_50={"multiple": 0.8},
    )

    assert passing == "candidate-for-integration"
    assert watch == "watch"
    assert rejected == "rejected-now"


def test_realized_market_beta_recovers_a_known_exposure() -> None:
    from scripts.run_residual_horizon_scan import realized_market_beta

    index = pd.date_range("2026-01-01", periods=5, freq="D", tz="UTC")
    bitcoin = pd.Series([0.0, 0.01, -0.02, 0.03, 0.01], index=index)
    strategy = 2.0 * bitcoin

    assert realized_market_beta(strategy, bitcoin) == pytest.approx(2.0)


def test_ranking_rows_read_asset_names_from_the_contribution_index() -> None:
    from scripts.run_residual_horizon_scan import _ranking_rows, variant_specs

    variant = variant_specs()[0]
    metrics = {"multiple": 1.0, "sharpe": 0.5, "max_drawdown": -0.2}
    by_variant = {
        variant.variant_id: {
            sample: {cost: metrics for cost in (20.0, 50.0)}
            for sample in ("full", "discovery", "validation", "latest")
        }
    }
    contributions = {
        variant.variant_id: pd.DataFrame(
            {
                "cumulative_contribution": [0.2, -0.1],
                "absolute_share": [2 / 3, 1 / 3],
            },
            index=pd.Index(["A", "B"], name="asset"),
        )
    }

    rows = _ranking_rows((variant,), by_variant, contributions)

    assert rows[0]["top_positive_assets"].split(", ") == ["A", "B"]
    assert rows[0]["top_negative_assets"].split(", ") == ["B", "A"]
