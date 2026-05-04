"""RFC 7807 Problem Details error handling for the API layer."""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import Request
from fastapi.responses import JSONResponse
import structlog

logger = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# Base application error hierarchy
# ---------------------------------------------------------------------------

class AppError(Exception):
    """Base exception that maps to an HTTP error response.

    Subclasses set *status_code* and *error_type* at the class level; individual
    instances may carry a human-readable *detail* message plus optional *extra*
    key-value pairs that are merged into the RFC 7807 body.
    """

    status_code: int = 500
    error_type: str = "internal_error"

    def __init__(self, detail: str = "An unexpected error occurred", **extra: Any) -> None:
        self.detail = detail
        self.extra = extra
        super().__init__(detail)


class NotFoundError(AppError):
    status_code = 404
    error_type = "not_found"

    def __init__(self, resource: str = "Resource", resource_id: str | None = None) -> None:
        detail = f"{resource} not found"
        if resource_id:
            detail = f"{resource} with id '{resource_id}' not found"
        super().__init__(detail, resource=resource)


class ConflictError(AppError):
    status_code = 409
    error_type = "conflict"


class ValidationError(AppError):
    status_code = 422
    error_type = "validation_error"


class AuthenticationError(AppError):
    status_code = 401
    error_type = "authentication_error"

    def __init__(self, detail: str = "Invalid or expired credentials") -> None:
        super().__init__(detail)


class AuthorizationError(AppError):
    status_code = 403
    error_type = "authorization_error"

    def __init__(self, detail: str = "Insufficient permissions") -> None:
        super().__init__(detail)


class RateLimitError(AppError):
    status_code = 429
    error_type = "rate_limit_exceeded"

    def __init__(self, detail: str = "Rate limit exceeded. Please try again later.") -> None:
        super().__init__(detail)


class BadRequestError(AppError):
    status_code = 400
    error_type = "bad_request"


class ServiceUnavailableError(AppError):
    status_code = 503
    error_type = "service_unavailable"


# ---------------------------------------------------------------------------
# RFC 7807 Problem Details response builder
# ---------------------------------------------------------------------------

def _build_problem_detail(
    request: Request,
    status: int,
    error_type: str,
    detail: str,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build an RFC 7807 Problem Details JSON body."""
    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    body: dict[str, Any] = {
        "type": f"urn:adobe-genai:error:{error_type}",
        "title": error_type.replace("_", " ").title(),
        "status": status,
        "detail": detail,
        "instance": str(request.url),
        "request_id": request_id,
    }
    if extra:
        body.update(extra)
    return body


# ---------------------------------------------------------------------------
# FastAPI exception handler
# ---------------------------------------------------------------------------

async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    """Convert any *AppError* subclass into an RFC 7807 Problem Details response."""
    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    logger.warning(
        "api.error",
        error_type=exc.error_type,
        status_code=exc.status_code,
        detail=exc.detail,
        request_id=request_id,
        path=str(request.url),
    )
    body = _build_problem_detail(
        request,
        status=exc.status_code,
        error_type=exc.error_type,
        detail=exc.detail,
        extra=exc.extra if exc.extra else None,
    )
    return JSONResponse(status_code=exc.status_code, content=body)


async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Catch-all for unhandled exceptions -- return a safe 500."""
    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    logger.exception(
        "api.unhandled_error",
        request_id=request_id,
        path=str(request.url),
        exc_info=exc,
    )
    body = _build_problem_detail(
        request,
        status=500,
        error_type="internal_error",
        detail="An unexpected internal error occurred",
    )
    return JSONResponse(status_code=500, content=body)
