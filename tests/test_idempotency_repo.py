from sqlmodel import Session, select

from atlas20.api.db.models import IdempotencyKey
from atlas20.api.repositories import IdempotencyRepo


def test_idempotency_repo_store_get_and_expiry(db_session: Session):
    repo = IdempotencyRepo(db_session)

    assert repo.get("abc") is None

    repo.store("abc", "POST", "/api/backtests/run", '{"ok": true}', ttl_seconds=60)
    row = repo.get("abc")

    assert row is not None
    assert row.method == "POST"
    assert row.path == "/api/backtests/run"
    assert row.response_json == '{"ok": true}'

    repo.store("expired", "POST", "/api/backtests/run", '{"ok": false}', ttl_seconds=-1)
    repo.store("expired-2", "POST", "/api/backtests/run", '{"ok": false}', ttl_seconds=-1)

    assert repo.get("expired") is None
    assert repo.purge_expired() == 2
    keys = db_session.exec(select(IdempotencyKey.key)).all()
    assert keys == ["abc"]
