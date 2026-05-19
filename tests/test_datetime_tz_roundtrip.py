from datetime import date, datetime, timezone

from sqlmodel import SQLModel, Session, create_engine, select

from atlas20.api.db.models import IdempotencyKey, KvSetting, ReportFile, Run


def assert_utc_roundtrip(value: datetime, expected: datetime) -> None:
    assert value.tzinfo == timezone.utc
    assert value == expected


def test_run_datetime_fields_preserve_utc_timezone_roundtrip(tmp_path):
    db_path = tmp_path / "datetime.sqlite"
    engine = create_engine(f"sqlite:///{db_path.as_posix()}")
    SQLModel.metadata.create_all(engine)
    created_at = datetime(2026, 5, 20, 12, 0, 0, tzinfo=timezone.utc)
    started_at = datetime(2026, 5, 20, 12, 1, 0, tzinfo=timezone.utc)
    heartbeat_at = datetime(2026, 5, 20, 12, 2, 0, tzinfo=timezone.utc)

    with Session(engine) as session:
        session.add(
            Run(
                run_id="btk_9001",
                strategy="ATLAS Adaptive v4",
                strategy_family="ATLAS",
                universe="Top-20",
                window_start=date(2024, 1, 1),
                window_end=date(2026, 5, 18),
                status="queued",
                created_at=created_at,
                started_at=started_at,
                heartbeat_at=heartbeat_at,
            )
        )
        session.commit()

    with Session(engine) as session:
        run = session.exec(select(Run).where(Run.run_id == "btk_9001")).one()

    assert_utc_roundtrip(run.created_at, created_at)
    assert_utc_roundtrip(run.started_at, started_at)
    assert_utc_roundtrip(run.heartbeat_at, heartbeat_at)


def test_supporting_datetime_fields_preserve_utc_timezone_roundtrip(tmp_path):
    db_path = tmp_path / "datetime.sqlite"
    engine = create_engine(f"sqlite:///{db_path.as_posix()}")
    SQLModel.metadata.create_all(engine)
    generated_at = datetime(2026, 5, 20, 12, 3, 0, tzinfo=timezone.utc)
    updated_at = datetime(2026, 5, 20, 12, 4, 0, tzinfo=timezone.utc)
    created_at = datetime(2026, 5, 20, 12, 5, 0, tzinfo=timezone.utc)
    expires_at = datetime(2026, 5, 20, 12, 6, 0, tzinfo=timezone.utc)

    with Session(engine) as session:
        session.add(
            ReportFile(
                run_id=None,
                kind="digest",
                path="reports/app_runs/btk_9001.md",
                size_bytes=128,
                sha256="abc123",
                generated_at=generated_at,
            )
        )
        session.add(KvSetting(key="timezone", value="utc", updated_at=updated_at))
        session.add(
            IdempotencyKey(
                key="idem-1",
                method="POST",
                path="/api/backtests/run",
                response_json='{"ok": true}',
                created_at=created_at,
                expires_at=expires_at,
            )
        )
        session.commit()

    with Session(engine) as session:
        report = session.exec(select(ReportFile).where(ReportFile.sha256 == "abc123")).one()
        setting = session.get(KvSetting, "timezone")
        key = session.get(IdempotencyKey, "idem-1")

    assert_utc_roundtrip(report.generated_at, generated_at)
    assert setting is not None
    assert_utc_roundtrip(setting.updated_at, updated_at)
    assert key is not None
    assert_utc_roundtrip(key.created_at, created_at)
    assert_utc_roundtrip(key.expires_at, expires_at)
