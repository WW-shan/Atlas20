from __future__ import annotations

import json
import logging
from pathlib import Path

from atlas20.api.manifest import ReportArtifact, sha256_file, verify_manifest_artifact, write_report_manifest


def test_report_manifest_written_with_expected_schema(tmp_path: Path) -> None:
    run_dir = tmp_path / "reports" / "app_runs" / "btk_0142"
    run_dir.mkdir(parents=True)
    digest = run_dir / "digest.md"
    digest.write_text("# Digest\n", encoding="utf-8")

    manifest_path = write_report_manifest("btk_0142", run_dir, [ReportArtifact(kind="markdown", path=digest)])

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
    write_report_manifest("btk_0142", run_dir, [ReportArtifact(kind="markdown", path=digest)])

    assert verify_manifest_artifact(run_dir, digest) is True


def test_report_manifest_merges_partial_regeneration_artifacts(tmp_path: Path) -> None:
    run_dir = tmp_path / "reports" / "app_runs" / "btk_0142"
    run_dir.mkdir(parents=True)
    digest = run_dir / "digest.md"
    digest.write_text("# Digest\n", encoding="utf-8")
    png = run_dir / "equity_curve.png"
    png.write_bytes(b"png-data")

    write_report_manifest("btk_0142", run_dir, [ReportArtifact(kind="markdown", path=digest)])
    manifest_path = write_report_manifest("btk_0142", run_dir, [ReportArtifact(kind="png", path=png)])

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

    manifest_path = write_report_manifest("btk_0142", run_dir, [ReportArtifact(kind="markdown", path=digest)])

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
        manifest_path = write_report_manifest("btk_0142", run_dir, [ReportArtifact(kind="markdown", path=digest)])

    assert "non-list artifacts" in caplog.text
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert payload["artifacts"] == [
        {"kind": "markdown", "path": "digest.md", "sha256": sha256_file(digest), "size": digest.stat().st_size}
    ]
