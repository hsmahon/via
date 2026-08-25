"""Tool registration and discovery tests (required area 2)."""

from __future__ import annotations

import pytest
from pydantic import BaseModel
from via_harness import (
    AuthorizationContext,
    ErrorCategory,
    HarnessError,
    InProcessToolRegistry,
    Permission,
    ToolContract,
)


class _EmptyIn(BaseModel):
    """Input schema requiring no arguments."""


class _EmptyOut(BaseModel):
    """Output schema carrying nothing."""


class _Gated:
    """Tool gated behind the analyze permission."""

    contract = ToolContract(
        name="gated",
        description="Requires video:analyze.",
        input_model=_EmptyIn,
        output_model=_EmptyOut,
        required_permissions=frozenset({Permission.VIDEO_ANALYZE}),
    )

    def execute(self, *, video_id: str, authz: AuthorizationContext, arguments: dict) -> object:
        """Return an empty ok result.

        Args:
            video_id: Target video id.
            authz: Caller context.
            arguments: Validated args.

        Returns:
            Ok ToolResult with empty payload.
        """
        from via_harness import ToolResult, ToolStatus

        _ = video_id, authz, arguments
        return ToolResult(status=ToolStatus.OK, payload={})


class TestInProcessRegistry:
    """Registration and permission-filtered discovery."""

    def test_register_and_discover(
        self, registry: InProcessToolRegistry, authz: AuthorizationContext
    ) -> None:
        """Registered tools are discoverable."""
        registry.register(_Gated())
        assert [t.contract.name for t in registry.get_tools(authz)] == ["gated"]

    def test_duplicate_registration_is_internal_error(
        self, registry: InProcessToolRegistry
    ) -> None:
        """Re-registering a name indicates a wiring bug (INTERNAL_ERROR)."""
        registry.register(_Gated())
        with pytest.raises(HarnessError) as err:
            registry.register(_Gated())
        assert err.value.category is ErrorCategory.INTERNAL_ERROR

    def test_discovery_filters_by_permissions(
        self, registry: InProcessToolRegistry, authz: AuthorizationContext
    ) -> None:
        """Tools whose required permissions are not granted stay hidden."""
        registry.register(_Gated())
        limited = AuthorizationContext(
            user_id=authz.user_id,
            video_id=authz.video_id,
            permissions=frozenset({Permission.VIDEO_READ}),
        )
        assert registry.get_tools(limited) == []
        assert len(registry.get_tools(authz)) == 1

    def test_get_tool_unknown_returns_none(self, registry: InProcessToolRegistry) -> None:
        """Unknown lookups return None instead of raising."""
        assert registry.get_tool("missing") is None
