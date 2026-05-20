"""Reports API routes."""

import logging
from datetime import timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from fastapi.responses import FileResponse
from sqlmodel import Session, select

from atlas20.api.db.models import Run
from atlas20.api.dependencies.auth import verify_api_key
from atlas20.api.dependencies.ratelimit import limiter
from atlas20.api.repositories import get_session
from atlas20.api.schemas import FeaturedDigest, GenerateReportRequest, ReportEntry, ReportFormat, ReportId
from atlas20.api.services import get_featured_digest, list_reports, resolve_download
from atlas20.api.services_report import generate_run_report_with_warnings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["reports"])


@router.get("/reports/digest/featured", response_model=FeaturedDigest)
def get_digest_featured(session: Session = Depends(get_session)) -> FeaturedDigest:
    return get_featured_digest(session)


@router.get("/reports/digest/download", dependencies=[Depends(verify_api_key)])
def get_digest_download(
    format: ReportFormat = "markdown",
    session: Session = Depends(get_session),
) -> FileResponse:
    path, content_type, filename = resolve_download("featured", format, session)
    return FileResponse(path, media_type=content_type, filename=filename)


@router.get("/reports", response_model=list[ReportEntry], response_model_exclude_none=True)
def get_reports(
    sort: Literal["recent", "oldest", "size", "type"] = Query(default="recent"),
    session: Session = Depends(get_session),
) -> list[ReportEntry]:
    return list_reports(sort, session)


@router.post("/reports/generate", status_code=202, dependencies=[Depends(verify_api_key)])
@limiter.limit("5/minute")
def generate_report(
    request: Request,
    response: Response,
    req: GenerateReportRequest,
    session: Session = Depends(get_session),
) -> dict[str, object]:
    del request, response
    run_id = req.run_id or _select_generate_run_id(req, session)
    if run_id is None:
        return {
            "job_id": "report-none",
            "status": "completed",
            "files": [],
            "warnings": ["no completed run available for report generation"],
        }

    try:
        result = generate_run_report_with_warnings(run_id, set(req.formats), session=session)
    except HTTPException as exc:
        if req.run_id is not None:
            raise
        detail = getattr(exc, "detail", str(exc))
        logger.warning("Skipping legacy report generation for %s: %s", run_id, detail)
        return {
            "job_id": f"report-{run_id}",
            "status": "completed",
            "files": [],
            "warnings": [f"generation skipped: {detail}"],
        }

    return {
        "job_id": f"report-{run_id}",
        "status": "completed",
        "files": [_report_file_payload(row) for row in result.files],
        "warnings": result.warnings,
    }


@router.get("/reports/{report_id}/download", dependencies=[Depends(verify_api_key)])
def get_report_download(
    report_id: ReportId,
    format: ReportFormat | None = None,
    session: Session = Depends(get_session),
) -> FileResponse:
    path, content_type, filename = resolve_download(report_id, format, session)
    return FileResponse(path, media_type=content_type, filename=filename)


def _select_generate_run_id(req: GenerateReportRequest, session: Session) -> str | None:
    stmt = select(Run).where(Run.status == "completed")
    if req.strategy:
        stmt = stmt.where(Run.strategy == req.strategy)
    row = session.exec(stmt.order_by(Run.created_at.desc(), Run.run_id.desc()).limit(1)).first()
    return row.run_id if row is not None else None


def _report_file_payload(row) -> dict[str, object]:
    generated_at = row.generated_at
    if generated_at.tzinfo is None:
        generated_at = generated_at.replace(tzinfo=timezone.utc)
    return {
        "id": str(row.id),
        "run_id": row.run_id,
        "kind": row.kind,
        "path": row.path,
        "sha256": row.sha256,
        "size_bytes": row.size_bytes,
        "generated_at": generated_at.isoformat(timespec="seconds").replace("+00:00", "Z"),
    }
