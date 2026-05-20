from __future__ import annotations

import json
import logging
from pathlib import Path

import pytest

from atlas20.api.db.models import ReportFile
from atlas20.api.manifest import ReportArtifact, sha256_file, verify_manifest_artifact, write_report_manifest
from atlas20.api.services_report import _artifacts_from_rows
from atlas20.api.settings import Settings


def _artifact(kind: str, path: Path) -> ReportArtifact:
    return ReportArtifact(kind=kind, path=path, sha256=sha256_file(path), size=path.stat().st_size)


def test_report_manifest_written_with_expected_schema(tmp_path: Path) -> None:
    run_dir = tmp_path / "reports" / "app_runs" / "btk_0142"
    run_dir.mkdir(parents=True)
    digest = run_dir / "digest.md"
    digest.write_text("# Digest\n", encoding="utf-8")

    manifest_path = write_report_manifest("btk_0142", run_dir, [_artifact("markdown", digest)])

    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert payload["run_id"] == "btk_0142"
    assert payload["generated_at"].endswith("Z")
    assert payload["artifacts"] == [
        {"kind": "markdown", "path": "digest.md", "sha256": sha256_file(digest), "size": digest.stat().st_size}
    ]


def test_report_manifest_sha256_matches_file_content(tmp_path: Path) -> None:
    run_dir = tmp_path / "reports" / "app_runs" / "btk_0142"
    run_dir.mkdir(parents=True)
    digest = run_dir / "digest.md"
    digest.write_text("# Digest\n", encoding="utf-8")
    write_report_manifest("btk_0142", run_dir, [_artifact("markdown", digest)])

    assert verify_manifest_artifact(run_dir, digest) is True


def test_report_manifest_merges_partial_regeneration_artifacts(tmp_path: Path) -> None:
    run_dir = tmp_path / "reports" / "app_runs" / "btk_0142"
    run_dir.mkdir(parents=True)
    digest = run_dir / "digest.md"
    digest.write_text("# Digest\n", encoding="utf-8")
    png = run_dir / "equity_curve.png"
    png.write_bytes(b"png-data")

    write_report_manifest("btk_0142", run_dir, [_artifact("markdown", digest)])
    manifest_path = write_report_manifest("btk_0142", run_dir, [_artifact("png", png)])

    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert [artifact["kind"] for artifact in payload["artifacts"]] == ["markdown", "png"]
    assert verify_manifest_artifact(run_dir, digest) is True
    assert verify_manifest_artifact(run_dir, png) is True


def test_write_manifest_recovers_from_non_dict_payload(tmp_path: Path) -> None:
    run_dir = tmp_path / "reports" / "app_runs" / "btk_0142"
    run_dir.mkdir(parents=True)
    digest = run_dir / "digest.md"
    digest.write_text("# Digest\n", encoding="utf-8")
    (run_dir / "report_manifest.json").write_text("[1, 2, 3]\n", encoding="utf-8")

    manifest_path = write_report_manifest("btk_0142", run_dir, [_artifact("markdown", digest)])

    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert payload["artifacts"] == [
        {"kind": "markdown", "path": "digest.md", "sha256": sha256_file(digest), "size": digest.stat().st_size}
    ]


def test_write_manifest_recovers_from_non_list_artifacts(tmp_path: Path, caplog) -> None:
    run_dir = tmp_path / "reports" / "app_runs" / "btk_0142"
    run_dir.mkdir(parents=True)
    digest = run_dir / "digest.md"
    digest.write_text("# Digest\n", encoding="utf-8")
    (run_dir / "report_manifest.json").write_text('{"artifacts": 1}\n', encoding="utf-8")

    with caplog.at_level(logging.WARNING, logger="atlas20.api.manifest"):
        manifest_path = write_report_manifest("btk_0142", run_dir, [_artifact("markdown", digest)])

    assert "non-list artifacts" in caplog.text
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert payload["artifacts"] == [
        {"kind": "markdown", "path": "digest.md", "sha256": sha256_file(digest), "size": digest.stat().st_size}
    ]


def test_write_manifest_recovers_from_unreadable_existing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    (run_dir / "report_manifest.json").write_text('{"artifacts": []}', encoding="utf-8")

    original_read_text = Path.read_text
    raised = False

    def _boom(self: Path, *args, **kwargs):
        nonlocal raised
        if self.name == "report_manifest.json" and not raised:
            raised = True
            raise PermissionError("denied")
        return original_read_text(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", _boom)

    artifact = ReportArtifact(kind="markdown", path="digest.md", sha256="abc", size=1)
    with caplog.at_level("WARNING", logger="atlas20.api.manifest"):
        write_report_manifest("btk_0001", run_dir, [artifact])

    assert any("unreadable" in rec.message for rec in caplog.records)
    payload = json.loads((run_dir / "report_manifest.json").read_text(encoding="utf-8"))
    assert [a["kind"] for a in payload["artifacts"]] == ["markdown"]


def test_artifacts_from_rows_uses_row_sha256(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    settings = Settings(report_root=tmp_path / "reports")
    run_dir = settings.report_root / "app_runs" / "btk_0142"
    run_dir.mkdir(parents=True)
    digest = run_dir / "digest.md"
    digest.write_text("# Digest\n", encoding="utf-8")
    row = ReportFile(
        run_id="btk_0142",
        kind="markdown",
        path="app_runs/btk_0142/digest.md",
        sha256="known-sha",
        size_bytes=digest.stat().st_size,
    )

    def _boom(*args, **kwargs):
        raise AssertionError("sha256_file should not be called")

    monkeypatch.setattr("atlas20.api.services_report.sha256_file", _boom)
    monkeypatch.setattr("atlas20.api.manifest.sha256_file", _boom)

    artifacts = _artifacts_from_rows(settings, [row])
    manifest_path = write_report_manifest("btk_0142", run_dir, artifacts)

    assert artifacts == [
        ReportArtifact(kind="markdown", path=digest, sha256="known-sha", size=digest.stat().st_size)
    ]
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert payload["artifacts"] == [
        {"kind": "markdown", "path": "digest.md", "sha256": "known-sha", "size": digest.stat().st_size}
    ]
