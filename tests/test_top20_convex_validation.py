from __future__ import annotations

import pandas as pd
import pytest

from atlas20.config import load_config
from atlas20.universe.builder import MarketDataBundle
from scripts.run_top20_convex_validation import (
    CandidateDefinition,
    _add_candidate_ids,
    build_candidate_definitions,
    compute_contribution_summary,
    compute_cost_sensitivity,
    compute_raw_convexity_score,
    compute_robust_convexity_score,
    compute_rolling_start_validation,
    compute_rolling_window_summary,
    compute_stability_surface,
    run_full_window_screen,
    run_one_candidate,
    select_validation_candidates,
)


def _script_toy_market() -> MarketDataBundle:
    dates = pd.date_range("2024-01-01", periods=100, freq="D")
    price = pd.DataFrame(
        {
            "bitcoin": [100 + i * 0.4 for i in range(100)],
            "ethereum": [80 + i * 0.2 for i in range(100)],
            "solana": [10 + i * 1.2 for i in range(100)],
            "chainlink": [20 + i * 0.15 for i in range(100)],
        },
        index=dates,
    )
    metadata = pd.DataFrame(
        {
            "sector": {
                "bitcoin": "Store of Value",
                "ethereum": "Smart Contract Platform / L1",
                "solana": "Smart Contract Platform / L1",
                "chainlink": "Infrastructure",
            }
        }
    )
    return MarketDataBundle(
        raw_price=price,
        price=price,
        returns=price.pct_change().fillna(0.0),
        market_cap=price * 1_000_000,
        volume=pd.DataFrame(1_000_000.0, index=dates, columns=price.columns),
        history_count=price.notna().cumsum(),
        metadata=metadata,
    )


def _script_toy_universe(dates: pd.DatetimeIndex) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for date in dates:
        for rank, coin_id in enumerate(["bitcoin", "ethereum", "solana", "chainlink"], start=1):
            rows.append(
                {
                    "rebalance_date": date,
                    "coin_id": coin_id,
                    "universe_rank": rank,
                    "price": 1.0,
                    "market_cap": 10_000_000 / rank,
                    "volume_usd": 1_000_000,
                    "history_days": 100,
                    "symbol": coin_id.upper(),
                    "name": coin_id,
                    "sector": "Layer1",
                }
            )
    return pd.DataFrame(rows)


def _script_config():
    config = load_config("config/base.yaml")
    config.start_date = "2024-03-01"
    config.rebalancing.frequencies["14D"] = "14D"
    return config


def _script_universe_by_liquidity() -> dict[str, pd.DataFrame]:
    return {"loose": _script_toy_universe(pd.date_range("2024-03-01", periods=4, freq="14D"))}


def _script_candidate(**overrides: object) -> CandidateDefinition:
    fields: dict[str, object] = {
        "candidate_id": "ctrend_lite_test",
        "family_id": "ctrend_lite",
        "strategy_kind": "ctrend_lite",
        "top_n": 1,
        "frequency": "14D",
        "score_family": "ctrend_lite_balanced",
        "liquidity_label": "loose",
        "min_history_days": 30,
        "min_daily_dollar_volume": 1_000_000.0,
        "include_btc": True,
        "overlay_set": "no_stop_control",
        "risk_off_asset": "cash",
        "initial_asset": "cash",
        "stop_kind": "none",
        "stop_lookback": None,
        "stop_confirm_days": 1,
        "ma_window": None,
    }
    fields.update(overrides)
    return CandidateDefinition(**fields)


def _stability_summary_row(**overrides: object) -> dict[str, object]:
    row: dict[str, object] = {
        "candidate_id": "a",
        "family_id": "ctrend_lite",
        "strategy_kind": "ctrend_lite",
        "score_family": "ctrend_lite_balanced",
        "include_btc": True,
        "liquidity_label": "loose",
        "top_n": 1,
        "frequency": "14D",
        "stop_kind": "trailing",
        "stop_lookback": 11,
        "stop_confirm_days": 2,
        "ma_window": None,
        "risk_off_asset": "btc",
        "initial_asset": "btc",
        "multiple": 50.0,
    }
    row.update(overrides)
    return row


