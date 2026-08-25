"""Model failure and tool failure propagation tests (required area 8)."""

from __future__ import annotations

import json

import pytest
from pydantic import BaseModel, Field
from via_harness import (
    AgentRequest,
    AgentRunner,
    AuthorizationContext,
    Decision,
    DefaultAuthorizer,
    ErrorCategory,
    HarnessError,
    InProcessToolRegistry,
    LocalPromptResolver,
    LocalTracer,
    Permission,
    ToolContract,
    ToolResult,
)
from via_harness.model.types import ModelRequest, ModelResponse, StopReason


class _EchoIn(BaseModel):
    """Input schema for the loop-test echo tool."""

    text: str = Field(min_length=1)


class _EchoOut(BaseModel):
    """Output schema for the loop-test echo tool."""

    echoed: str


class _Echo:
    """Echo tool used by failure-path tests."""

    contract = ToolContract(
        name="echo",
        description="Echoes text.",
        input_model=_EchoIn,
        output_model=_EchoOut,
    )

    def execute(self, *, video_id: str, authz: AuthorizationContext, arguments: dict) -> ToolResult:
        """Return an ok echo result.

        Args:
            video_id: Target video id.
            authz: Caller context.
            arguments: Validated args.

        Returns:
            Ok ToolResult echoing ``text``.
        """
        from via_harness import ToolStatus

        _ = video_id, authz
        return ToolResult(status=ToolStatus.OK, payload={"echoed": arguments.get("text", "")})


def _prompt() -> object:
    """Build the standard test prompt.

    Returns:
        Prompt named ``video_assistant`` v1.
    """
    from via_harness import Prompt, PromptEnvironment

    return Prompt(
        name="video_assistant",
        version=1,
        environment=PromptEnvironment.LOCAL,
        template="You assist with video {{video_id}}.",
        variables=("video_id",),
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


def _registry_with_echo() -> InProcessToolRegistry:
    """Registry containing the echo tool.

    Returns:
        Registry with one echo tool registered.
    """
    registry = InProcessToolRegistry()
    registry.register(_Echo())
    return registry


def _runner(model: object, authorizer: object = None) -> AgentRunner:
    """Assemble a runner with local fakes.

    Args:
        model: Model client under test.
        authorizer: Optional authorizer override.

    Returns:
        Wired :class:`AgentRunner`.
    """
    return AgentRunner(
        model=model,  # type: ignore[arg-type]
        prompts=LocalPromptResolver([_prompt()]),  # type: ignore[list-item]
        tools=_registry_with_echo(),
        authorizer=authorizer or DefaultAuthorizer(_AllowAll()),  # type: ignore[arg-type]
        tracer=LocalTracer(),
    )


def _authz() -> AuthorizationContext:
    """Build a fully-permitted context.

    Returns:
        Context for user-1/video-1.
    """
    return AuthorizationContext(
        user_id="user-1",
        video_id="video-1",
        permissions=frozenset(
            {Permission.VIDEO_READ, Permission.TRANSCRIPT_READ, Permission.VIDEO_ANALYZE}
        ),
    )


class ExplodingModel:
    """Model client that always raises a retryable provider error."""

    def invoke(
        self, request: ModelRequest, *, timeout_seconds: float | None = None
    ) -> ModelResponse:
        """Raise a MODEL_ERROR every time.

        Args:
            request: Ignored request.
            timeout_seconds: Ignored budget.

        Raises:
            HarnessError: Retryable model error.
        """
        _ = request, timeout_seconds
        raise HarnessError(ErrorCategory.MODEL_ERROR, "throttled", retryable=True)


class ToolLoopModel:
    """Model client that never finalizes - always requests tools."""

    def invoke(
        self, request: ModelRequest, *, timeout_seconds: float | None = None
    ) -> ModelResponse:
        """Always emit a tool_request payload.

        Args:
            request: Conversation state.
            timeout_seconds: Ignored.

        Returns:
            Response whose text is a tool_request JSON body.
        """
        _ = request, timeout_seconds
        return ModelResponse(
            text=json.dumps({"type": "tool_request", "tool": "echo", "arguments": {"text": "x"}}),
            stop_reason=StopReason.END_TURN,
            model_id="loop",
        )


class TestFailurePropagation:
    """Failures surface as failed runs; nothing is swallowed."""

    def test_model_error_returns_failed_result(self) -> None:
        """MODEL_ERROR produces a failed result carrying run identity."""
        runner = _runner(ExplodingModel())
        result = runner.execute(AgentRequest(message="hi", video_id="video-1"), _authz())
        assert result.completed is False
        assert result.failure is not None
        assert result.failure.category is ErrorCategory.MODEL_ERROR
        assert result.run_id.startswith("run_")

    def test_unexpected_internal_error_reraises_wrapped(self) -> None:
        """Non-harness exceptions are recorded then re-raised as INTERNAL_ERROR."""

        class BadResolver:
            """Resolver that explodes unexpectedly."""

            def get_prompt(
                self, name: str, *, version: int | None = None, environment: object = None
            ) -> object:
                """Raise a plain RuntimeError.

                Args:
                    name: Prompt name.
                    version: Unused pin.
                    environment: Unused scope.

                Raises:
                    RuntimeError: Always.
                """
                _ = name, version, environment
                raise RuntimeError("wiring bug")

        runner = AgentRunner(
            model=LocalModelClientShim(),
            prompts=BadResolver(),  # type: ignore[arg-type]
            tools=InProcessToolRegistry(),
            authorizer=DefaultAuthorizer(_AllowAll()),
            tracer=LocalTracer(),
        )
        with pytest.raises(HarnessError) as err:
            runner.execute(AgentRequest(message="hi", video_id="v"), _authz())
        assert err.value.category is ErrorCategory.INTERNAL_ERROR
        assert isinstance(err.value.__cause__, RuntimeError)

    def test_authorization_denial_aborts_run(self) -> None:
        """A denied tool aborts the whole run with AUTHORIZATION_ERROR."""

        class DenyAll:
            """Authorizer denying everything."""

            def authorize(self, contract: object, authz: AuthorizationContext) -> Decision:
                """Deny all invocations.

                Args:
                    contract: Tool contract.
                    authz: Caller context.

                Returns:
                    Denial decision.
                """
                _ = contract, authz
                return Decision(allowed=False, reason="policy says no")

        runner = _runner(ToolLoopModel(), authorizer=DenyAll())
        result = runner.execute(AgentRequest(message="hi", video_id="v", max_steps=2), _authz())
        assert result.failure is not None
        assert result.failure.category is ErrorCategory.AUTHORIZATION_ERROR

    def test_max_steps_exhaustion_is_invalid_model_response(self) -> None:
        """A model that only ever requests tools exhausts the step budget."""
        runner = _runner(ToolLoopModel())
        result = runner.execute(AgentRequest(message="hi", video_id="v", max_steps=2), _authz())
        assert result.failure is not None
        assert result.failure.category is ErrorCategory.INVALID_MODEL_RESPONSE


class LocalModelClientShim:
    """End-turn stub used where model output is irrelevant."""

    def invoke(
        self, request: ModelRequest, *, timeout_seconds: float | None = None
    ) -> ModelResponse:
        """Return an immediately-finalizing response.

        Args:
            request: Ignored.
            timeout_seconds: Ignored.

        Returns:
            Final-answer response with valid JSON body.
        """
        _ = request, timeout_seconds
        return ModelResponse(
            text=json.dumps({"type": "final", "answer": "ok", "citations": []}),
            stop_reason=StopReason.END_TURN,
            model_id="shim",
        )
