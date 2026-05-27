"""Download resolution for report artifacts."""

from __future__ import annotations

from pathlib import Path
import re

from fastapi import HTTPException
from sqlmodel import Session

from atlas20.api.manifest import read_report_manifest, sha256_file, verify_manifest_artifact
from atlas20.api.repositories import KvRepo, ReportsRepo
from atlas20.api.schemas import ReportFormat
from atlas20.api.settings import Settings, get_settings

FORMAT_KIND = {
    "markdown": "markdown",
    "pdf": "pdf",
    "png": "png",
    "csv": "csv",
    "bundle": "bundle",
}
FORMAT_FILENAME = {
    "markdown": "digest.md",
    "pdf": "digest.pdf",
    "png": "equity_curve.png",
    "csv": "summary.csv",
    "bundle": "bundle.zip",
}
CONTENT_TYPES = {
    "markdown": "text/markdown",
    "pdf": "application/pdf",
    "png": "image/png",
    "csv": "text/csv",
    "bundle": "application/zip",
}
SAFE_FILENAME_CHARS = re.compile(r"[^\w.-]+", re.UNICODE)


def _sanitize_filename(filename: str) -> str:
    name = Path(filename).name
    cleaned = SAFE_FILENAME_CHARS.sub("_", name).strip("._")
    return cleaned or "report"


def _resolve_under_report_root(path: Path, settings: Settings) -> Path:
    report_root = Path(settings.report_root).resolve()
    resolved = Path(path).resolve()
    try:
        resolved.relative_to(report_root)
    except ValueError as exc:
        raise HTTPException(status_code=403, detail="report path outside report_root") from exc
    if not resolved.is_file():
        raise HTTPException(status_code=404, detail="report artifact not found")
    return resolved


def _run_dir_for_path(path: Path, settings: Settings, run_id: str | None) -> Path | None:
    if run_id:
        return Path(settings.report_root) / "app_runs" / run_id
    try:
        relative = path.resolve().relative_to(Path(settings.report_root).resolve())
    except ValueError:
        return None
    parts = relative.parts
    if len(parts) >= 3 and parts[0] == "app_runs":
        return Path(settings.report_root) / "app_runs" / parts[1]
    return None


def _manifest_includes_path(run_dir: Path, artifact_path: Path) -> bool:
    payload = read_report_manifest(run_dir)
    if payload is None:
        return False
    try:
        relative_path = Path(artifact_path).resolve().relative_to(Path(run_dir).resolve()).as_posix()
    except ValueError:
        return False
    artifacts = payload.get("artifacts")
    if not isinstance(artifacts, list):
        return False
    for artifact in artifacts:
        if isinstance(artifact, dict) and artifact.get("path") == relative_path:
            return True
    return False


def _validate_manifest_and_hash(path: Path, settings: Settings, *, run_id: str | None, expected_sha: str | None) -> None:
    run_dir = _run_dir_for_path(path, settings, run_id)
    manifest_path = (run_dir / "report_manifest.json") if run_dir is not None else None
    if manifest_path is not None and manifest_path.exists():
        if not verify_manifest_artifact(run_dir, path):
            if expected_sha is not None and not _manifest_includes_path(run_dir, path):
                if expected_sha == sha256_file(path):
                    return
            raise HTTPException(status_code=403, detail="report artifact failed manifest verification")
        return
    if expected_sha is not None:
        if expected_sha != sha256_file(path):
            raise HTTPException(status_code=403, detail="report artifact sha256 mismatch")
        return
    raise HTTPException(
        status_code=403,
        detail="report artifact has no manifest or registered sha256; regenerate via POST /api/reports/generate",
    )


def _fallback_run_path(report_id: str, fmt: str, settings: Settings) -> Path | None:
    run_dir = Path(settings.report_root) / "app_runs" / report_id
    candidate = run_dir / FORMAT_FILENAME[fmt]
    if candidate.exists():
        return candidate
    if fmt == "csv":
        alternate = run_dir / "strategy_summary.csv"
        if alternate.exists():
            return alternate
    return None


def _latest_markdown_report(settings: Settings) -> Path | None:
    latest_dir = Path(settings.report_root) / "latest"
    if not latest_dir.is_dir():
        return None
    candidates = [path for path in latest_dir.glob("*.md") if path.is_file()]
    return max(candidates, key=lambda path: path.stat().st_mtime) if candidates else None


def _resolve_report_file(
    report_id: str,
    fmt: str | None,
    session: Session,
    settings: Settings,
) -> tuple[Path, str | None, str | None]:
    repo = ReportsRepo(session)

    # If no format specified, return the file matching the ID directly
    if fmt is None:
        if report_id.isdigit():
            row = repo.get(int(report_id))
            if row is not None:
                return Path(settings.report_root) / row.path, row.run_id, row.sha256
        fallback = _fallback_run_path(report_id, "markdown", settings)
        if fallback is not None:
            return fallback, report_id, None
        raise HTTPException(status_code=404, detail="report not found")

    kind = FORMAT_KIND[fmt]

    row = None
    if report_id.isdigit():
        row = repo.get(int(report_id))
        if row is not None and row.kind != kind:
            row = repo.by_run_kind(row.run_id, kind) if row.run_id else None
    if row is None:
        row = repo.by_run_kind(report_id, kind)

    if row is not None:
        return Path(settings.report_root) / row.path, row.run_id, row.sha256

    fallback = _fallback_run_path(report_id, fmt, settings)
    if fallback is not None:
        return fallback, report_id, None
    raise HTTPException(status_code=404, detail="report not found")


def _resolve_featured_file(fmt: str, session: Session, settings: Settings) -> tuple[Path, str | None, str | None]:
    run_id = KvRepo(session).get("featured_digest_run_id")
    if run_id:
        row = ReportsRepo(session).by_run_kind(run_id, FORMAT_KIND[fmt])
        if row is not None:
            return Path(settings.report_root) / row.path, row.run_id, row.sha256
        # Fallback: try the requested format on disk
        fallback = _fallback_run_path(run_id, fmt, settings)
        if fallback is not None:
            return fallback, run_id, None
    if fmt == "markdown":
        latest_markdown = _latest_markdown_report(settings)
        if latest_markdown is not None:
            return latest_markdown, None, sha256_file(latest_markdown)
    raise HTTPException(
        status_code=404,
        detail="featured digest not yet generated; trigger via POST /api/reports/generate or the weekly scheduler",
    )


def resolve_download(
    report_id: str,
    fmt: ReportFormat | str | None,
    session: Session,
    *,
    settings: Settings | None = None,
) -> tuple[Path, str, str]:
    settings = settings or get_settings()
    format_value = str(fmt) if fmt is not None else None

    if report_id == "featured":
        # Featured digest always needs a format
        if format_value is None:
            format_value = "markdown"
        if format_value not in FORMAT_KIND:
            raise HTTPException(status_code=422, detail="unsupported report format")
        path, run_id, expected_sha = _resolve_featured_file(format_value, session, settings)
    else:
        if format_value is not None and format_value not in FORMAT_KIND:
            raise HTTPException(status_code=422, detail="unsupported report format")
        path, run_id, expected_sha = _resolve_report_file(report_id, format_value, session, settings)

    resolved = _resolve_under_report_root(path, settings)
    _validate_manifest_and_hash(resolved, settings, run_id=run_id, expected_sha=expected_sha)
    content_type = CONTENT_TYPES.get(format_value, "application/octet-stream") if format_value else "application/octet-stream"
    return resolved, content_type, _sanitize_filename(resolved.name)
