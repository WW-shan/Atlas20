"""Report manifest hashing and whitelist checks."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import logging
import os
import uuid
from pathlib import Path
from typing import Any

from atlas20.api._time import utc_now_iso

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ReportArtifact:
    kind: str
    path: Path | str
    sha256: str
    size: int


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _relative_to_run_dir(run_dir: Path, artifact_path: Path) -> str:
    run_root = run_dir.resolve()
    resolved = artifact_path.resolve()
    return resolved.relative_to(run_root).as_posix()


def _artifact_manifest_path(run_dir: Path, artifact_path: Path) -> str:
    if artifact_path.is_absolute():
        return _relative_to_run_dir(run_dir, artifact_path)
    return artifact_path.as_posix()


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    tmp_path = path.with_name(f"{path.name}.tmp_{os.getpid()}_{uuid.uuid4().hex[:8]}")
    tmp_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(tmp_path, path)


def write_report_manifest(run_id: str, run_dir: Path, artifacts: list[ReportArtifact]) -> Path:
    run_dir = Path(run_dir)
    manifest_path = run_dir / "report_manifest.json"
    existing: dict[str, dict[str, Any]] = {}
    if manifest_path.exists():
        try:
            existing_payload = json.loads(manifest_path.read_text(encoding="utf-8"))
            if isinstance(existing_payload, dict):
                artifacts_payload = existing_payload.get("artifacts", [])
                if isinstance(artifacts_payload, list):
                    for entry in artifacts_payload:
                        if not isinstance(entry, dict):
                            logger.warning(
                                "existing manifest at %s has non-dict artifact entry; skipping",
                                manifest_path,
                            )
                            continue
                        kind = entry.get("kind")
                        if not isinstance(kind, str) or not kind:
                            logger.warning(
                                "existing manifest at %s has artifact entry without string kind; skipping",
                                manifest_path,
                            )
                            continue
                        existing[kind] = entry
                else:
                    logger.warning(
                        "existing manifest at %s has non-list artifacts (%s); overwriting",
                        manifest_path,
                        type(artifacts_payload).__name__,
                    )
            else:
                logger.warning(
                    "existing manifest at %s parsed to non-dict (%s); overwriting",
                    manifest_path,
                    type(existing_payload).__name__,
                )
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("existing manifest at %s unreadable (%s); overwriting", manifest_path, exc)

    new_kinds = {artifact.kind for artifact in artifacts}
    rows = [existing[kind] for kind in existing if kind not in new_kinds]
    for artifact in artifacts:
        artifact_path = Path(artifact.path)
        rows.append(
            {
                "kind": artifact.kind,
                "path": _artifact_manifest_path(run_dir, artifact_path),
                "sha256": artifact.sha256,
                "size": artifact.size,
            }
        )
    _atomic_write_json(
        manifest_path,
        {
            "run_id": run_id,
            "generated_at": utc_now_iso(),
            "artifacts": rows,
        },
    )
    return manifest_path


def read_report_manifest(run_dir: Path) -> dict[str, Any] | None:
    manifest_path = Path(run_dir) / "report_manifest.json"
    if not manifest_path.exists():
        return None
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        return None
    return payload


def verify_manifest_artifact(run_dir: Path, artifact_path: Path) -> bool:
    payload = read_report_manifest(run_dir)
    if payload is None:
        return True
    try:
        relative_path = _relative_to_run_dir(Path(run_dir), Path(artifact_path))
    except ValueError:
        return False
    artifacts = payload.get("artifacts")
    if not isinstance(artifacts, list):
        return False
    for artifact in artifacts:
        if not isinstance(artifact, dict) or artifact.get("path") != relative_path:
            continue
        expected_sha = artifact.get("sha256")
        if not isinstance(expected_sha, str):
            return False
        if expected_sha != sha256_file(Path(artifact_path)):
            return False
        expected_size = artifact.get("size")
        if expected_size is not None:
            try:
                if int(expected_size) != Path(artifact_path).stat().st_size:
                    return False
            except (TypeError, ValueError):
                return False
        return True
    return False