def test_run_full_window_screen_writes_metrics_for_candidates() -> None:
    market = _script_toy_market()
    config = _script_config()
    universe_by_liquidity = _script_universe_by_liquidity()
    candidates = [_script_candidate()]

    summary, results = run_full_window_screen(market, universe_by_liquidity, config, candidates)

    assert summary.loc[0, "candidate_id"] == "ctrend_lite_test"
    assert summary.loc[0, "multiple"] > 1
    assert summary.loc[0, "best_rolling_5y_multiple"] == 0.0
    assert summary.loc[0, "hundred_x_hit_rate_5y"] == 0.0
    assert "raw_convexity_score" in summary.columns
    assert "robust_convexity_score" in summary.columns
    assert "ctrend_lite_test" in results


def test_run_one_candidate_slices_returns_to_config_window() -> None:
    market = _script_toy_market()
    market.price.loc[pd.Timestamp("2024-01-02"), "bitcoin"] = 10_000.0
    market.returns = market.price.pct_change().fillna(0.0)
    config = _script_config()
    config.end_date = "2024-03-15"
    candidate = _script_candidate(
        candidate_id="window_slice_test",
        risk_off_asset="btc",
        initial_asset="btc",
    )

    result = run_one_candidate(market, _script_universe_by_liquidity(), config, candidate)

    assert not result.daily_returns.empty
    assert result.daily_returns.index.min() == config.start_timestamp
    assert result.daily_returns.index.max() == config.end_timestamp


def test_run_one_candidate_total_cost_does_not_mutate_config_friction() -> None:
    market = _script_toy_market()
    config = _script_config()
    original_fee_bps = config.frictions.fee_bps
    original_slippage_bps = config.frictions.slippage_bps

    run_one_candidate(
        market,
        _script_universe_by_liquidity(),
        config,
        _script_candidate(candidate_id="cost_copy_test"),
        total_cost_bps=100.0,
    )

    assert config.frictions.fee_bps == original_fee_bps
    assert config.frictions.slippage_bps == original_slippage_bps


def test_run_full_window_screen_empty_candidates_has_schema() -> None:
    summary, results = run_full_window_screen(
        _script_toy_market(),
        _script_universe_by_liquidity(),
        _script_config(),
        [],
    )

    assert summary.empty
    assert {
        "candidate_id",
        "multiple",
        "raw_convexity_score",
        "robust_convexity_score",
        "trial_count_estimate",
    }.issubset(summary.columns)
    assert results == {}


def test_run_full_window_screen_can_exclude_btc_for_ctrend_lite() -> None:
    market = _script_toy_market()
    config = _script_config()
    candidate_id = "ctrend_lite_ex_btc"

    _, results = run_full_window_screen(
        market,
        _script_universe_by_liquidity(),
        config,
        [_script_candidate(candidate_id=candidate_id, include_btc=False)],
    )

    targets = results[candidate_id].rebalance_targets
    assert not targets.empty
    assert (targets["bitcoin"] <= 0.0).all()


def test_run_one_candidate_parks_in_eth_when_trailing_stop_turns_off() -> None:
    market = _script_toy_market()
    market.price.loc[pd.Timestamp("2024-02-27") : pd.Timestamp("2024-02-29"), "bitcoin"] = 200.0
    market.price.loc[pd.Timestamp("2024-03-01") : pd.Timestamp("2024-03-08"), "bitcoin"] = 50.0
    market.returns = market.price.pct_change().fillna(0.0)
    config = _script_config()
    candidate = _script_candidate(
        candidate_id="eth_parking_stop_test",
        stop_kind="trailing",
        stop_lookback=3,
        risk_off_asset="eth",
        initial_asset="cash",
    )

    result = run_one_candidate(market, _script_universe_by_liquidity(), config, candidate)

    targets = result.rebalance_targets
    assert not targets.empty
    assert (targets["ethereum"] > 0.0).any()


def test_run_full_window_screen_handles_leader_momentum_candidate() -> None:
    market = _script_toy_market()
    config = _script_config()
    candidate_id = "leader_momentum_test"

    summary, results = run_full_window_screen(
        market,
        _script_universe_by_liquidity(),
        config,
        [
            _script_candidate(
                candidate_id=candidate_id,
                family_id="leader_momentum",
                strategy_kind="leader_momentum",
                score_family="base",
            )
        ],
    )

    assert summary.loc[0, "candidate_id"] == candidate_id
    assert candidate_id in results
    targets = results[candidate_id].rebalance_targets
    assert not targets.empty
    assert (targets.sum(axis=1) > 0.0).any()


