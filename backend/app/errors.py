"""One error shape for the whole API.

FastAPI's defaults would hand the frontend three different bodies: 422 with a
`detail` array for validation, 404 with a `detail` string for HTTPException,
and an HTML-ish 500 otherwise. The UI would need three parsers. These handlers
normalize everything to `ErrorEnvelope` so the frontend has exactly one
error-rendering path.

Validation failures are reported as **400**, not FastAPI's default 422: the
handout frames these as bad requests ("minPrice greater than maxPrice"), and
400 is what a client developer expects.
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
    """Build the one error response shape this API ever returns.

    Central so the handlers below cannot drift into emitting variants.
    """
    return JSONResponse(
        status_code=status,
        content=ErrorEnvelope(
            error=ErrorBody(code=code, message=message, details=details)
        ).model_dump(),
    )


def _field_name(loc: tuple) -> str | None:
    """Turn Pydantic's ("query", "page_size") location into "pageSize"."""
    parts = [query_alias(str(p)) for p in loc if p not in ("query", "body", "path")]
    return ".".join(parts) or None


def _message(raw: str) -> str:
    """Drop Pydantic's "Value error, " prefix from custom validator messages."""
    return raw.removeprefix("Value error, ")


def register_error_handlers(app: FastAPI) -> None:
    """Install the handlers that normalize every failure into `ErrorEnvelope`.

    Called once at app construction. Without it FastAPI emits three different
    error shapes and the frontend would need three parsers.
    """

    @app.exception_handler(RequestValidationError)
    async def on_validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
        """Bad query parameters -> 400, listing every offending field.

        Reported as 400 rather than FastAPI's default 422 because the brief
        frames these as bad requests, and all problems are returned at once so
        one round trip reveals everything the user must fix.
        """
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
        """Last resort: an unhandled exception becomes a clean 500.

        The brief asks that a clear error beat a crash. The cause is logged for
        the operator; the client gets nothing that leaks internals.
        """
        # Log the cause, but never leak internals to the client.
        logger.exception("Unhandled error", exc_info=exc)
        return _envelope(
            500, "INTERNAL_ERROR", "An unexpected error occurred.", []
        )
