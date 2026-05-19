from datetime import date, datetime, timezone

from sqlmodel import SQLModel, Session, create_engine, select

from atlas20.api.db.models import IdempotencyKey, ReportFile, Run


def test_datetime_fields_preserve_utc_timezone_roundtrip(tmp_path):
    db_path = tmp_path / "datetime.sqlite"
    engine = create_engine(f"sqlite:///{db_path.as_posix()}")
    SQLModel.metadata.create_all(engine)
    created_at = datetime(2026, 5, 20, 1, 2, 3, tzinfo=timezone.utc)
    generated_at = datetime(2026, 5, 20, 2, 3, 4, tzinfo=timezone.utc)
    expires_at = datetime(2026, 5, 21, 1, 2, 3, tzinfo=timezone.utc)

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
            )
        )
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
        run = session.exec(select(Run).where(Run.run_id == "btk_9001")).one()
        report = session.exec(select(ReportFile).where(ReportFile.sha256 == "abc123")).one()
        key = session.get(IdempotencyKey, "idem-1")

    assert run.created_at.tzinfo == timezone.utc
    assert report.generated_at.tzinfo == timezone.utc
    assert key is not None
    assert key.expires_at.tzinfo == timezone.utc
