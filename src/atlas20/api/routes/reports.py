"""Reports API routes."""

from typing import Literal

from fastapi import APIRouter, HTTPException, Query

from atlas20.api.schemas import FeaturedDigest, ReportEntry, ReportFormat
from atlas20.api.services import (
    build_digest_download_url,
    build_report_download_url,
    get_featured_digest,
    list_reports,
)

router = APIRouter(prefix="/api", tags=["reports"])


@router.get("/reports/digest/featured", response_model=FeaturedDigest)
def get_digest_featured() -> FeaturedDigest:
    return get_featured_digest()


@router.get("/reports/digest/download")
def get_digest_download(
    format: Literal["markdown", "pdf", "png", "csv", "bundle"] = "markdown",
) -> dict[str, str]:
    return build_digest_download_url(format)


@router.get("/reports", response_model=list[ReportEntry], response_model_exclude_none=True)
def get_reports(
    sort: Literal["recent", "oldest", "size", "type"] = Query(default="recent"),
) -> list[ReportEntry]:
    return list_reports(sort)


@router.get("/reports/{report_id}/download")
def get_report_download(
    report_id: str,
    format: ReportFormat | None = None,
) -> dict[str, str]:
    result = build_report_download_url(report_id, format)
    if result is None:
        raise HTTPException(status_code=404, detail="report not found")
    return result
