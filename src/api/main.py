"""FastAPI application factory for the Creative Automation Pipeline API."""

from __future__ import annotations

import os
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import structlog

from src.api.errors import AppError, app_error_handler, generic_exception_handler
from src.cache import get_cache
from src.db.base import close_db, init_db

logger = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# Lifespan: startup / shutdown
# ---------------------------------------------------------------------------


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize DB and Redis cache on startup, dispose on shutdown."""
    logger.info("api.startup")
    await init_db()
    cache = get_cache()
    await cache.connect()
    yield
    logger.info("api.shutdown")
    await cache.close()
    await close_db()


# ---------------------------------------------------------------------------
# App factory
# ---------------------------------------------------------------------------


def create_app() -> FastAPI:
    """Build and return the configured FastAPI application."""
    app = FastAPI(
        title="Creative Automation Pipeline API",
        version="2.0.0",
        description="AI-powered creative automation platform API",
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=lifespan,
    )

    # ------------------------------------------------------------------
    # CORS -- reject wildcard "*" in production to prevent credential leaks
    # ------------------------------------------------------------------
    origins_raw = os.getenv("CORS_ORIGINS", "http://localhost:5173")
    origins = [o.strip() for o in origins_raw.split(",") if o.strip()]

    # Security: reject wildcard origin when running with real credentials
    if "*" in origins and os.getenv("SECRET_KEY"):
        logger.warning(
            "cors.wildcard_rejected",
            detail="CORS_ORIGINS='*' is not allowed outside local development. "
                   "Set explicit origins in CORS_ORIGINS.",
        )
        origins = ["http://localhost:5173"]

    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
    )

    # ------------------------------------------------------------------
    # Request-ID middleware
    # ------------------------------------------------------------------
    @app.middleware("http")
    async def request_id_middleware(request: Request, call_next):
        request_id = request.headers.get("x-request-id", str(uuid.uuid4()))
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers["x-request-id"] = request_id
        return response

    # ------------------------------------------------------------------
    # Structlog access-log middleware
    # ------------------------------------------------------------------
    @app.middleware("http")
    async def access_log_middleware(request: Request, call_next):
        response = await call_next(request)
        request_id = getattr(request.state, "request_id", "")
        logger.info(
            "api.request",
            method=request.method,
            path=str(request.url.path),
            status=response.status_code,
            request_id=request_id,
        )
        return response

    # ------------------------------------------------------------------
    # Exception handlers
    # ------------------------------------------------------------------
    app.add_exception_handler(AppError, app_error_handler)  # type: ignore[arg-type]
    app.add_exception_handler(Exception, generic_exception_handler)  # type: ignore[arg-type]

    # ------------------------------------------------------------------
    # Routes
    # ------------------------------------------------------------------
    from src.api.routes.auth import router as auth_router
    from src.api.routes.campaigns import router as campaigns_router
    from src.api.routes.assets import router as assets_router
    from src.api.routes.brands import router as brands_router
    from src.api.routes.compliance import router as compliance_router
    from src.api.routes.jobs import router as jobs_router
    from src.api.routes.metrics import router as metrics_router
    from src.api.routes.settings import router as settings_router
    from src.api.routes.ws import router as ws_router

    app.include_router(auth_router, prefix="/api/v1")
    app.include_router(campaigns_router, prefix="/api/v1")
    app.include_router(assets_router, prefix="/api/v1")
    app.include_router(brands_router, prefix="/api/v1")
    app.include_router(compliance_router, prefix="/api/v1")
    app.include_router(jobs_router, prefix="/api/v1")
    app.include_router(metrics_router, prefix="/api/v1")
    app.include_router(settings_router, prefix="/api/v1")
    app.include_router(ws_router)

    # ------------------------------------------------------------------
    # Health check  (outside /api/v1 prefix)
    # ------------------------------------------------------------------
    @app.get("/health", tags=["health"])
    async def health_check():
        return JSONResponse(
            content={
                "status": "healthy",
                "version": "2.0.0",
            }
        )

    return app


# Module-level instance used by ``uvicorn src.api.main:app``
app = create_app()
