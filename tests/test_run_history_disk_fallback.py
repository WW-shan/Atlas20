from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path

import pytest
from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel, Session, create_engine

from atlas20.api.services import list_runs
from atlas20.api.settings import get_settings


@pytest.fixture
def empty_db_session() -> Iterator[Session]:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
        session.rollback()
    engine.dispose()


def _write_manifest(report_root: Path, directory_name: str, manifest: dict[str, object]) -> None:
    run_dir = report_root / "app_runs" / directory_name
    run_dir.mkdir(parents=True)
    (run_dir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")


def _disk_manifest(run_id: str = "btk_9001") -> dict[str, object]:
    return {
        "run_id": run_id,
        "strategy": "Disk Strategy",
        "strategy_family": "Other",
        "universe": "Top-20",
        "window": {"start": "2024-01-01", "end": "2026-05-18"},
        "status": "completed",
        "created_at": "2026-05-19T10:00:00Z",
        "favorited": True,
        "metrics": {
            "return_pct": 0.42,
            "sharpe": 1.23,
            "max_dd": -0.18,
            "duration_s": 73,
            "spark": [10, 11, 13],
        },
    }


def test_list_runs_falls_back_to_manifest_when_db_empty(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    empty_db_session: Session,
) -> None:
    report_root = tmp_path / "reports"
    _write_manifest(report_root, "directory-name-is-not-the-run-id", _disk_manifest())
    monkeypatch.setenv("ATLAS20_REPORT_ROOT", str(report_root))
    get_settings.cache_clear()

    rows, total = list_runs(empty_db_session, date_range="all")

    assert total == 1
    assert len(rows) == 1
    assert rows[0].run_id == "btk_9001"
    assert rows[0].strategy == "Disk Strategy"
    assert rows[0].return_pct == 0.42
    assert rows[0].sharpe == 1.23
    assert rows[0].max_dd == -0.18
    assert rows[0].created_at == "2026-05-19T10:00:00Z"
    assert rows[0].favorited is True


def test_list_runs_prefers_db_when_db_has_rows(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    db_session: Session,
) -> None:
    report_root = tmp_path / "reports"
    _write_manifest(report_root, "disk-only", _disk_manifest("btk_disk_only"))
    monkeypatch.setenv("ATLAS20_REPORT_ROOT", str(report_root))
    get_settings.cache_clear()

    rows, total = list_runs(db_session, date_range="all", page_size=50)

    assert total == 14
    assert len(rows) == 14
    assert all(row.run_id != "btk_disk_only" for row in rows)


def test_list_runs_does_not_fall_back_when_db_filter_matches_nothing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    db_session: Session,
) -> None:
    report_root = tmp_path / "reports"
    _write_manifest(report_root, "disk-only", _disk_manifest("btk_disk_only"))
    monkeypatch.setenv("ATLAS20_REPORT_ROOT", str(report_root))
    get_settings.cache_clear()

    rows, total = list_runs(db_session, q="Disk", date_range="all")

    assert rows == []
    assert total == 0


def test_list_runs_empty_db_without_disk_returns_empty_not_mock(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    empty_db_session: Session,
) -> None:
    monkeypatch.setenv("ATLAS20_REPORT_ROOT", str(tmp_path / "reports"))
    get_settings.cache_clear()

    rows, total = list_runs(empty_db_session, date_range="all")

    assert rows == []
    assert total == 0
