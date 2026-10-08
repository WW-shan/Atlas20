"""Reports listed from disk (no DB rows) must be downloadable under the same protections."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re

from fastapi.testclient import TestClient
import pytest
from sqlmodel import Session

from atlas20.api.app import create_app
from atlas20.api.repositories import get_session
from atlas20.api.settings import get_settings


REPORT_ID = re.compile(r"^[a-z0-9_-]{1,64}$")


def _client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, db_session: Session) -> TestClient:
    monkeypatch.setenv("ATLAS20_REPORT_ROOT", str(tmp_path / "reports"))
    monkeypatch.setenv("ATLAS20_DATA_ROOT", str(tmp_path / "data"))
    monkeypatch.setenv("ATLAS20_DB_URL", f"sqlite:///{(tmp_path / 'disk-download.sqlite').as_posix()}")
    monkeypatch.delenv("ATLAS20_API_KEYS", raising=False)
    get_settings.cache_clear()
    app = create_app()

    def override_get_session():
        yield db_session

    app.dependency_overrides[get_session] = override_get_session
    return TestClient(app)


def _write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def _listed_ids_by_subtitle(client: TestClient) -> dict[str, str]:
    response = client.get("/api/reports")
    assert response.status_code == 200
    return {entry["subtitle"].split(" - ")[0]: entry["id"] for entry in response.json()}


def test_listed_disk_reports_are_downloadable_when_db_is_empty(tmp_path, monkeypatch, db_session: Session):
    client = _client(tmp_path, monkeypatch, db_session)
    report_root = tmp_path / "reports"
    _write(report_root / "latest" / "weekly_digest.md", "# Weekly digest\n")
    _write(report_root / "phase_momentum_2022" / "parameter_returns.csv", "param,return\n1,0.5\n")

    ids = _listed_ids_by_subtitle(client)

    assert set(ids) == {"latest/weekly_digest.md", "phase_momentum_2022/parameter_returns.csv"}
    digest = client.get(f"/api/reports/{ids['latest/weekly_digest.md']}/download")
    assert digest.status_code == 200
    assert digest.content == b"# Weekly digest\n"
    assert digest.headers["content-type"].startswith("text/markdown")
    assert digest.headers["content-disposition"].startswith("attachment;")
    assert 'filename="weekly_digest.md"' in digest.headers["content-disposition"]
    csv_download = client.get(f"/api/reports/{ids['phase_momentum_2022/parameter_returns.csv']}/download")
    assert csv_download.status_code == 200
    assert csv_download.content == b"param,return\n1,0.5\n"


def test_disk_report_ids_are_unique_for_colliding_and_long_paths(tmp_path, monkeypatch, db_session: Session):
    client = _client(tmp_path, monkeypatch, db_session)
    report_root = tmp_path / "reports"
    long_dir = "convex_overlay_sweep_2022_top20_validation_with_a_long_directory_name"
    files = {
        "latest/a.b.md": "dotted\n",
        "latest/a_b.md": "underscored\n",
        f"{long_dir}/summary_first.csv": "first\n",
        f"{long_dir}/summary_second.csv": "second\n",
    }
    for relative, text in files.items():
        _write(report_root / relative, text)

    ids = _listed_ids_by_subtitle(client)

    assert set(ids) == set(files)
    assert len(set(ids.values())) == len(files)
    assert all(REPORT_ID.fullmatch(report_id) for report_id in ids.values())
    for relative, text in files.items():
        response = client.get(f"/api/reports/{ids[relative]}/download")
        assert response.status_code == 200, relative
        assert response.content == text.encode()


def test_disk_report_download_honours_matching_format_only(tmp_path, monkeypatch, db_session: Session):
    client = _client(tmp_path, monkeypatch, db_session)
    _write(tmp_path / "reports" / "latest" / "atlas20_report.md", "# Latest\n")
    report_id = _listed_ids_by_subtitle(client)["latest/atlas20_report.md"]

    markdown = client.get(f"/api/reports/{report_id}/download?format=markdown")
    pdf = client.get(f"/api/reports/{report_id}/download?format=pdf")

    assert markdown.status_code == 200
    assert markdown.content == b"# Latest\n"
    assert pdf.status_code == 404


def test_listed_run_artifact_still_needs_its_report_manifest(tmp_path, monkeypatch, db_session: Session):
    client = _client(tmp_path, monkeypatch, db_session)
    report_root = tmp_path / "reports"
    _write(report_root / "app_runs" / "btk_0001" / "digest.md", "# Planted\n")
    verified = _write(report_root / "app_runs" / "btk_0002" / "digest.md", "# Verified\n")
    (verified.parent / "report_manifest.json").write_text(
        json.dumps(
            {
                "run_id": "btk_0002",
                "generated_at": "2026-05-20T00:00:00Z",
                "artifacts": [
                    {
                        "kind": "markdown",
                        "path": "digest.md",
                        "sha256": hashlib.sha256(verified.read_bytes()).hexdigest(),
                        "size": verified.stat().st_size,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    ids = _listed_ids_by_subtitle(client)

    planted = client.get(f"/api/reports/{ids['app_runs/btk_0001/digest.md']}/download")
    allowed = client.get(f"/api/reports/{ids['app_runs/btk_0002/digest.md']}/download")

    assert planted.status_code == 403
    assert allowed.status_code == 200
    assert allowed.content == b"# Verified\n"


def test_disk_catalogue_skips_symlinks_that_escape_report_root(tmp_path, monkeypatch, db_session: Session):
    client = _client(tmp_path, monkeypatch, db_session)
    secret = _write(tmp_path / "outside" / "secret.md", "# Secret\n")
    _write(tmp_path / "reports" / "latest" / "visible.md", "# Visible\n")
    (tmp_path / "reports" / "latest" / "escape.md").symlink_to(secret)

    ids = _listed_ids_by_subtitle(client)
    response = client.get("/api/reports/latest_escape_md/download")

    assert set(ids) == {"latest/visible.md"}
    assert response.status_code == 404
    assert b"Secret" not in response.content
