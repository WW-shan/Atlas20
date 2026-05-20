"""Health and readiness probes."""

from __future__ import annotations

import os

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlmodel import Session

from atlas20.api.repositories import get_session
from atlas20.api.settings import get_settings

router = APIRouter(tags=["health"])


def _is_report_root_writable(path) -> bool:
    return os.access(path, os.W_OK)


@router.get("/healthz", include_in_schema=False)
def healthz() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/readyz", include_in_schema=False)
def readyz(session: Session = Depends(get_session)) -> JSONResponse:
    checks: dict[str, str] = {}
    status_code = 200
    try:
        session.exec(text("SELECT 1")).one()
        checks["db"] = "ok"
    except Exception:
        checks["db"] = "fail"
        status_code = 503

    settings = get_settings()
    if _is_report_root_writable(settings.report_root):
        checks["reports"] = "ok"
    else:
        checks["reports"] = "fail"
        status_code = 503

    status = "ready" if status_code == 200 else "not_ready"
    return JSONResponse(status_code=status_code, content={"status": status, "checks": checks})
