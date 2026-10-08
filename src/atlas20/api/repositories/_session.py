"""SQLModel session dependency."""

from __future__ import annotations

from collections.abc import Iterator
import logging
from pathlib import Path
import sqlite3
from typing import Any

from sqlalchemy import event
from sqlalchemy.engine import Engine, make_url
from sqlmodel import Session, create_engine

from atlas20.api.settings import Settings, get_settings

logger = logging.getLogger(__name__)

# The API, every worker and each run subprocess share one SQLite file. Wait
# this long for a competing writer instead of failing after sqlite3's 5s
# default; it stays well under the worker's stale-heartbeat threshold.
SQLITE_BUSY_TIMEOUT_SECONDS = 30.0


def _sqlite_file(db_url: str) -> str | None:
    """Return the database path of a file-backed SQLite URL, else None."""
    url = make_url(db_url)
    database = url.database
    if url.get_backend_name() != "sqlite" or database is None or database in ("", ":memory:"):
        return None
    return database


def _ensure_sqlite_parent(db_url: str) -> None:
    database = _sqlite_file(db_url)
    if database is None:
        return
    Path(database).expanduser().parent.mkdir(parents=True, exist_ok=True)


_ENGINES: dict[str, Engine] = {}


def _use_wal(dbapi_connection: Any, connection_record: Any) -> None:
    # WAL lets readers proceed while a writer holds the lock, so API reads and
    # worker heartbeats stop tripping over each other. The mode is stored in
    # the database file; this only converts it once.
    del connection_record
    cursor = dbapi_connection.cursor()
    try:
        cursor.execute("PRAGMA journal_mode=WAL")
    except sqlite3.OperationalError as exc:
        logger.warning("could not switch SQLite to WAL journal mode: %s", exc)
    finally:
        cursor.close()


def _engine_for_url(db_url: str) -> Engine:
    if db_url in _ENGINES:
        return _ENGINES[db_url]
    _ensure_sqlite_parent(db_url)
    connect_args: dict[str, Any] = {}
    if make_url(db_url).get_backend_name() == "sqlite":
        connect_args = {"check_same_thread": False, "timeout": SQLITE_BUSY_TIMEOUT_SECONDS}
    engine = create_engine(db_url, connect_args=connect_args)
    if _sqlite_file(db_url) is not None:
        event.listen(engine, "connect", _use_wal)
    _ENGINES[db_url] = engine
    return engine


def dispose_all_engines() -> None:
    for engine in _ENGINES.values():
        engine.dispose()
    _ENGINES.clear()


def get_engine(settings: Settings) -> Engine:
    return _engine_for_url(settings.db_url)


def get_session() -> Iterator[Session]:
    """Yield a request session that commits on success and rolls back on error.

    Declare it as ``Depends(get_session, scope="function")``. With the default
    request scope FastAPI runs the code after ``yield`` only once the response
    has been sent, so a failed commit would reach the client as a 200 for a row
    that never persisted, and a client could read before the commit landed.
    """
    engine = get_engine(get_settings())
    with Session(engine) as session:
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
