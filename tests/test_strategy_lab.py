from datetime import date, datetime, timezone

import pytest
from sqlmodel import Session

from atlas20.api.db.models import Run
from atlas20.api.repositories import RunsRepo
from atlas20.api.schemas import BacktestConfig, StrategyLabMatrixRequest
from atlas20.api import services


def valid_config() -> dict:
    return {
        "preset": "base",
        "universe": {"topN": 20, "excludeStable": True, "excludeWrapped": True},
        "window": {"start": "2024-01-01", "end": "2026-05-18", "rebalance": "Monthly"},
        "allocation": {"positionPct": 10, "slots": 10},
        "costs": {"feeBps": 10, "slippageBps": 5},
    }


def test_strategy_lab_matrix_request_validates_payload() -> None:
    request = StrategyLabMatrixRequest.model_validate(
        {
            "presets": ["base"],
            "topNs": [10, 20],
            "rebalances": ["Weekly", "Monthly"],
            "baseConfig": valid_config(),
        }
    )

    assert request.presets == ["base"]
    assert request.top_ns == [10, 20]
    assert request.base_config == BacktestConfig.model_validate(valid_config())


def test_runs_repo_lists_runs_by_strategy_lab_batch(db_session: Session) -> None:
    db_session.add(
        Run(
            run_id="btk_9991",
            strategy="base",
            strategy_family="Other",
            universe="Top-20",
            window_start=date(2024, 1, 1),
            window_end=date(2026, 5, 18),
            status="completed",
            return_pct=0.2,
            sharpe=1.4,
            max_dd=-0.15,
            strategy_lab_batch_id="lab_test",
            created_at=datetime(2026, 5, 19, tzinfo=timezone.utc),
        )
    )
    db_session.commit()

    rows = RunsRepo(db_session).list_by_strategy_lab_batch("lab_test")

    assert [row.run_id for row in rows] == ["btk_9991"]


def test_submit_strategy_lab_batch_queues_matrix(db_session: Session) -> None:
    request = StrategyLabMatrixRequest.model_validate(
        {
            "presets": ["base"],
            "topNs": [10, 20],
            "rebalances": ["Weekly", "Monthly"],
            "baseConfig": valid_config(),
        }
    )

    response = services.submit_strategy_lab_batch(db_session, request)

    assert response.total == 4
    assert response.batch_id.startswith("lab_")
    assert {run.strategy for run in response.runs} == {"base"}
    rows = RunsRepo(db_session).list_by_strategy_lab_batch(response.batch_id)
    assert len(rows) == 4
    assert {row.universe for row in rows} == {"Top-10", "Top-20"}


def test_submit_strategy_lab_batch_rejects_oversized_matrix(db_session: Session) -> None:
    request = StrategyLabMatrixRequest.model_validate(
        {
            "presets": ["base"] * 5,
            "topNs": [5, 10, 15],
            "rebalances": ["Weekly", "Biweekly"],
            "baseConfig": valid_config(),
        }
    )

    with pytest.raises(ValueError, match="at most 24"):
        services.submit_strategy_lab_batch(db_session, request)


def test_get_strategy_lab_batch_returns_counts_and_results(db_session: Session) -> None:
    request = StrategyLabMatrixRequest.model_validate(
        {
            "presets": ["base"],
            "topNs": [20],
            "rebalances": ["Monthly"],
            "baseConfig": valid_config(),
        }
    )
    response = services.submit_strategy_lab_batch(db_session, request)
    run_id = response.runs[0].run_id
    RunsRepo(db_session).update(
        run_id,
        status="completed",
        return_pct=0.24,
        sharpe=1.9,
        max_dd=-0.12,
        duration_s=42,
    )

    payload = services.get_strategy_lab_batch(db_session, response.batch_id)

    assert payload.batch_id == response.batch_id
    assert payload.status_counts["completed"] == 1
    assert payload.results[0].run_id == run_id
    assert payload.results[0].topN == 20
