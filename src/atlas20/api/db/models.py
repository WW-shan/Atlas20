"""SQLModel table definitions for API persistence."""

from __future__ import annotations

from datetime import date, datetime

from sqlmodel import Field, SQLModel

from atlas20.api._time import utc_now


class Run(SQLModel, table=True):
    __tablename__ = "runs"

    id: int | None = Field(default=None, primary_key=True)
    run_id: str = Field(index=True, unique=True)
    strategy: str
    strategy_family: str | None = None
    universe: str
    window_start: date
    window_end: date
    status: str = Field(index=True)
    return_pct: float | None = None
    sharpe: float | None = None
    max_dd: float | None = None
    duration_s: int | None = None
    eta_s: int | None = None
    spark: str | None = None
    params: str | None = None
    error: str | None = None
    worker_pid: int | None = None
    started_at: datetime | None = None
    heartbeat_at: datetime | None = None
    requested_cancel: bool = False
    favorited: bool = False
    created_at: datetime = Field(default_factory=utc_now, index=True)


class ReportFile(SQLModel, table=True):
    __tablename__ = "report_files"

    id: int | None = Field(default=None, primary_key=True)
    run_id: str | None = Field(index=True, foreign_key="runs.run_id", nullable=True)
    kind: str
    path: str
    size_bytes: int
    sha256: str = Field(index=True)
    generated_at: datetime = Field(default_factory=utc_now)


class KvSetting(SQLModel, table=True):
    __tablename__ = "kv_settings"

    key: str = Field(primary_key=True)
    value: str
    updated_at: datetime = Field(default_factory=utc_now)


class IdempotencyKey(SQLModel, table=True):
    __tablename__ = "idempotency_keys"

    key: str = Field(primary_key=True)
    method: str
    path: str
    response_json: str
    created_at: datetime = Field(default_factory=utc_now)
    expires_at: datetime
