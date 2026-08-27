"""Typed settings for the video-processing worker.

Provides :class:`WorkerSettings` with ``VIA_``-prefixed environment bindings
for table name, DynamoDB endpoint, and processing mode flags. Validates
empty-string endpoints to ``None`` and coerces ``processing_hooks_enabled`` /
``processing_mode`` for deterministic local runs.
"""

from __future__ import annotations

from typing import Literal

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

__all__ = ["WorkerSettings"]


class WorkerSettings(BaseSettings):
    """Environment-driven configuration (``VIA_`` prefix)."""

    model_config = SettingsConfigDict(env_prefix="VIA_", env_file=".env", extra="ignore")

    service_name: str = "via-video-processing-worker"
    log_level: str = "INFO"
    table_name: str = "via"
    dynamodb_endpoint_url: str | None = None
    processing_hooks_enabled: bool = False
    """When true, invoke Transcribe/Pegasus hooks. ``VIA_PROCESSING_MODE`` selects the implementation (``mock`` vs ``aws``). Keeping this flag allows ``VIA_PROCESSING_HOOKS_ENABLED=true`` to keep working as ``mode=mock``."""

    processing_mode: Literal["off", "mock", "aws"] = "off"
    """Processing implementation selector. ``off`` means no hooks, ``mock`` uses deterministic in-memory adapters, ``aws`` uses the real Transcribe/Bedrock stubs (raise NotImplementedError until v0.2)."""

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

    @model_validator(mode="after")
    def _coerce_processing_mode(self) -> WorkerSettings:
        """Align ``processing_hooks_enabled`` and ``processing_mode``.

        ``VIA_PROCESSING_HOOKS_ENABLED=true`` without an explicit
        ``VIA_PROCESSING_MODE`` is treated as ``mock`` so local runs
        succeed deterministically instead of forcing ``FAILED``.

        Returns:
            Validated settings with coherent mode.
        """
        if self.processing_hooks_enabled and self.processing_mode == "off":
            self.processing_mode = "mock"
        if self.processing_mode != "off":
            self.processing_hooks_enabled = True
        return self
