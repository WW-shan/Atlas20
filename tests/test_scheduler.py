from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

import pytest
from sqlmodel import Session

from atlas20.api.db.models import Run
from atlas20.api.repositories import KvRepo
from atlas20.api.scheduler import generate_featured_digest, start_scheduler
from atlas20.api.services import get_featured_digest
from atlas20.api.settings import get_settings
from tests.test_generate_report import VALID_PARAMS, _prepare_run


def test_scheduler_start_is_disabled_in_pytest() -> None:
    assert os.environ["ATLAS20_DISABLE_SCHEDULER"] == "1"
    assert start_scheduler() is None


def _create_completed_run(db_session: Session, report_root: Path, run_id: str, created_at: datetime) -> None:
    run = Run(
        run_id=run_id,
        strategy="ATLAS Adaptive v3",
        strategy_family="ATLAS",
        universe="Top-20",
        window_start=datetime(2024, 1, 1, tzinfo=timezone.utc).date(),
        window_end=datetime(2026, 5, 18, tzinfo=timezone.utc).date(),
        status="completed",
        params=json.dumps(VALID_PARAMS),
        created_at=created_at,
    )
    db_session.add(run)
    db_session.flush()
    _prepare_run(db_session, report_root, run_id)


def test_featured_digest_job_picks_most_recent_completed_run(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, db_session: Session
) -> None:
    monkeypatch.setenv("ATLAS20_REPORT_ROOT", str(tmp_path / "reports"))
    monkeypatch.setenv("ATLAS20_DATA_ROOT", str(tmp_path / "data"))
    get_settings.cache_clear()
    report_root = get_settings().report_root
    _create_completed_run(db_session, report_root, "btk_9001", datetime(2026, 6, 1, tzinfo=timezone.utc))
    _create_completed_run(db_session, report_root, "btk_9002", datetime(2026, 6, 8, tzinfo=timezone.utc))

    generate_featured_digest(session=db_session, formats={"markdown"})

    assert KvRepo(db_session).get("featured_digest_run_id") == "btk_9002"


def test_featured_digest_job_writes_kv_setting(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, db_session: Session
) -> None:
    monkeypatch.setenv("ATLAS20_REPORT_ROOT", str(tmp_path / "reports"))
    monkeypatch.setenv("ATLAS20_DATA_ROOT", str(tmp_path / "data"))
    get_settings.cache_clear()
    _create_completed_run(db_session, get_settings().report_root, "btk_9003", datetime(2026, 6, 8, tzinfo=timezone.utc))

    generate_featured_digest(session=db_session, formats={"markdown"})

    assert KvRepo(db_session).get("featured_digest_run_id") == "btk_9003"


def test_get_featured_digest_reads_kv_settings_first(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, db_session: Session
) -> None:
    monkeypatch.setenv("ATLAS20_REPORT_ROOT", str(tmp_path / "reports"))
    monkeypatch.setenv("ATLAS20_DATA_ROOT", str(tmp_path / "data"))
    get_settings.cache_clear()
    _create_completed_run(db_session, get_settings().report_root, "btk_9004", datetime(2026, 6, 8, tzinfo=timezone.utc))
    generate_featured_digest(session=db_session, formats={"markdown"})

    payload = get_featured_digest(db_session)

    assert payload.id == "btk_9004"
    assert "ATLAS Adaptive v3" in payload.subtitle
