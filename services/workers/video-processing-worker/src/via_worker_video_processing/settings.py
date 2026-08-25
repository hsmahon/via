"""Typed settings for the video-processing worker."""

from __future__ import annotations

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

__all__ = ["WorkerSettings"]


class WorkerSettings(BaseSettings):
    """Environment-driven configuration (``VIA_`` prefix)."""

    model_config = SettingsConfigDict(env_prefix="VIA_", env_file=".env", extra="ignore")

    service_name: str = "via-video-processing-worker"
    log_level: str = "INFO"
    table_name: str = "via"
    dynamodb_endpoint_url: str | None = None
    #: When true, invoke the pending Transcribe/Pegasus interfaces (they raise
    #: NotImplementedError, which marks videos FAILED).
    processing_hooks_enabled: bool = False

    @field_validator("dynamodb_endpoint_url", mode="before")
    @classmethod
    def _empty_endpoint_becomes_none(cls, value: str | None) -> str | None:
        """Treat empty-string endpoints as unset (Docker Compose quirk).

        Args:
            value: Raw endpoint value from environment or dotenv.

        Returns:
            None when empty, otherwise the value unchanged.
        """
        return value or None
