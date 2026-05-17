from pathlib import Path

import pytest

from atlas20.api.runner import build_run_request_name, write_run_artifacts
from atlas20.api.schemas import (
    BacktestRequest,
    RiskConfigInput,
    StrategyConfigInput,
    UniverseConfigInput,
    WeightInput,
    WindowInput,
)


def _request() -> BacktestRequest:
    return BacktestRequest(
        window=WindowInput(start_date="2022-11-21", end_date="2026-04-21"),
        strategy=StrategyConfigInput(family="momentum_lead", top_n=1, frequency="14D"),
        universe=UniverseConfigInput(
            min_history_days=30,
            min_daily_dollar_volume=1000000.5,
            exclude_btc=False,
        ),
        risk=RiskConfigInput(
            mode="always_on",
            stop_lookback_days=11,
            confirm_days=2,
            risk_off_asset="bitcoin",
        ),
        weights=WeightInput(
            momentum_rank=0.607681,
            ret_21_rank=0.268948,
            ret_42_rank=0.017319,
            near_high_rank=0.106052,
        ),
    )


def test_window_input_rejects_start_date_after_end_date():
    with pytest.raises(ValueError):
        WindowInput(start_date="2026-04-21", end_date="2022-11-21")


def test_build_run_request_name_is_stable_and_distinguishes_material_changes():
    base = _request()
    changed = base.model_copy(
        update={
            "risk": RiskConfigInput(
                mode="bull_only",
                stop_lookback_days=11,
                confirm_days=2,
                risk_off_asset="bitcoin",
            )
        }
    )

    assert build_run_request_name(base).startswith("momentum_lead_top1_14D")
    assert build_run_request_name(base) != build_run_request_name(changed)


def test_write_run_artifacts_creates_github_friendly_run_files(tmp_path: Path):
    write_run_artifacts(
        tmp_path,
        summary={"strategy": "demo", "multiple": 2.0},
        equity_rows=[{"date": "2026-01-01", "equity": 100000.0}],
        drawdown_rows=[{"date": "2026-01-01", "drawdown": 0.0}],
        daily_return_rows=[{"date": "2026-01-01", "daily_return": 0.0}],
        selection_rows=[{"rebalance_date": "2026-01-01", "coin_id": "bitcoin"}],
    )

    assert (tmp_path / "summary.csv").exists()
    assert (tmp_path / "equity_curve.csv").exists()
    assert (tmp_path / "request.json").exists()
