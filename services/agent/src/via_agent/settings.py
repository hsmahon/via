"""Typed settings for the agent service."""

from __future__ import annotations

from typing import Literal

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

__all__ = ["Settings"]


class Settings(BaseSettings):
    """Environment-driven configuration (``VIA_`` prefix)."""

    model_config = SettingsConfigDict(env_prefix="VIA_", env_file=".env", extra="ignore")

    service_name: str = "via-agent"
    env: str = "local"
    log_level: str = "INFO"
    aws_region: str = "us-east-1"

    table_name: str = "via"
    dynamodb_endpoint_url: str | None = None

    #: Which ModelClient implementation to bind (local for dev, Bedrock in prod).
    model_backend: Literal["local", "bedrock"] = "local"
    #: TwelveLabs Pegasus inference-profile id on Bedrock.
    pegasus_model_id: str | None = None

    agent_version: str = "0.1.0"
    default_user_id: str = "dev-user"

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
