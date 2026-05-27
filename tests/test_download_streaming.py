from __future__ import annotations

import hashlib
import json
import zipfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from atlas20.api.app import create_app
from atlas20.api.db.models import ReportFile
from atlas20.api.repositories import KvRepo, ReportsRepo, get_session
from atlas20.api.settings import get_settings


def _client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, db_session: Session) -> TestClient:
    monkeypatch.setenv("ATLAS20_REPORT_ROOT", str(tmp_path / "reports"))
    monkeypatch.setenv("ATLAS20_DATA_ROOT", str(tmp_path / "data"))
    monkeypatch.setenv("ATLAS20_DB_URL", f"sqlite:///{(tmp_path / 'streaming.sqlite').as_posix()}")
    get_settings.cache_clear()
    app = create_app()

    def override_get_session():
        yield db_session

    app.dependency_overrides[get_session] = override_get_session
    return TestClient(app)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_manifest(run_dir: Path, kind: str, path: str, sha256: str, size: int) -> None:
    run_dir.joinpath("report_manifest.json").write_text(
        json.dumps(
            {
                "run_id": run_dir.name,
                "generated_at": "2026-05-20T00:00:00Z",
                "artifacts": [{"kind": kind, "path": path, "sha256": sha256, "size": size}],
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


def test_report_download_streams_markdown_with_attachment_headers(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, db_session: Session
) -> None:
    client = _client(tmp_path, monkeypatch, db_session)
    report_root = get_settings().report_root
    run_dir = report_root / "app_runs" / "btk_0142"
    run_dir.mkdir(parents=True)
    digest = run_dir / "digest.md"
    digest.write_text("# Digest\n", encoding="utf-8")
    digest_sha = _sha256(digest)
    _write_manifest(run_dir, "markdown", "digest.md", digest_sha, digest.stat().st_size)
    ReportsRepo(db_session).create(
        ReportFile(
            run_id="btk_0142",
            kind="markdown",
            path="app_runs/btk_0142/digest.md",
            sha256=digest_sha,
            size_bytes=digest.stat().st_size,
        )
    )

    response = client.get("/api/reports/btk_0142/download?format=markdown")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/markdown")
    assert "attachment" in response.headers["content-disposition"]
    assert b"# Digest" in response.content


def test_download_routes_require_api_key_when_configured(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, db_session: Session
) -> None:
    monkeypatch.setenv("ATLAS20_API_KEYS", "download-secret")
    client = _client(tmp_path, monkeypatch, db_session)

    report_response = client.get("/api/reports/btk_0142/download?format=markdown")
    digest_response = client.get("/api/reports/digest/download?format=markdown")
    authed_response = client.get(
        "/api/reports/btk_0142/download?format=markdown",
        headers={"X-API-Key": "download-secret"},
    )

    assert report_response.status_code == 401
    assert digest_response.status_code == 401
    assert authed_response.status_code != 401


def test_featured_digest_download_ignores_unrelated_disk_artifacts_without_db_row(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, db_session: Session
) -> None:
    client = _client(tmp_path, monkeypatch, db_session)
    report_root = get_settings().report_root
    run_dir = report_root / "app_runs" / "btk_unrelated"
    run_dir.mkdir(parents=True)
    digest = run_dir / "digest.md"
    digest.write_text("# Unrelated\n", encoding="utf-8")
    digest_sha = _sha256(digest)
    _write_manifest(run_dir, "markdown", "digest.md", digest_sha, digest.stat().st_size)

    response = client.get("/api/reports/digest/download?format=markdown")
    assert response.status_code == 404

    KvRepo(db_session).set("featured_digest_run_id", "btk_0142")
    response = client.get("/api/reports/digest/download?format=markdown")
    assert response.status_code == 404


def test_featured_digest_download_falls_back_to_latest_markdown(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, db_session: Session
) -> None:
    client = _client(tmp_path, monkeypatch, db_session)
    report_root = get_settings().report_root
    latest = report_root / "latest"
    latest.mkdir(parents=True)
    latest.joinpath("atlas20_report.md").write_text("# Latest Digest\n", encoding="utf-8")

    response = client.get("/api/reports/digest/download?format=markdown")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/markdown")
    assert b"Latest Digest" in response.content


def test_featured_digest_download_streams_bundle(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, db_session: Session
) -> None:
    client = _client(tmp_path, monkeypatch, db_session)
    report_root = get_settings().report_root
    run_dir = report_root / "app_runs" / "btk_0142"
    run_dir.mkdir(parents=True)
    bundle = run_dir / "bundle.zip"
    with zipfile.ZipFile(bundle, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("digest.md", "# Digest\n")
    bundle_sha = _sha256(bundle)
    _write_manifest(run_dir, "bundle", "bundle.zip", bundle_sha, bundle.stat().st_size)
    ReportsRepo(db_session).create(
        ReportFile(
            run_id="btk_0142",
            kind="bundle",
            path="app_runs/btk_0142/bundle.zip",
            sha256=bundle_sha,
            size_bytes=bundle.stat().st_size,
        )
    )
    KvRepo(db_session).set("featured_digest_run_id", "btk_0142")

    response = client.get("/api/reports/digest/download?format=bundle")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/zip")
    assert response.content.startswith(b"PK")


def test_report_download_allows_registered_artifact_when_manifest_omits_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, db_session: Session
) -> None:
    client = _client(tmp_path, monkeypatch, db_session)
    report_root = get_settings().report_root
    run_dir = report_root / "app_runs" / "btk_0142"
    run_dir.mkdir(parents=True)
    digest = run_dir / "digest.md"
    digest.write_text("# Digest\n", encoding="utf-8")
    digest_sha = _sha256(digest)
    csv = run_dir / "strategy_summary.csv"
    csv.write_text("strategy,total_return\nbase,1.23\n", encoding="utf-8")
    csv_sha = _sha256(csv)
    _write_manifest(run_dir, "markdown", "digest.md", digest_sha, digest.stat().st_size)
    row = ReportsRepo(db_session).create(
        ReportFile(
            run_id="btk_0142",
            kind="csv",
            path="app_runs/btk_0142/strategy_summary.csv",
            sha256=csv_sha,
            size_bytes=csv.stat().st_size,
        )
    )

    response = client.get(f"/api/reports/{row.id}/download")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    assert response.text.startswith("strategy,total_return")


def test_featured_digest_bundle_download_does_not_fallback_to_markdown(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, db_session: Session
) -> None:
    client = _client(tmp_path, monkeypatch, db_session)
    report_root = get_settings().report_root
    run_dir = report_root / "app_runs" / "btk_0142"
    run_dir.mkdir(parents=True)
    digest = run_dir / "digest.md"
    digest.write_text("# Digest\n", encoding="utf-8")
    digest_sha = _sha256(digest)
    _write_manifest(run_dir, "markdown", "digest.md", digest_sha, digest.stat().st_size)
    ReportsRepo(db_session).create(
        ReportFile(
            run_id="btk_0142",
            kind="markdown",
            path="app_runs/btk_0142/digest.md",
            sha256=digest_sha,
            size_bytes=digest.stat().st_size,
        )
    )
    KvRepo(db_session).set("featured_digest_run_id", "btk_0142")

    response = client.get("/api/reports/digest/download?format=bundle")

    assert response.status_code == 404
