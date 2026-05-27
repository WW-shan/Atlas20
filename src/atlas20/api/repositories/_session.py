"""SQLModel session dependency."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

from sqlalchemy.engine import Engine, make_url
from sqlmodel import Session, create_engine

from atlas20.api.settings import Settings, get_settings


def _ensure_sqlite_parent(db_url: str) -> None:
    url = make_url(db_url)
    database = url.database
    if url.get_backend_name() != "sqlite" or database is None or database in ("", ":memory:"):
        return
    Path(database).expanduser().parent.mkdir(parents=True, exist_ok=True)


_ENGINES: dict[str, Engine] = {}


def _engine_for_url(db_url: str) -> Engine:
    if db_url in _ENGINES:
        return _ENGINES[db_url]
    _ensure_sqlite_parent(db_url)
    connect_args = {"check_same_thread": False} if make_url(db_url).get_backend_name() == "sqlite" else {}
    engine = create_engine(db_url, connect_args=connect_args)
    _ENGINES[db_url] = engine
    return engine


def dispose_all_engines() -> None:
    for engine in _ENGINES.values():
        engine.dispose()
    _ENGINES.clear()


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
