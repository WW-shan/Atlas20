from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from atlas20.api.app import create_app
from atlas20.api.db.models import ReportFile
from atlas20.api.repositories import ReportsRepo, get_session
from atlas20.api.settings import get_settings


def _client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, db_session: Session) -> TestClient:
    monkeypatch.setenv("ATLAS20_REPORT_ROOT", str(tmp_path / "reports"))
    monkeypatch.setenv("ATLAS20_DATA_ROOT", str(tmp_path / "data"))
    monkeypatch.setenv("ATLAS20_DB_URL", f"sqlite:///{(tmp_path / 'download.sqlite').as_posix()}")
    get_settings.cache_clear()
    app = create_app()

    def override_get_session():
        yield db_session

    app.dependency_overrides[get_session] = override_get_session
    return TestClient(app)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_report_manifest(run_dir: Path, artifacts: list[dict[str, object]]) -> None:
    run_dir.joinpath("report_manifest.json").write_text(
        json.dumps(
            {
                "run_id": run_dir.name,
                "generated_at": "2026-05-20T00:00:00Z",
                "artifacts": artifacts,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


def _add_report_row(
    db_session: Session,
    *,
    run_id: str = "btk_0142",
    kind: str = "markdown",
    path: str,
    sha256: str = "sha",
    size_bytes: int = 1,
) -> None:
    ReportsRepo(db_session).create(
        ReportFile(run_id=run_id, kind=kind, path=path, sha256=sha256, size_bytes=size_bytes)
    )


def test_download_rejects_symlink_escape(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, db_session: Session) -> None:
    """Reject downloads when a symlink points outside report_root.

    NOTE: this test will pytest.skip() on Windows hosts without symlink
    creation privilege (common dev case). The symlink-escape attack
    surface is real and this test MUST run on Linux CI to actually
    exercise the rejection path. Do not interpret a green run on a
    Windows dev box as coverage of this case.
    """
    client = _client(tmp_path, monkeypatch, db_session)
    report_root = get_settings().report_root
    run_dir = report_root / "app_runs" / "btk_0142"
    run_dir.mkdir(parents=True)
    outside = tmp_path / "outside.md"
    outside.write_text("secret", encoding="utf-8")
    link = run_dir / "digest.md"
    try:
        link.symlink_to(outside)
    except OSError as exc:
        pytest.skip(f"symlink creation unavailable: {exc}")
    _add_report_row(db_session, path="app_runs/btk_0142/digest.md", sha256=_sha256(outside), size_bytes=outside.stat().st_size)

    response = client.get("/api/reports/btk_0142/download?format=markdown")

    assert response.status_code == 403


def test_download_rejects_path_outside_report_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, db_session: Session
) -> None:
    client = _client(tmp_path, monkeypatch, db_session)
    report_root = get_settings().report_root
    outside = report_root.parent / "outside.md"
    outside.parent.mkdir(parents=True, exist_ok=True)
    outside.write_text("secret", encoding="utf-8")
    _add_report_row(db_session, path="../outside.md", sha256=_sha256(outside), size_bytes=outside.stat().st_size)

    response = client.get("/api/reports/btk_0142/download?format=markdown")

    assert response.status_code == 403


def test_download_rejects_file_missing_from_report_manifest(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, db_session: Session
) -> None:
    client = _client(tmp_path, monkeypatch, db_session)
    report_root = get_settings().report_root
    run_dir = report_root / "app_runs" / "btk_0142"
    run_dir.mkdir(parents=True)
    digest = run_dir / "digest.md"
    digest.write_bytes(b"# Digest\n")
    _write_report_manifest(run_dir, [])
    _add_report_row(db_session, path="app_runs/btk_0142/digest.md", sha256=_sha256(digest), size_bytes=digest.stat().st_size)

    response = client.get("/api/reports/btk_0142/download?format=markdown")

    assert response.status_code == 403


def test_download_rejects_manifest_sha256_mismatch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, db_session: Session
) -> None:
    client = _client(tmp_path, monkeypatch, db_session)
    report_root = get_settings().report_root
    run_dir = report_root / "app_runs" / "btk_0142"
    run_dir.mkdir(parents=True)
    digest = run_dir / "digest.md"
    digest.write_text("# Digest\n", encoding="utf-8")
    _write_report_manifest(
        run_dir,
        [{"kind": "markdown", "path": "digest.md", "sha256": "bad-sha", "size": digest.stat().st_size}],
    )
    _add_report_row(db_session, path="app_runs/btk_0142/digest.md", sha256=_sha256(digest), size_bytes=digest.stat().st_size)

    response = client.get("/api/reports/btk_0142/download?format=markdown")

    assert response.status_code == 403


def test_download_allows_valid_manifest_sha256(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, db_session: Session
) -> None:
    client = _client(tmp_path, monkeypatch, db_session)
    report_root = get_settings().report_root
    run_dir = report_root / "app_runs" / "btk_0142"
    run_dir.mkdir(parents=True)
    digest = run_dir / "digest.md"
    digest.write_bytes(b"# Digest\n")
    digest_sha = _sha256(digest)
    _write_report_manifest(
        run_dir,
        [{"kind": "markdown", "path": "digest.md", "sha256": digest_sha, "size": digest.stat().st_size}],
    )
    _add_report_row(db_session, path="app_runs/btk_0142/digest.md", sha256=digest_sha, size_bytes=digest.stat().st_size)

    response = client.get("/api/reports/btk_0142/download?format=markdown")

    assert response.status_code == 200
    assert response.content == b"# Digest\n"


def test_download_rejects_bare_disk_fallback_without_manifest_or_db_sha(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, db_session: Session
) -> None:
    client = _client(tmp_path, monkeypatch, db_session)
    report_root = get_settings().report_root
    run_dir = report_root / "app_runs" / "btk_0001"
    run_dir.mkdir(parents=True)
    (run_dir / "digest.md").write_text("# Planted\n", encoding="utf-8")

    response = client.get("/api/reports/btk_0001/download?format=markdown")

    assert response.status_code == 403
