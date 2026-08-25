"""Identity, authorization and run context objects for the agent harness.

The harness draws a hard line between:

* **Authentication** ("who is this user?") - resolved by the application's
  identity layer *before* the harness is invoked and represented here as
  :class:`SessionContext`.
* **Authorization** ("can this user invoke this tool against this video?")
  - expressed as an :class:`AuthorizationContext` carrying the permissions
  granted to the user for a specific video, evaluated by the policy layer.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

__all__ = [
    "AuthorizationContext",
    "Permission",
    "RunContext",
    "SessionContext",
    "new_id",
]


def new_id(prefix: str) -> str:
    """Generate a new opaque identifier with the given prefix.

    Args:
        prefix: Short prefix such as ``"run"`` or ``"sess"``.

    Returns:
        Identifier in the form ``<prefix>_<32-hex uuid4 slice>``.
    """
    return f"{prefix}_{uuid.uuid4().hex}"


class Permission(StrEnum):
    """Permissions that guard tool invocation.

    Permissions are coarse-grained and video-scoped: holding a permission
    means "may perform this class of action on this specific video".
    """

    VIDEO_READ = "video:read"
    TRANSCRIPT_READ = "transcript:read"
    VIDEO_ANALYZE = "video:analyze"


class SessionContext(BaseModel):
    """Authentication result handed to the harness by the application."""

    model_config = ConfigDict(frozen=True)

    session_id: str = Field(min_length=1)
    user_id: str = Field(min_length=1)


class AuthorizationContext(BaseModel):
    """Authorization inputs for one tool-capable agent interaction.

    Attributes:
        user_id: Authenticated subject.
        video_id: Video the interaction is scoped to.
        permissions: Permissions granted to ``user_id`` on ``video_id``.
            Tool contracts declare required permissions; the policy layer
            verifies coverage before any tool runs.
    """

    model_config = ConfigDict(frozen=True)

    user_id: str = Field(min_length=1)
    video_id: str = Field(min_length=1)
    permissions: frozenset[Permission] = Field(default=frozenset())

    def has_permissions(self, required: frozenset[Permission]) -> bool:
        """Check whether all required permissions are granted.

        Args:
            required: Permission set declared by a tool contract.

        Returns:
            True iff ``required`` is a subset of the granted permissions.
        """
        return required.issubset(self.permissions)


class RunContext(BaseModel):
    """Identity and correlation identifiers for a single agent run.

    Every span, tool call and model call produced during the run references
    these fields so that a complete execution is reconstructible from the
    trace alone.
    """

    run_id: str = Field(min_length=1)
    trace_id: str = Field(
        min_length=32,
        max_length=32,
        description="OpenTelemetry-compatible 32-hex trace id shared by all spans of the run.",
    )
    request_id: str | None = Field(
        default=None, description="Inbound HTTP request id, when available."
    )
    session_id: str = Field(min_length=1)
    user_id: str = Field(min_length=1)
    video_id: str = Field(min_length=1)
    agent_version: str = Field(min_length=1)
    started_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
