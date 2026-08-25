"""Authorization policy for tool invocation.

Separates two questions the harness must answer before a tool runs:

1. Does the caller hold the permissions the contract requires?
   (coarse-grained, carried in :class:`AuthorizationContext`)
2. Does the caller actually have access to the target video? (ownership,
   delegated to a :class:`VideoAccessChecker` port backed by application
   state, e.g. the ``via-db`` video repository)

A denial always aborts the agent run with ``AUTHORIZATION_ERROR`` - the
model is never shown authorization feedback it could reason around.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from via_harness.context import AuthorizationContext
from via_harness.errors import ErrorCategory, HarnessError
from via_harness.tools.base import ToolContract

__all__ = ["Authorizer", "Decision", "DefaultAuthorizer", "VideoAccessChecker"]


@runtime_checkable
class VideoAccessChecker(Protocol):
    """Port answering "can this user access this video?".

    Implemented by the application (e.g. DynamoDB-backed ownership lookup);
    the harness itself stays storage-agnostic.
    """

    def check(self, *, user_id: str, video_id: str) -> bool:
        """Return whether the user may read/interact with the video.

        Args:
            user_id: Authenticated subject.
            video_id: Video under question.

        Returns:
            True when access is granted.
        """
        ...


@dataclass(frozen=True)
class Decision:
    """Outcome of an authorization evaluation."""

    allowed: bool
    reason: str


class Authorizer(Protocol):
    """Port deciding whether a tool may run in a given context."""

    def authorize(self, contract: ToolContract, authz: AuthorizationContext) -> Decision:
        """Evaluate a tool invocation request.

        Args:
            contract: Contract declaring required permissions.
            authz: Caller's authorization context.

        Returns:
            The authorization decision with a human-readable reason.
        """
        ...


class DefaultAuthorizer:
    """Default policy: permission coverage plus video ownership."""

    def __init__(self, checker: VideoAccessChecker) -> None:
        """Initialize the policy.

        Args:
            checker: Application-provided ownership/access oracle.
        """
        self._checker = checker

    def authorize(self, contract: ToolContract, authz: AuthorizationContext) -> Decision:
        """Enforce permission coverage and video access.

        Args:
            contract: Tool contract under evaluation.
            authz: Caller's authorization context.

        Returns:
            Allowed decision, or denial with the failing criterion.
        """
        if not authz.has_permissions(contract.required_permissions):
            missing = sorted(p.value for p in contract.required_permissions - authz.permissions)
            return Decision(allowed=False, reason=f"missing permissions: {', '.join(missing)}")
        if not self._checker.check(user_id=authz.user_id, video_id=authz.video_id):
            return Decision(allowed=False, reason="user does not have access to this video")
        return Decision(allowed=True, reason="ok")


def authorization_denied(reason: str, *, run_id: str | None = None) -> HarnessError:
    """Build the canonical denial error.

    Args:
        reason: Human-readable denial reason from the decision.
        run_id: Agent run identifier for traceability.

    Returns:
        Harness error with category ``AUTHORIZATION_ERROR``.
    """
    return HarnessError(
        ErrorCategory.AUTHORIZATION_ERROR, f"Tool invocation denied: {reason}", run_id=run_id
    )
