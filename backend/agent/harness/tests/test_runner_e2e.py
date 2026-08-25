"""End-to-end local execution of the harness (local-implementations proof)."""

from __future__ import annotations

import json

from pydantic import BaseModel
from via_harness import (
    AgentRequest,
    AgentRunner,
    AuthorizationContext,
    DefaultAuthorizer,
    InProcessToolRegistry,
    LocalMetrics,
    LocalPromptResolver,
    LocalTracer,
    Permission,
    ToolContract,
)


class _MetadataInput(BaseModel):
    """Input schema: metadata tool needs no arguments."""


class _MetadataOutput(BaseModel):
    """Output schema mirroring the video snapshot."""

    found: bool
    filename: str | None = None


class MetadataTool:
    """Fake stand-in for the real get_video_metadata implementation."""

    contract = ToolContract(
        name="get_video_metadata",
        description="Returns stored video metadata.",
        input_model=_MetadataInput,
        output_model=_MetadataOutput,
        required_permissions=frozenset({Permission.VIDEO_READ}),
    )

    def execute(self, *, video_id: str, authz: AuthorizationContext, arguments: dict) -> object:
        """Return a metadata payload for the authorized video.

        Args:
            video_id: Target video id.
            authz: Caller context.
            arguments: Ignored (schema is empty).

        Returns:
            Ok result describing the video.
        """
        from via_harness import ToolResult, ToolStatus

        return ToolResult(
            status=ToolStatus.OK,
            payload={
                "found": True,
                "video": {"video_id": video_id, "filename": "clip.mp4", "duration": 15.0},
            },
        )


class TestLocalEndToEnd:
    """The full loop runs locally with zero AWS dependencies."""

    def test_full_loop_completes_with_citation_and_trace(self) -> None:
        """Request → prompt → tool → model → validated answer, all traced."""
        from via_harness.model.local import LocalModelClient

        registry = InProcessToolRegistry()
        registry.register(MetadataTool())
        tracer = LocalTracer()
        metrics = LocalMetrics()

        runner = AgentRunner(
            model=LocalModelClient(),
            prompts=LocalPromptResolver([make_prompt_named()]),
            tools=registry,
            authorizer=DefaultAuthorizer(_AllowAll()),
            tracer=tracer,
            metrics=metrics,
            agent_version="0.1.0",
        )
        authz = AuthorizationContext(
            user_id="u1", video_id="v1", permissions=frozenset({Permission.VIDEO_READ})
        )
        result = runner.execute(AgentRequest(message="What is this video?", video_id="v1"), authz)

        assert result.completed, result.failure
        assert result.response is not None
        assert result.response.answer
        assert result.usage.input_tokens  # usage telemetry captured
        citation = result.response.citations[0]
        assert citation.video_id == "v1"
        assert citation.timestamp_end == 15.0

        names = {s.name for s in tracer.query(result.run_id)}
        assert "tool.invoke" in names
        snapshot = metrics.snapshot()
        assert snapshot.get("agent.runs.completed", 0) == 1

    def test_tool_result_json_is_wire_shaped(self) -> None:
        """Tool results carry the documented tool_result JSON envelope."""
        registry = InProcessToolRegistry()
        registry.register(MetadataTool())
        model = CapturingModel()
        runner = AgentRunner(
            model=model,
            prompts=LocalPromptResolver([make_prompt_named()]),
            tools=registry,
            authorizer=DefaultAuthorizer(_AllowAll()),
            tracer=LocalTracer(),
        )
        authz = AuthorizationContext(
            user_id="u1", video_id="v1", permissions=frozenset({Permission.VIDEO_READ})
        )
        runner.execute(AgentRequest(message="go", video_id="v1"), authz)

        tool_message = model.requests[-1].messages[-1]
        body = json.loads(tool_message.content)
        assert body["type"] == "tool_result"
        assert body["status"] == "ok"
        assert body["payload"]["video"]["filename"] == "clip.mp4"


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


def make_prompt_named() -> object:
    """Build the standard test prompt.

    Returns:
        Prompt named ``video_assistant`` v1.
    """
    from via_harness import Prompt, PromptEnvironment

    return Prompt(
        name="video_assistant",
        version=1,
        environment=PromptEnvironment.LOCAL,
        template="You assist with video {{video_id}} for user {{user_id}}.",
        variables=("video_id", "user_id"),
    )


class CapturingModel:
    """Model capturing every request and finalizing after tool results."""

    def __init__(self) -> None:
        """Initialize with an empty request log."""
        self.requests: list = []

    def invoke(self, request, *, timeout_seconds=None):  # type: ignore[no-untyped-def]
        """Record the request; request a tool first, finalize afterwards.

        Args:
            request: Conversation to capture.
            timeout_seconds: Ignored.

        Returns:
            Tool-request response on round one, final answer afterwards.
        """
        import json as _json

        from via_harness.model.types import ModelResponse, StopReason

        self.requests.append(request)
        if not any(m.role.value == "tool" for m in request.messages):
            return ModelResponse(
                text=_json.dumps(
                    {"type": "tool_request", "tool": "get_video_metadata", "arguments": {}}
                ),
                stop_reason=StopReason.TOOL_USE,
                model_id="cap",
            )
        return ModelResponse(
            text=_json.dumps({"type": "final", "answer": "clip.mp4 is 15s"}),
            stop_reason=StopReason.END_TURN,
            model_id="cap",
        )