def test_candidate_definitions_are_bounded_and_include_discovery_lane() -> None:
    candidates = build_candidate_definitions()
    family_ids = {candidate.family_id for candidate in candidates}

    assert isinstance(candidates[0], CandidateDefinition)
    assert "leader_momentum" in family_ids
    assert "ctrend_lite" in family_ids
    assert "champion_ablation" in family_ids
    assert len(candidates) < 2_500
    assert len({candidate.candidate_id for candidate in candidates}) == len(candidates)


def test_raw_convexity_score_prefers_higher_multiple_with_drawdown_penalty() -> None:
    strong = pd.Series(
        {
            "multiple": 100.0,
            "best_rolling_5y_multiple": 120.0,
            "hundred_x_hit_rate_5y": 0.50,
            "max_drawdown": -0.60,
        }
    )
    weak = pd.Series(
        {
            "multiple": 20.0,
            "best_rolling_5y_multiple": 25.0,
            "hundred_x_hit_rate_5y": 0.05,
            "max_drawdown": -0.50,
        }
    )

    assert compute_raw_convexity_score(strong) > compute_raw_convexity_score(weak)


def test_robust_convexity_score_penalizes_fragile_costly_candidate() -> None:
    robust = pd.Series(
        {
            "median_rolling_start_multiple": 40.0,
            "hundred_x_hit_rate_5y": 0.25,
            "max_drawdown": -0.55,
            "cost_survival_100bps": 0.70,
            "stability_score": 0.80,
            "annualized_turnover": 20.0,
        }
    )
    fragile = pd.Series(
        {
            "median_rolling_start_multiple": 60.0,
            "hundred_x_hit_rate_5y": 0.25,
            "max_drawdown": -0.78,
            "cost_survival_100bps": 0.20,
            "stability_score": 0.10,
            "annualized_turnover": 60.0,
        }
    )

    assert compute_robust_convexity_score(robust) > compute_robust_convexity_score(fragile)


def test_select_validation_candidates_keeps_champion_and_deduplicates() -> None:
    frame = pd.DataFrame(
        [
            {
                "candidate_id": "champion",
                "raw_convexity_score": 1.0,
                "robust_convexity_score": 1.0,
                "multiple": 2.0,
            },
            {
                "candidate_id": "raw_best",
                "raw_convexity_score": 5.0,
                "robust_convexity_score": 1.0,
                "multiple": 50.0,
            },
            {
                "candidate_id": "robust_best",
                "raw_convexity_score": 1.0,
                "robust_convexity_score": 5.0,
                "multiple": 30.0,
            },
            {
                "candidate_id": "also_good",
                "raw_convexity_score": 4.0,
                "robust_convexity_score": 4.0,
                "multiple": 26.0,
            },
        ]
    )

    selected = select_validation_candidates(
        frame,
        champion_candidate_id="champion",
        max_validation_candidates=3,
        min_multiple_for_validation=25.0,
    )

    assert selected == ["champion", "raw_best", "robust_best"]


def test_select_validation_candidates_adds_ranked_candidates_until_cap() -> None:
    frame = pd.DataFrame(
        [
            {
                "candidate_id": f"raw_{rank}",
                "raw_convexity_score": float(rank),
                "robust_convexity_score": 0.0,
                "multiple": 1.0,
            }
            for rank in range(1, 7)
        ]
    )

    selected = select_validation_candidates(
        frame,
        champion_candidate_id="missing_champion",
        max_validation_candidates=5,
        min_multiple_for_validation=25.0,
    )

    assert selected[:2] == ["raw_6", "raw_5"]
    assert len(selected) == 5
    assert len(set(selected)) == len(selected)


def test_select_validation_candidates_returns_empty_for_nonpositive_cap() -> None:
    frame = pd.DataFrame(
        [
            {
                "candidate_id": "candidate",
                "raw_convexity_score": 1.0,
                "robust_convexity_score": 1.0,
                "multiple": 100.0,
            }
        ]
    )

    assert (
        select_validation_candidates(
            frame,
            champion_candidate_id="candidate",
            max_validation_candidates=0,
            min_multiple_for_validation=25.0,
        )
        == []
    )


