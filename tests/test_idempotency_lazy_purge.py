from sqlmodel import Session

from atlas20.api.db.models import IdempotencyKey
from atlas20.api.repositories import IdempotencyRepo
from atlas20.api.schemas import BacktestConfig
from atlas20.api.services import register_new_backtest


def test_register_new_backtest_purges_expired_idempotency_rows(db_session: Session):
    repo = IdempotencyRepo(db_session)
    repo.store("expired-key", "POST", "/api/backtests/run", '{"ok": false}', ttl_seconds=-1)
    assert db_session.get(IdempotencyKey, "expired-key") is not None

    register_new_backtest(
        db_session,
        BacktestConfig.model_validate(
            {
                "preset": "ATLAS Adaptive v3",
                "universe": {"topN": 20, "excludeStable": True, "excludeWrapped": True},
                "window": {"start": "2024-01-01", "end": "2026-05-18", "rebalance": "Weekly"},
                "allocation": {"positionPct": 5.0, "slots": 10},
                "costs": {"feeBps": 10, "slippageBps": 5},
            }
        ),
    )

    assert db_session.get(IdempotencyKey, "expired-key") is None
