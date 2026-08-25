"""Tool invocation tests (required areas 4, 6 and 7)."""

from __future__ import annotations

from time import sleep

import pytest
from pydantic import BaseModel, Field
from via_harness import (
    AuthorizationContext,
    ErrorCategory,
    HarnessError,
    ToolContract,
    ToolExecutor,
    ToolResult,
    ToolStatus,
)


class _EchoIn(BaseModel):
    """Input schema for the local echo tool."""

    text: str = Field(min_length=1)


class _EchoOut(BaseModel):
    """Output schema for the local echo tool."""

    echoed: str


class _Echo:
    """Minimal echo tool used by executor tests."""

    contract = ToolContract(
        name="echo",
        description="Echoes text.",
        input_model=_EchoIn,
        output_model=_EchoOut,
    )

    def __init__(self, *, fail: bool = False) -> None:
        """Initialize the tool.

        Args:
            fail: When True, execute raises.
        """
        self._fail = fail

    def execute(self, *, video_id: str, authz: AuthorizationContext, arguments: dict) -> ToolResult:
        """Echo arguments or raise.

        Args:
            video_id: Target video id.
            authz: Caller context.
            arguments: Validated args.

        Returns:
            Ok ToolResult echoing ``text``.

        Raises:
            RuntimeError: When built with fail=True.
        """
        _ = video_id, authz
        if self._fail:
            raise RuntimeError("boom")
        return ToolResult(status=ToolStatus.OK, payload={"echoed": arguments.get("text", "")})


class SlowTool(_Echo):
    """Echo tool that sleeps past its contract deadline."""

    contract = ToolContract(
        name="slow",
        description="Deliberately exceeds its timeout budget.",
        input_model=_EchoIn,
        output_model=_EchoOut,
        timeout_seconds=0.05,
        owner="test",
    )

    def execute(self, *, video_id: str, authz: AuthorizationContext, arguments: dict) -> ToolResult:
        """Sleep beyond the deadline.

        Args:
            video_id: Target video id.
            authz: Caller authorization context.
            arguments: Validated tool arguments.

        Returns:
            Never returns normally; abandoned by the executor.
        """
        _ = video_id, authz, arguments
        sleep(0.5)
        raise AssertionError("should have been abandoned")  # pragma: no cover


class TestToolInvocation:
    """Executor mechanics: success paths and error normalization."""

    def test_successful_invocation_returns_payload(
        self,
        executor: ToolExecutor,
        authz: AuthorizationContext,
    ) -> None:
        """Valid arguments flow through to the tool payload."""
        result = executor.execute(
            _Echo(), video_id="video-1", authz=authz, arguments={"text": "hi"}
        )
        assert result.status is ToolStatus.OK
        assert result.payload == {"echoed": "hi"}

    def test_invalid_arguments_raise_invalid_tool_arguments(
        self,
        executor: ToolExecutor,
        authz: AuthorizationContext,
    ) -> None:
        """Schema violations map to INVALID_TOOL_ARGUMENTS with details."""
        with pytest.raises(HarnessError) as err:
            executor.execute(_Echo(), video_id="video-1", authz=authz, arguments={})
        assert err.value.category is ErrorCategory.INVALID_TOOL_ARGUMENTS
        assert err.value.details["tool"] == "echo"

    def test_unexpected_tool_failure_wrapped_as_tool_error(
        self,
        executor: ToolExecutor,
        authz: AuthorizationContext,
    ) -> None:
        """Arbitrary tool exceptions are wrapped with the cause preserved."""
        with pytest.raises(HarnessError) as err:
            executor.execute(_Echo(fail=True), video_id="v", authz=authz, arguments={"text": "x"})
        assert err.value.category is ErrorCategory.TOOL_ERROR
        assert isinstance(err.value.__cause__, RuntimeError)

    def test_timeout_maps_to_timeout_category(self, authz: AuthorizationContext) -> None:
        """A tool exceeding its contract timeout raises TIMEOUT."""
        slow = SlowTool()
        with pytest.raises(HarnessError) as err:
            ToolExecutor().execute(slow, video_id="v", authz=authz, arguments={"text": "x"})
        assert err.value.category is ErrorCategory.TIMEOUT
        assert "slow" in err.value.message
