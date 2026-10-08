"""Health and readiness probes."""

from __future__ import annotations

import logging
import os
from pathlib import Path

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlmodel import Session

from atlas20.api.data_freshness import evaluate_data_freshness
from atlas20.api.repositories import get_session
from atlas20.api.settings import Settings, get_settings

router = APIRouter(tags=["health"])
logger = logging.getLogger(__name__)


def _is_report_root_writable(path: Path) -> bool:
    return os.access(path, os.W_OK)


def _data_freshness_summary(settings: Settings) -> dict[str, str]:
    try:
        freshness = evaluate_data_freshness(settings)
    except Exception as exc:
        logger.warning("data freshness evaluation failed: %s", exc)
        return {"status": "unknown", "reason": "data freshness could not be evaluated"}
    return {"status": str(freshness["status"]), "reason": str(freshness["reason"])}


@router.get("/healthz", include_in_schema=False)
def healthz() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/readyz", include_in_schema=False)
def readyz(session: Session = Depends(get_session, scope="function")) -> JSONResponse:
    """Readiness of this process: database reachable and report root writable.

    Data freshness is reported but never gates readiness. The worker that
    refreshes the data starts only once the backend is ready, so gating on it
    would keep a fresh install unready forever. Alerting on stale data goes
    through /api/data/freshness and the data alerts instead.
    """
    checks: dict[str, str] = {}
    status_code = 200
    try:
        session.execute(text("SELECT 1")).one()
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
    return JSONResponse(
        status_code=status_code,
        content={"status": status, "checks": checks, "data_freshness": _data_freshness_summary(settings)},
    )
