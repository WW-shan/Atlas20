"""Reports API routes."""

import logging
from datetime import timezone
from pathlib import Path
from typing import Literal, cast

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from fastapi.responses import FileResponse
from sqlmodel import Session

from atlas20.api._metrics import REPORT_FORMATS, record_report_generation
from atlas20.api.db.models import ReportFile
from atlas20.api.dependencies.auth import verify_api_key
from atlas20.api.dependencies.ratelimit import limiter
from atlas20.api.repositories import RunsRepo, get_session
from atlas20.api.schemas import (
    FeaturedDigest,
    GeneratedReportFile,
    GenerateReportRequest,
    GenerateReportResponse,
    ReportEntry,
    ReportFormat,
    ReportId,
)
from atlas20.api.services import ConsoleService, get_console_service
from atlas20.api.services_report import generate_run_report_with_warnings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["reports"])


@router.get("/reports/digest/featured", response_model=FeaturedDigest)
def get_digest_featured(
    session: Session = Depends(get_session),
    service: ConsoleService = Depends(get_console_service),
) -> FeaturedDigest:
    return service.get_featured_digest(session)


@router.get("/reports/digest/download", dependencies=[Depends(verify_api_key)])
def get_digest_download(
    format: ReportFormat = "markdown",
    session: Session = Depends(get_session),
    service: ConsoleService = Depends(get_console_service),
) -> FileResponse:
    path, content_type, filename = service.resolve_download("featured", format, session)
    return FileResponse(path, media_type=content_type, filename=filename)


@router.get("/reports", response_model=list[ReportEntry], response_model_exclude_none=True)
def get_reports(
    sort: Literal["recent", "oldest", "size", "type"] = Query(default="recent"),
    session: Session = Depends(get_session),
    service: ConsoleService = Depends(get_console_service),
) -> list[ReportEntry]:
    return service.list_reports(sort, session)


@router.post(
    "/reports/generate",
    status_code=202,
    response_model=GenerateReportResponse,
    dependencies=[Depends(verify_api_key)],
)
@limiter.limit("5/minute")
def generate_report(
    request: Request,
    response: Response,
    req: GenerateReportRequest,
    session: Session = Depends(get_session),
) -> GenerateReportResponse:
    del request, response
    run_id = req.run_id or _select_generate_run_id(req, session)
    if run_id is None:
        _record_report_skipped(req.formats)
        return GenerateReportResponse(
            job_id="report-none",
            status="completed",
            files=[],
            warnings=["no completed run available for report generation"],
        )

    try:
        result = generate_run_report_with_warnings(run_id, set(req.formats), session=session)
    except HTTPException as exc:
        if req.run_id is not None:
            raise
        detail = getattr(exc, "detail", str(exc))
        logger.warning("Skipping legacy report generation for %s: %s", run_id, detail)
        _record_report_skipped(req.formats)
        return GenerateReportResponse(
            job_id=f"report-{run_id}",
            status="completed",
            files=[],
            warnings=[f"generation skipped: {detail}"],
        )

    return GenerateReportResponse(
        job_id=f"report-{run_id}",
        status="completed",
        files=[_report_file_payload(row) for row in result.files],
        warnings=result.warnings,
    )


@router.get("/reports/{report_id}/download", dependencies=[Depends(verify_api_key)])
def get_report_download(
    report_id: ReportId,
    format: ReportFormat | None = None,
    session: Session = Depends(get_session),
    service: ConsoleService = Depends(get_console_service),
) -> FileResponse:
    path, content_type, filename = service.resolve_download(report_id, format, session)
    # Infer content type from file extension when no format was specified
    if format is None:
        ext = Path(path).suffix.lower()
        mime_map = {".md": "text/markdown", ".png": "image/png", ".csv": "text/csv", ".pdf": "application/pdf", ".zip": "application/zip"}
        content_type = mime_map.get(ext, content_type)
    return FileResponse(path, media_type=content_type, filename=filename)


def _select_generate_run_id(req: GenerateReportRequest, session: Session) -> str | None:
    row = RunsRepo(session).find_latest_completed_by_strategy(req.strategy)
    return row.run_id if row is not None else None


def _record_report_skipped(formats: list[ReportFormat]) -> None:
    for fmt in formats:
        if fmt in REPORT_FORMATS:
            record_report_generation(fmt, "skipped")
        else:
            logger.info("ignoring unknown format in skipped metric path: %s", fmt)


def _report_file_payload(row: ReportFile) -> GeneratedReportFile:
    generated_at = row.generated_at
    if generated_at.tzinfo is None:
        generated_at = generated_at.replace(tzinfo=timezone.utc)
    return GeneratedReportFile(
        id=str(row.id),
        run_id=row.run_id,
        kind=cast(ReportFormat, row.kind),
        path=row.path,
        sha256=row.sha256,
        size_bytes=row.size_bytes,
        generated_at=generated_at.isoformat(timespec="seconds").replace("+00:00", "Z"),
    )
