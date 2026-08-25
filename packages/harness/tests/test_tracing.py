"""Trace creation tests (required area 9)."""

from __future__ import annotations

import json
import re

from pydantic import BaseModel, Field
from via_harness import (
    AgentRequest,
    AgentRunner,
    AuthorizationContext,
    DefaultAuthorizer,
    ErrorCategory,
    HarnessError,
    InProcessToolRegistry,
    LocalPromptResolver,
    LocalTracer,
    Permission,
    Prompt,
    PromptEnvironment,
    ToolContract,
)

_HEX16 = re.compile(r"^[0-9a-f]{16}$")
_HEX32 = re.compile(r"^[0-9a-f]{32}$")


class _EchoIn(BaseModel):
    """Input schema for the tracing echo tool."""

    text: str = Field(min_length=1)


class _EchoOut(BaseModel):
    """Output schema for the tracing echo tool."""

    echoed: str


class _Echo:
    """Echo tool used by tracing tests."""

    contract = None  # assigned after class definition

    def execute(self, *, video_id: str, authz: AuthorizationContext, arguments: dict) -> object:
        """Return an ok echo result.

        Args:
            video_id: Target video id.
            authz: Caller context.
            arguments: Validated args.

        Returns:
            Ok ToolResult echoing ``text``.
        """
        from via_harness import ToolResult, ToolStatus

        _ = video_id, authz
        return ToolResult(status=ToolStatus.OK, payload={"echoed": arguments.get("text", "")})


def _prompt() -> Prompt:
    """Build the standard test prompt.

    Returns:
        Prompt named ``video_assistant`` v1.
    """
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


class _FinalModel:
    """Model returning an immediate valid final answer."""

    def invoke(self, request: object, *, timeout_seconds: float | None = None) -> object:
        """Produce a final JSON answer.

        Args:
            request: Ignored conversation.
            timeout_seconds: Ignored budget.

        Returns:
            Response containing a final payload with token usage.
        """
        from via_harness.model.types import ModelResponse, StopReason, TokenUsage

        _ = request, timeout_seconds
        return ModelResponse(
            text=json.dumps({"type": "final", "answer": "done", "citations": []}),
            stop_reason=StopReason.END_TURN,
            model_id="trace-test",
            usage=TokenUsage(input_tokens=3, output_tokens=4),
        )


class _ExplodingModel:
    """Model that always raises a retryable provider error."""

    def invoke(self, request: object, *, timeout_seconds: float | None = None) -> object:
        """Raise MODEL_ERROR unconditionally.

        Args:
            request: Ignored.
            timeout_seconds: Ignored.

        Raises:
            HarnessError: Retryable model error.
        """
        _ = request, timeout_seconds
        raise HarnessError(ErrorCategory.MODEL_ERROR, "throttled", retryable=True)


def _authz() -> AuthorizationContext:
    """Fully-permitted authorization context.

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


def _runner(model: object, tracer: LocalTracer) -> AgentRunner:
    """Assemble a runner with local fakes.

    Args:
        model: Model client under test.
        tracer: Tracer capturing spans.

    Returns:
        Wired :class:`AgentRunner`.
    """
    registry = InProcessToolRegistry()
    registry.register(_Echo())
    return AgentRunner(
        model=model,  # type: ignore[arg-type]
        prompts=LocalPromptResolver([_prompt()]),
        tools=registry,
        authorizer=DefaultAuthorizer(_AllowAll()),
        tracer=tracer,
        agent_version="9.9.9",
    )


_Echo.contract = ToolContract(
    name="echo",
    description="Echoes text for trace assertions.",
    input_model=_EchoIn,
    output_model=_EchoOut,
)


class TestTracing:
    """Every run leaves a complete OTel-compatible span tree."""

    def test_completed_run_produces_root_and_child_spans(self) -> None:
        """Root span plus prompt/model/response spans share one trace id."""
        tracer = LocalTracer()
        runner = _runner(_FinalModel(), tracer)
        result = runner.execute(AgentRequest(message="hi", video_id="v-1"), _authz())
        assert result.completed, result.failure

        spans = tracer.query(result.run_id)
        names = [s.name for s in spans]
        assert names[0] == "agent.run"
        assert {"prompt.resolve", "model.invoke", "response.validate"}.issubset(set(names))

        root = spans[0]
        assert _HEX32.match(root.trace_id)
        for span in spans:
            if span.parent_span_id is not None:
                assert _HEX16.match(span.parent_span_id)
        assert root.attributes["video_id"] == "v-1"
        assert root.attributes["agent_version"] == "9.9.9"
        assert root.duration_ms is not None

    def test_failed_run_marks_root_span_error(self) -> None:
        """Failures stamp category/message onto the root span."""
        tracer = LocalTracer()
        runner = _runner(_ExplodingModel(), tracer)
        result = runner.execute(AgentRequest(message="hi", video_id="v"), _authz())
        spans = tracer.query(result.run_id)
        root = next(s for s in spans if s.name == "agent.run")
        assert root.status == "error"
        assert root.error_category == ErrorCategory.MODEL_ERROR.value
