"""Platform settings endpoints: get, update, list backends."""

from __future__ import annotations

import os

from fastapi import APIRouter, Depends
import structlog

from src.api.dependencies import check_rate_limit, get_db, require_role
from src.api.schemas import (
    BackendInfo,
    Envelope,
    Meta,
    SettingsResponse,
    SettingsUpdateRequest,
)
from src.config import get_config

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/settings", tags=["settings"])


# ---------------------------------------------------------------------------
# In-memory settings store (persisted across requests in a single process).
# In production these would live in the database.
# ---------------------------------------------------------------------------

_platform_settings: dict = {
    "default_backend": os.getenv("DEFAULT_IMAGE_BACKEND", "firefly"),
    "max_concurrent_requests": int(os.getenv("MAX_CONCURRENT_REQUESTS", "5")),
    "rate_limit_auth": int(os.getenv("RATE_LIMIT_AUTH", "100")),
    "rate_limit_unauth": int(os.getenv("RATE_LIMIT_UNAUTH", "20")),
    "enable_localization": os.getenv("ENABLE_LOCALIZATION", "true").lower() == "true",
    "enable_compliance_check": True,
    "supported_locales": ["en-US", "es-MX", "fr-CA", "pt-BR", "de-DE", "ja-JP", "ko-KR"],
}


def _build_backend_list() -> list[BackendInfo]:
    """Build the list of image-generation backends and their availability."""
    cfg = get_config()
    available = cfg.get_available_backends()

    all_backends = [
        BackendInfo(
            name="firefly",
            available="firefly" in available,
            description="Adobe Firefly image generation",
        ),
        BackendInfo(
            name="openai",
            available="openai" in available,
            description="OpenAI DALL-E image generation",
        ),
        BackendInfo(
            name="gemini",
            available="gemini" in available,
            description="Google Gemini / Imagen image generation",
        ),
        BackendInfo(
            name="claude",
            available=bool(os.getenv("CLAUDE_API_KEY")),
            description="Anthropic Claude (text processing only)",
        ),
    ]
    return all_backends


# ---------------------------------------------------------------------------
# GET /settings
# ---------------------------------------------------------------------------


@router.get(
    "",
    response_model=Envelope[SettingsResponse],
    dependencies=[Depends(check_rate_limit)],
)
async def get_settings(
    user=Depends(require_role(["admin"])),
):
    """Return current platform settings (Admin only)."""
    backends = _build_backend_list()

    resp = SettingsResponse(
        default_backend=_platform_settings["default_backend"],
        available_backends=backends,
        max_concurrent_requests=_platform_settings["max_concurrent_requests"],
        rate_limit_auth=_platform_settings["rate_limit_auth"],
        rate_limit_unauth=_platform_settings["rate_limit_unauth"],
        enable_localization=_platform_settings["enable_localization"],
        enable_compliance_check=_platform_settings["enable_compliance_check"],
        supported_locales=_platform_settings["supported_locales"],
    )

    return Envelope[SettingsResponse](data=resp, meta=Meta())


# ---------------------------------------------------------------------------
# PATCH /settings
# ---------------------------------------------------------------------------


@router.patch(
    "",
    response_model=Envelope[SettingsResponse],
    dependencies=[Depends(check_rate_limit)],
)
async def update_settings(
    body: SettingsUpdateRequest,
    user=Depends(require_role(["admin"])),
):
    """Update platform settings (Admin only)."""
    updates = body.model_dump(exclude_unset=True)

    for key, value in updates.items():
        if key in _platform_settings:
            _platform_settings[key] = value

    logger.info("settings.updated", fields=list(updates.keys()), user_id=str(user.id))

    backends = _build_backend_list()

    resp = SettingsResponse(
        default_backend=_platform_settings["default_backend"],
        available_backends=backends,
        max_concurrent_requests=_platform_settings["max_concurrent_requests"],
        rate_limit_auth=_platform_settings["rate_limit_auth"],
        rate_limit_unauth=_platform_settings["rate_limit_unauth"],
        enable_localization=_platform_settings["enable_localization"],
        enable_compliance_check=_platform_settings["enable_compliance_check"],
        supported_locales=_platform_settings["supported_locales"],
    )

    return Envelope[SettingsResponse](data=resp, meta=Meta())


# ---------------------------------------------------------------------------
# GET /settings/backends
# ---------------------------------------------------------------------------


@router.get(
    "/backends",
    response_model=Envelope[list[BackendInfo]],
    dependencies=[Depends(check_rate_limit)],
)
async def list_backends(
    user=Depends(require_role(["admin"])),
):
    """Return available image-generation backends and their status."""
    backends = _build_backend_list()
    return Envelope[list[BackendInfo]](data=backends, meta=Meta())
