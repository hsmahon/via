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
    """Optional S3 endpoint override for testing (LocalStack); None uses real S3."""

    s3_public_endpoint_url: str | None = None
    """Optional public endpoint embedded in presigned URLs (LocalStack); must be reachable by the client; None uses real S3 / reuses primary client."""

    presign_expiry_seconds: int = 900
    default_user_id: str = "dev-user"
    max_videos_per_user: int = 20
    """Maximum videos a single user may create (quota). Evaluated at write time."""

    allowed_video_content_types: str = "video/mp4,video/quicktime,video/mpeg"
    """Comma-separated allow-list for ``content_type``; empty allows any type."""

    @property
    def allowed_content_type_set(self) -> set[str]:
        """Parsed allow-list for video MIME types.

        Returns:
            Lower-cased set of permitted content types.
        """
        raw = self.allowed_video_content_types.strip()
        if not raw:
            return set()
        return {item.strip().lower() for item in raw.split(",") if item.strip()}

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