def test_select_validation_candidates_validates_candidate_id_column() -> None:
    frame = pd.DataFrame([{"multiple": 100.0}])

    with pytest.raises(ValueError, match="candidate_id"):
        select_validation_candidates(
            frame,
            champion_candidate_id="candidate",
            max_validation_candidates=5,
            min_multiple_for_validation=25.0,
        )


def test_select_validation_candidates_validates_multiple_column() -> None:
    frame = pd.DataFrame([{"candidate_id": "candidate"}])

    with pytest.raises(ValueError, match="multiple"):
        select_validation_candidates(
            frame,
            champion_candidate_id="candidate",
            max_validation_candidates=5,
            min_multiple_for_validation=25.0,
        )


def test_select_validation_candidates_dedupes_threshold_overlap() -> None:
    frame = pd.DataFrame(
        [
            {"candidate_id": "raw_best", "raw_convexity_score": 5.0, "multiple": 30.0},
            {"candidate_id": "threshold_best", "raw_convexity_score": 1.0, "multiple": 50.0},
            {"candidate_id": "raw_best", "raw_convexity_score": 0.5, "multiple": 40.0},
        ]
    )

    selected = select_validation_candidates(
        frame,
        champion_candidate_id="missing_champion",
        max_validation_candidates=5,
        min_multiple_for_validation=25.0,
    )

    assert selected == ["raw_best", "threshold_best"]


def test_select_validation_candidates_reserves_threshold_lane() -> None:
    frame = pd.DataFrame(
        [
            {
                "candidate_id": "raw_1",
                "raw_convexity_score": 100.0,
                "robust_convexity_score": 5.0,
                "multiple": 1.0,
            },
            {
                "candidate_id": "raw_2",
                "raw_convexity_score": 90.0,
                "robust_convexity_score": 4.0,
                "multiple": 1.0,
            },
            {
                "candidate_id": "robust_1",
                "raw_convexity_score": 3.0,
                "robust_convexity_score": 100.0,
                "multiple": 1.0,
            },
            {
                "candidate_id": "robust_2",
                "raw_convexity_score": 2.0,
                "robust_convexity_score": 90.0,
                "multiple": 1.0,
            },
            {
                "candidate_id": "robust_3",
                "raw_convexity_score": 1.0,
                "robust_convexity_score": 80.0,
                "multiple": 1.0,
            },
            {
                "candidate_id": "high_multiple",
                "raw_convexity_score": 0.0,
                "robust_convexity_score": 0.0,
                "multiple": 1_000.0,
            },
        ]
    )

    selected = select_validation_candidates(
        frame,
        champion_candidate_id="missing_champion",
        max_validation_candidates=5,
        min_multiple_for_validation=100.0,
    )

    assert "high_multiple" in selected


def test_add_candidate_ids_respects_zero_limit() -> None:
    selected: list[str] = []

    _add_candidate_ids(selected, ["candidate"], max_candidates=5, limit=0)

    assert selected == []


def test_compute_rolling_window_summary_detects_hundred_x_window() -> None:
    dates = pd.date_range("2020-01-01", periods=365 * 5, freq="D")
    daily_returns = pd.Series(100.0 ** (1.0 / len(dates)) - 1.0, index=dates, name="candidate")

    summary, windows = compute_rolling_window_summary(
        {"candidate": daily_returns},
        windows_days=(365 * 5,),
    )

    assert summary.loc[0, "candidate_id"] == "candidate"
    assert summary.loc[0, "best_rolling_5y_multiple"] >= 99.0
    assert summary.loc[0, "hundred_x_hit_rate_5y"] > 0
    assert not windows.empty


def test_compute_rolling_window_summary_uses_exact_window_length() -> None:
    dates = pd.date_range("2020-01-01", periods=365 * 5 + 5, freq="D")
    daily_returns = pd.Series(100.0 ** (1.0 / len(dates)) - 1.0, index=dates, name="candidate")

    summary, windows = compute_rolling_window_summary(
        {"candidate": daily_returns},
        windows_days=(365 * 5,),
    )

    assert summary.loc[0, "best_rolling_5y_multiple"] < 100.0
    assert summary.loc[0, "hundred_x_hit_rate_5y"] == 0.0
    assert windows.empty


