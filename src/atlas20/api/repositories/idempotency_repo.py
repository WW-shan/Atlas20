"""Idempotency key repository."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlmodel import Session, select

from atlas20.api import _time
from atlas20.api.db.models import IdempotencyKey


class IdempotencyRepo:
    def __init__(self, session: Session):
        self._s = session

    def get(self, key: str) -> IdempotencyKey | None:
        row = self._s.get(IdempotencyKey, key)
        if row is None or self._is_expired(row):
            return None
        return row

    def store(self, key: str, method: str, path: str, response_json: str, ttl_seconds: int = 86400) -> None:
        now = _time.utc_now()
        row = self._s.get(IdempotencyKey, key)
        if row is None:
            row = IdempotencyKey(
                key=key,
                method=method,
                path=path,
                response_json=response_json,
                created_at=now,
                expires_at=now + timedelta(seconds=ttl_seconds),
            )
        else:
            row.method = method
            row.path = path
            row.response_json = response_json
            row.created_at = now
            row.expires_at = now + timedelta(seconds=ttl_seconds)
        self._s.add(row)
        self._s.flush()

    def purge_expired(self) -> int:
        rows = self._s.exec(select(IdempotencyKey)).all()
        expired = [row for row in rows if self._is_expired(row)]
        for row in expired:
            self._s.delete(row)
        self._s.flush()
        return len(expired)

    def _is_expired(self, row: IdempotencyKey) -> bool:
        return _aware(row.expires_at) <= _time.utc_now()


def _aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value
