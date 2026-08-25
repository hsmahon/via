"""Deterministic local model client for development and tests.

``LocalModelClient`` lets the full agent loop run on a laptop with zero AWS
dependencies and no network access. It is intentionally simple:

* When scripted responses are supplied, they are returned in order. This
  gives tests exact control over tool-use rounds, malformed output, retries,
  and provider failures.
* Without scripts it follows a deterministic policy: call the first available
  tool once (auto-filling well-known required arguments), then emit a final
  structured answer summarizing whatever tool results exist.
"""

from __future__ import annotations

import json
from collections import deque
from collections.abc import Iterator
from typing import Any

from via_harness.errors import HarnessError
from via_harness.model.types import (
    ModelRequest,
    ModelResponse,
    ModelRole,
    StopReason,
    TokenUsage,
    ToolCallRequest,
    last_user_message,
    required_argument_fillers,
)

__all__ = ["LocalModelClient"]


class LocalModelClient:
    """Scriptable, dependency-free :class:`ModelClient` implementation."""

    def __init__(
        self,
        scripted: list[ModelResponse] | None = None,
        *,
        model_id: str = "via-local-model",
        fail_after_scripts: HarnessError | None = None,
    ) -> None:
        """Initialize the client.

        Args:
            scripted: Optional queue of responses returned in FIFO order.
            model_id: Identifier reported on every response (visible in traces).
            fail_after_scripts: If set, raised once the script queue is empty;
                useful for exercising model-failure paths deterministically.
        """
        self._scripted = deque(scripted or [])
        self._model_id = model_id
        self._fail_after_scripts = fail_after_scripts

    def invoke(
        self, request: ModelRequest, *, timeout_seconds: float | None = None
    ) -> ModelResponse:
        """Return the next scripted response or synthesize one.

        Args:
            request: Normalized conversation request (ignored timeout kept
                for protocol compatibility).
            timeout_seconds: Unused; accepted for protocol compatibility.

        Returns:
            The next response according to the scripting/heuristic policy.

        Raises:
            HarnessError: The injected ``fail_after_scripts`` error, if any.
        """
        if self._scripted:
            return self._scripted.popleft()
        if self._fail_after_scripts is not None:
            raise self._fail_after_scripts

        has_tool_result = any(m.role is ModelRole.TOOL for m in request.messages)
        has_assistant = any(m.role is ModelRole.ASSISTANT for m in request.messages)

        if request.tools and not has_tool_result and not has_assistant:
            return self._tool_call_response(request)
        return self._final_response(request)

    def stream(
        self, request: ModelRequest, *, timeout_seconds: float | None = None
    ) -> Iterator[str]:
        """Yield the synthesized answer word by word.

        Args:
            request: Normalized conversation request.
            timeout_seconds: Unused; accepted for protocol compatibility.

        Yields:
            Individual whitespace-separated chunks of the final text.
        """
        response = self.invoke(request)
        for word in (response.text or "").split():
            yield word + " "

    # ------------------------------------------------------------------
    # Heuristics
    # ------------------------------------------------------------------

    def _tool_call_response(self, request: ModelRequest) -> ModelResponse:
        """Build the deterministic first-round tool invocation.

        Args:
            request: Request whose tools should be called.

        Returns:
            Response carrying the wire-contract ``tool_request`` payload.
        """
        spec = request.tools[0]
        arguments = required_argument_fillers(spec, last_user_message(request))
        call = ToolCallRequest(
            call_id=f"local-call-{len(request.messages)}", name=spec.name, arguments=arguments
        )
        body = {"type": "tool_request", "tool": spec.name, "arguments": arguments}
        return ModelResponse(
            text=json.dumps(body),
            tool_calls=[call],
            stop_reason=StopReason.TOOL_USE,
            usage=TokenUsage(input_tokens=10, output_tokens=5),
            model_id=self._model_id,
        )

    def _final_response(self, request: ModelRequest) -> ModelResponse:
        """Build the final structured JSON answer from prior tool results.

        Args:
            request: Conversation containing at least one tool result.

        Returns:
            Response whose text is the JSON-encoded final-answer payload.
        """
        context_bits: list[str] = []
        citations: list[dict[str, Any]] = []
        for message in request.messages:
            if message.role is not ModelRole.TOOL:
                continue
            try:
                payload = json.loads(message.content)
            except json.JSONDecodeError:
                continue
            inner = payload.get("payload") or {}
            video = inner.get("video") if isinstance(inner, dict) else None
            if isinstance(video, dict) and video.get("filename"):
                context_bits.append(f'file "{video["filename"]}"')
                duration = video.get("duration")
                if isinstance(duration, (int, float)) and duration > 0:
                    citations.append(
                        {
                            "video_id": str(video.get("video_id", "")),
                            "timestamp_start": 0.0,
                            "timestamp_end": round(float(duration), 3),
                        }
                    )
            elif isinstance(inner, dict) and inner.get("status") == "unavailable":
                context_bits.append(str(inner.get("detail", "a pending integration")))

        answer = (
            f"Here is what I know about this video based on {', '.join(context_bits)}."
            if context_bits
            else "I could not retrieve additional context about this video."
        )
        body: dict[str, Any] = {"type": "final", "answer": answer, "citations": citations}
        return ModelResponse(
            text=json.dumps(body),
            tool_calls=[],
            stop_reason=StopReason.END_TURN,
            usage=TokenUsage(input_tokens=20, output_tokens=30),
            model_id=self._model_id,
        )