def test_compute_cost_sensitivity_reports_survival_ratio() -> None:
    base_summary = pd.DataFrame(
        [{"candidate_id": "candidate", "multiple": 10.0, "max_drawdown": -0.4}]
    )
    stressed = {
        20.0: {"candidate": 9.0},
        100.0: {"candidate": 6.0},
    }

    result = compute_cost_sensitivity(base_summary, stressed)

    assert set(result["total_cost_bps"]) == {20.0, 100.0}
    assert result[result["total_cost_bps"] == 100.0].iloc[0][
        "survival_ratio"
    ] == pytest.approx(0.6)


def test_compute_stability_surface_marks_neighbor_region() -> None:
    summary = pd.DataFrame(
        [
            _stability_summary_row(candidate_id="a", top_n=1, frequency="14D", stop_lookback=11),
            _stability_summary_row(
                candidate_id="b",
                top_n=2,
                frequency="14D",
                stop_lookback=11,
                multiple=40.0,
            ),
            _stability_summary_row(
                candidate_id="c",
                top_n=1,
                frequency="21D",
                stop_lookback=12,
                multiple=35.0,
            ),
        ]
    )

    result = compute_stability_surface(summary, candidate_ids=["a"], multiple_floor=25.0)

    assert result.loc[0, "candidate_id"] == "a"
    assert result.loc[0, "neighbor_count"] == 2
    assert result.loc[0, "stability_score"] > 0


def test_compute_stability_surface_excludes_different_overlay_neighbors() -> None:
    summary = pd.DataFrame(
        [
            _stability_summary_row(candidate_id="a"),
            _stability_summary_row(
                candidate_id="valid_neighbor",
                top_n=2,
                stop_lookback=12,
                multiple=40.0,
            ),
            _stability_summary_row(
                candidate_id="different_parking",
                risk_off_asset="cash",
                multiple=45.0,
            ),
            _stability_summary_row(
                candidate_id="different_stop",
                stop_kind="ma",
                ma_window=100,
                multiple=44.0,
            ),
        ]
    )

    result = compute_stability_surface(summary, candidate_ids=["a"], multiple_floor=25.0)

    assert result.loc[0, "neighbor_count"] == 1
    assert result.loc[0, "median_neighbor_multiple"] == pytest.approx(40.0)


def test_compute_stability_surface_excludes_different_universe_neighbors() -> None:
    summary = pd.DataFrame(
        [
            _stability_summary_row(candidate_id="a"),
            _stability_summary_row(
                candidate_id="valid_neighbor",
                top_n=2,
                stop_lookback=12,
                multiple=40.0,
            ),
            _stability_summary_row(
                candidate_id="different_include_btc",
                include_btc=False,
                multiple=45.0,
            ),
            _stability_summary_row(
                candidate_id="different_liquidity",
                liquidity_label="strict",
                multiple=44.0,
            ),
        ]
    )

    result = compute_stability_surface(summary, candidate_ids=["a"], multiple_floor=25.0)

    assert result.loc[0, "neighbor_count"] == 1
    assert result.loc[0, "median_neighbor_multiple"] == pytest.approx(40.0)


def test_compute_stability_surface_requires_structural_columns() -> None:
    summary = pd.DataFrame([_stability_summary_row(candidate_id="a")]).drop(
        columns=["include_btc", "risk_off_asset"]
    )

    with pytest.raises(ValueError, match="include_btc"):
        compute_stability_surface(summary, candidate_ids=["a"], multiple_floor=25.0)
    with pytest.raises(ValueError, match="risk_off_asset"):
        compute_stability_surface(
            summary.assign(include_btc=True),
            candidate_ids=["a"],
            multiple_floor=25.0,
        )


