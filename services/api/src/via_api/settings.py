"""Typed settings for the API service."""

from __future__ import annotations

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

__all__ = ["Settings"]


class Settings(BaseSettings):
    """Environment-driven configuration (``VIA_`` prefix)."""

    model_config = SettingsConfigDict(env_prefix="VIA_", env_file=".env", extra="ignore")

    service_name: str = "via-api"
    env: str = "local"
    log_level: str = "INFO"
    aws_region: str = "us-east-1"

    table_name: str = "via"
    bucket: str = "via-videos"
    dynamodb_endpoint_url: str | None = None
    s3_endpoint_url: str | None = None
    #: Endpoint embedded in presigned URLs; must be reachable by the CLIENT.
    s3_public_endpoint_url: str | None = None
    presign_expiry_seconds: int = 900
    default_user_id: str = "dev-user"

    @field_validator(
        "dynamodb_endpoint_url", "s3_endpoint_url", "s3_public_endpoint_url", mode="before"
    )
    @classmethod
    def _empty_endpoint_becomes_none(cls, value: str | None) -> str | None:
        """Treat empty-string endpoints as unset (Docker Compose quirk).

        Args:
            value: Raw endpoint value from environment or dotenv.

        Returns:
            None when empty, otherwise the value unchanged.
        """
        return value or None
