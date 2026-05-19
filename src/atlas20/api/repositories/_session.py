"""SQLModel session dependency."""

from __future__ import annotations

from collections.abc import Iterator
from functools import lru_cache
from pathlib import Path

from sqlalchemy.engine import Engine, make_url
from sqlmodel import Session, create_engine

from atlas20.api.settings import Settings, get_settings


def _ensure_sqlite_parent(db_url: str) -> None:
    url = make_url(db_url)
    if url.get_backend_name() != "sqlite" or url.database in (None, "", ":memory:"):
        return
    Path(url.database).expanduser().parent.mkdir(parents=True, exist_ok=True)


@lru_cache
def _engine_for_url(db_url: str) -> Engine:
    _ensure_sqlite_parent(db_url)
    connect_args = {"check_same_thread": False} if make_url(db_url).get_backend_name() == "sqlite" else {}
    return create_engine(db_url, connect_args=connect_args)


def get_engine(settings: Settings) -> Engine:
    return _engine_for_url(settings.db_url)


def get_session() -> Iterator[Session]:
    engine = get_engine(get_settings())
    with Session(engine) as session:
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
