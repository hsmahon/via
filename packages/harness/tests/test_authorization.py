"""Tool authorization tests (required area 3)."""

from __future__ import annotations

from pydantic import BaseModel
from via_harness import AuthorizationContext, DefaultAuthorizer, Permission, ToolContract


class _In(BaseModel):
    """Empty input schema for contract construction."""


class _Out(BaseModel):
    """Empty output schema for contract construction."""


def _contract(perms: set[Permission]) -> ToolContract:
    """Build a minimal contract requiring the given permissions.

    Args:
        perms: Required permission set.

    Returns:
        Configured contract named "probe".
    """
    return ToolContract(
        name="probe",
        description="Authorization probe.",
        input_model=_In,
        output_model=_Out,
        required_permissions=frozenset(perms),
    )


class _AllowAll:
    """Ownership checker granting every request."""

    def check(self, *, user_id: str, video_id: str) -> bool:
        """Grant access unconditionally.

        Args:
            user_id: Authenticated subject.
            video_id: Video under question.

        Returns:
            Always True.
        """
        _ = user_id, video_id
        return True


class _DenyAll:
    """Ownership checker that always denies."""

    def check(self, *, user_id: str, video_id: str) -> bool:
        """Deny every request.

        Args:
            user_id: Authenticated subject.
            video_id: Video under question.

        Returns:
            Always False.
        """
        _ = user_id, video_id
        return False


class TestDefaultAuthorizer:
    """Permission coverage plus ownership semantics."""

    def test_allows_when_permissions_and_ownership_ok(self) -> None:
        """Granted permissions and owned video produce an allow decision."""
        ctx = AuthorizationContext(
            user_id="u", video_id="v", permissions=frozenset({Permission.VIDEO_READ})
        )
        assert (
            DefaultAuthorizer(_AllowAll())
            .authorize(_contract({Permission.VIDEO_READ}), ctx)
            .allowed
        )

    def test_denies_missing_permissions(self) -> None:
        """Missing contract permissions deny with reason listing them."""
        ctx = AuthorizationContext(
            user_id="u", video_id="v", permissions=frozenset({Permission.VIDEO_READ})
        )
        decision = DefaultAuthorizer(_AllowAll()).authorize(
            _contract({Permission.VIDEO_ANALYZE}), ctx
        )
        assert not decision.allowed
        assert "video:analyze" in decision.reason

    def test_denies_non_owner(self) -> None:
        """A non-owner with correct permissions is still denied."""
        ctx = AuthorizationContext(
            user_id="attacker", video_id="victim", permissions=frozenset({Permission.VIDEO_READ})
        )
        decision = DefaultAuthorizer(_DenyAll()).authorize(_contract(set()), ctx)
        assert not decision.allowed
        assert "access" in decision.reason
