"""Key-value settings repository."""

from __future__ import annotations

from sqlmodel import Session

from atlas20.api._time import utc_now
from atlas20.api.db.models import KvSetting


class KvRepo:
    def __init__(self, session: Session):
        self._s = session

    def get(self, key: str) -> str | None:
        row = self._s.get(KvSetting, key)
        return row.value if row else None

    def set(self, key: str, value: str) -> None:
        row = self._s.get(KvSetting, key)
        if row is None:
            row = KvSetting(key=key, value=value, updated_at=utc_now())
        else:
            row.value = value
            row.updated_at = utc_now()
        self._s.add(row)
        self._s.flush()
