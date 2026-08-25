"""Health route."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from via_harness import __version__ as harness_version  # noqa: F401 - surfaced in docs

from via_api.deps import get_settings
from via_api.schemas import HealthResponse
from via_api.settings import Settings

router = APIRouter(tags=["system"])


@router.get("/health", response_model=HealthResponse, summary="Liveness probe")
def health(settings: Annotated[Settings, Depends(get_settings)]) -> HealthResponse:
    """Report service liveness and version.

    Args:
        settings: Application settings.

    Returns:
        Static healthy payload.
    """
    return HealthResponse(service=settings.service_name, status="ok", version="0.1.0")
