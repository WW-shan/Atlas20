"""Unified API error response helpers."""

from __future__ import annotations

from http import HTTPStatus
import logging
from collections.abc import Mapping
from typing import Any

from fastapi import Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.responses import JSONResponse

logger = logging.getLogger(__name__)


STATUS_ERROR_CODES = {
    400: "bad_request",
    401: "unauthorized",
    403: "forbidden",
    404: "not_found",
    409: "conflict",
    422: "validation_error",
    429: "rate_limited",
    500: "internal_server_error",
    503: "service_unavailable",
}


def error_code_for_status(status_code: int) -> str:
    if status_code in STATUS_ERROR_CODES:
        return STATUS_ERROR_CODES[status_code]
    if 400 <= status_code < 500:
        return "client_error"
    return "server_error"


def request_id_from_request(request: Request) -> str:
    request_id = getattr(request.state, "request_id", "")
    return request_id if isinstance(request_id, str) else ""


def build_error_response(
    request: Request,
    *,
    status_code: int,
    code: str,
    message: str,
    details: Any = None,
    headers: Mapping[str, str] | None = None,
) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={
            "error": {
                "code": code,
                "message": message,
                "details": jsonable_encoder(details),
                "request_id": request_id_from_request(request),
            }
        },
        headers=dict(headers) if headers is not None else None,
    )


async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    detail = exc.detail
    if isinstance(detail, str):
        message = detail
        details = None
    else:
        message = HTTPStatus(exc.status_code).phrase
        details = detail
    return build_error_response(
        request,
        status_code=exc.status_code,
        code=error_code_for_status(exc.status_code),
        message=message,
        details=details,
        headers=exc.headers,
    )


async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    return build_error_response(
        request,
        status_code=422,
        code="validation_error",
        message="Request validation failed",
        details=exc.errors(),
    )


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled API exception", exc_info=exc)
    return build_error_response(
        request,
        status_code=500,
        code="internal_server_error",
        message="Internal server error",
    )