def test_compute_rolling_start_validation_runs_multiple_starts() -> None:
    market = _script_toy_market()
    config = load_config("config/base.yaml")
    config.start_date = "2024-02-01"
    config.rebalancing.frequencies["14D"] = "14D"
    universe_by_liquidity = {
        "loose": _script_toy_universe(pd.date_range("2024-02-01", periods=5, freq="14D"))
    }
    candidate = CandidateDefinition(
        candidate_id="ctrend_lite_test",
        family_id="ctrend_lite",
        strategy_kind="ctrend_lite",
        top_n=1,
        frequency="14D",
        score_family="ctrend_lite_balanced",
        liquidity_label="loose",
        min_history_days=30,
        min_daily_dollar_volume=1_000_000.0,
        include_btc=True,
        overlay_set="no_stop_control",
        risk_off_asset="cash",
        initial_asset="cash",
        stop_kind="none",
        stop_lookback=None,
        stop_confirm_days=1,
        ma_window=None,
    )

    summary, by_candidate = compute_rolling_start_validation(
        market,
        universe_by_liquidity,
        config,
        {candidate.candidate_id: candidate},
        [candidate.candidate_id],
        min_days_after_start=30,
    )

    expected_summary_columns = {
        "candidate_id",
        "start_count",
        "median_rolling_start_multiple",
        "min_rolling_start_multiple",
        "max_rolling_start_multiple",
        "max_rolling_start_drawdown",
        "median_rolling_start_drawdown",
    }
    expected_detail_columns = {
        "candidate_id",
        "start_date",
        "multiple",
        "cagr",
        "sharpe",
        "max_drawdown",
        "annualized_turnover",
    }

    assert summary.loc[0, "candidate_id"] == "ctrend_lite_test"
    assert summary.loc[0, "start_count"] >= 2
    assert by_candidate["start_date"].nunique() >= 2
    assert expected_summary_columns.issubset(summary.columns)
    assert expected_detail_columns.issubset(by_candidate.columns)


def test_compute_rolling_start_validation_respects_config_end_date() -> None:
    market = _script_toy_market()
    config = load_config("config/base.yaml")
    config.start_date = "2024-02-01"
    config.end_date = "2024-03-15"
    config.rebalancing.frequencies["14D"] = "14D"
    universe_by_liquidity = {
        "loose": _script_toy_universe(pd.date_range("2024-02-01", periods=5, freq="14D"))
    }
    candidate = _script_candidate()

    _, by_candidate = compute_rolling_start_validation(
        market,
        universe_by_liquidity,
        config,
        {candidate.candidate_id: candidate},
        [candidate.candidate_id],
        min_days_after_start=0,
    )

    start_dates = pd.to_datetime(by_candidate["start_date"])
    assert not start_dates.empty
    assert (start_dates <= config.end_timestamp).all()


def test_compute_rolling_start_validation_rejects_unknown_candidate_id() -> None:
    with pytest.raises(ValueError, match="missing"):
        compute_rolling_start_validation(
            _script_toy_market(),
            _script_universe_by_liquidity(),
            _script_config(),
            {},
            ["missing"],
            min_days_after_start=30,
        )


def test_compute_contribution_summary_records_top_dependency() -> None:
    market = _script_toy_market()
    dates = market.price.index[:4]
    weights = pd.DataFrame(
        {
            "bitcoin": [0.0, 0.0, 0.0, 0.0],
            "ethereum": [0.0, 0.0, 0.0, 0.0],
            "solana": [1.0, 1.0, 1.0, 1.0],
            "chainlink": [0.0, 0.0, 0.0, 0.0],
        },
        index=dates,
    )
    from atlas20.backtest.engine import BacktestResult

    result = BacktestResult(
        name="candidate",
        daily_returns=pd.Series([0.0, 0.1, 0.1, 0.1], index=dates),
        equity_curve=pd.Series([1.0, 1.1, 1.21, 1.331], index=dates),
        drawdown=pd.Series([0.0, 0.0, 0.0, 0.0], index=dates),
        weights=weights,
        turnover=pd.Series([0.0, 1.0, 0.0, 0.0], index=dates),
        holdings_count=pd.Series([1.0, 1.0, 1.0, 1.0], index=dates),
        sector_exposure=pd.DataFrame(index=dates),
        rebalance_targets=weights,
    )

    summary = compute_contribution_summary({"candidate": result}, market)

    assert summary.loc[0, "candidate_id"] == "candidate"
    assert summary.loc[0, "top_coin_id"] == "solana"
    assert summary.loc[0, "top1_contribution_share"] == pytest.approx(1.0)
