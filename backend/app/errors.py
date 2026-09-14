"""One error shape for the whole API.

Normalizes FastAPI's three failure shapes (422 validation, 404 HTTPException,
raw 500) into one `ErrorEnvelope`. Validation failures report as 400, not
422, matching how the brief frames bad input.
"""

from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from .models import ErrorBody, ErrorDetail, ErrorEnvelope, query_alias

logger = logging.getLogger(__name__)


def _envelope(status: int, code: str, message: str, details: list[ErrorDetail]) -> JSONResponse:
    """The one error response shape this API ever returns."""
    return JSONResponse(
        status_code=status,
        content=ErrorEnvelope(
            error=ErrorBody(code=code, message=message, details=details)
        ).model_dump(),
    )


def _field_name(loc: tuple) -> str | None:
    """Turn Pydantic's ("query", "page_size") into "pageSize"."""
    parts = [query_alias(str(p)) for p in loc if p not in ("query", "body", "path")]
    return ".".join(parts) or None


def _message(raw: str) -> str:
    """Drop Pydantic's "Value error, " prefix from custom validator messages."""
    return raw.removeprefix("Value error, ")


def register_error_handlers(app: FastAPI) -> None:
    """Install the handlers that normalize every failure into `ErrorEnvelope`."""

    @app.exception_handler(RequestValidationError)
    async def on_validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
        """Bad query parameters -> 400, listing every offending field at once."""
        details = [
            ErrorDetail(
                field=_field_name(e.get("loc", ())),
                issue=_message(e.get("msg", "invalid")),
            )
            for e in exc.errors()
        ]
        return _envelope(
            400, "INVALID_REQUEST", "One or more query parameters are invalid.", details
        )

    @app.exception_handler(StarletteHTTPException)
    async def on_http_error(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        """Re-wrap deliberate HTTP errors (404, 405) in the shared envelope."""
        codes = {404: "NOT_FOUND", 405: "METHOD_NOT_ALLOWED"}
        return _envelope(
            exc.status_code,
            codes.get(exc.status_code, "HTTP_ERROR"),
            str(exc.detail),
            [],
        )

    @app.exception_handler(Exception)
    async def on_unexpected_error(_: Request, exc: Exception) -> JSONResponse:
        """Last resort: log the cause, return a clean 500 with no internals leaked."""
        logger.exception("Unhandled error", exc_info=exc)
        return _envelope(
            500, "INTERNAL_ERROR", "An unexpected error occurred.", []
        )
