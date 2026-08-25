"""FastAPI dependency providers wiring repositories and settings."""

from __future__ import annotations

from functools import lru_cache
from typing import Annotated

from fastapi import Depends, Header
from via_db import VideoRepository

from via_api.settings import Settings
from via_api.storage import Presigner

__all__ = [
    "get_presigner",
    "get_settings",
    "get_video_repository",
    "require_user_id",
    "user_id_header",
]


@lru_cache(maxsize=1)
def _cached_settings() -> Settings:
    """Build the process-wide settings instance.

    Returns:
        Parsed :class:`Settings`.
    """
    return Settings()


def get_settings() -> Settings:
    """FastAPI dependency returning application settings.

    Returns:
        The cached :class:`Settings`.
    """
    return _cached_settings()


@lru_cache(maxsize=1)
def _cached_repository(table_name: str, endpoint_url: str | None) -> VideoRepository:
    """Build the process-wide video repository.

    Args:
        table_name: DynamoDB table name.
        endpoint_url: Optional DynamoDB Local endpoint.

    Returns:
        Configured :class:`VideoRepository`.
    """
    from via_db import get_table

    return VideoRepository(get_table(table_name, endpoint_url=endpoint_url))


def get_video_repository(settings: Annotated[Settings, Depends(get_settings)]) -> VideoRepository:
    """FastAPI dependency returning the video repository.

    Args:
        settings: Application settings.

    Returns:
        Configured :class:`VideoRepository`.
    """
    return _cached_repository(settings.table_name, settings.dynamodb_endpoint_url)


def get_presigner(settings: Annotated[Settings, Depends(get_settings)]) -> Presigner:
    """FastAPI dependency returning the upload presigner.

    Args:
        settings: Application settings.

    Returns:
        Configured :class:`Presigner`.
    """
    return Presigner(
        bucket=settings.bucket,
        region=settings.aws_region,
        endpoint_url=settings.s3_endpoint_url,
        public_endpoint_url=settings.s3_public_endpoint_url,
        expiry_seconds=settings.presign_expiry_seconds,
    )


def user_id_header(
    settings: Annotated[Settings, Depends(get_settings)],
    x_user_id: Annotated[str | None, Header()] = None,
) -> str:
    """Resolve the acting user until the real identity layer lands.

    v0.1 authentication: clients assert identity through ``X-User-Id``;
    production replaces this dependency with the application auth layer
    without touching route bodies.

    When no identity can be resolved (empty ``X-User-Id`` and no
    ``VIA_DEFAULT_USER_ID``), a 401 is raised so tests and future auth
    modes can assert unauthenticated behaviour without inventing a new
    system.

    Args:
        settings: Application settings (default user fallback).
        x_user_id: Optional asserted identity header.

    Returns:
        The resolved user id.

    Raises:
        HTTPException: 401 when no identity is available.
    """
    from fastapi import HTTPException

    resolved = (x_user_id or settings.default_user_id or "").strip()
    if not resolved:
        raise HTTPException(status_code=401, detail="not authenticated")
    return resolved


def require_user_id(user_id: Annotated[str, Depends(user_id_header)]) -> str:
    """Alias enforcing authentication for routes requiring identity.

    Args:
        user_id: Resolved user from :func:`user_id_header`.

    Returns:
        The authenticated user id.
    """
    return user_id
