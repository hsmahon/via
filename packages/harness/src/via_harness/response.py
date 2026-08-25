"""Structured agent response contract.

The final model output must be strict JSON matching :class:`FinalAnswer`.
Citations carry the timestamps the UI will eventually use to jump into the
video. Validation failures surface as ``INVALID_MODEL_RESPONSE`` so bad
model output is visible in traces instead of leaking to clients.
"""

from __future__ import annotations

import json
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from via_harness.errors import ErrorCategory, HarnessError

__all__ = ["AgentResponse", "Citation", "FinalAnswer", "parse_model_output"]

_FINAL_RESPONSE_INSTRUCTION = """
You must respond with exactly one JSON object and no other text.
To call a tool: {"type": "tool_request", "tool": "<tool name>", "arguments": {...}}
To give the final answer:
{"type": "final", "answer": "<answer text>", "citations": [{"video_id": "...", "timestamp_start": 0.0, "timestamp_end": 0.0, "transcript_reference": null}]}
Only cite the video you were asked about. Omit citation fields you cannot support.
"""


def final_response_instruction() -> str:
    """Return the mechanical wire-contract instruction appended to prompts.

    Returns:
        Instruction text describing the tool-request/final-answer JSON
        protocol every model must follow regardless of backend.
    """
    return _FINAL_RESPONSE_INSTRUCTION


class Citation(BaseModel):
    """A pointer into the video that supports part of the answer."""

    model_config = ConfigDict(frozen=True)

    video_id: str = Field(min_length=1)
    timestamp_start: float | None = Field(default=None, ge=0.0)
    timestamp_end: float | None = Field(default=None, ge=0.0)
    transcript_reference: str | None = Field(
        default=None, description="Reference into transcript segments, when available."
    )

    def scoped_to(self, video_id: str) -> bool:
        """Check whether this citation points at the expected video.

        Args:
            video_id: Video the agent run is authorized for.

        Returns:
            True when the citation references exactly ``video_id``.
        """
        return self.video_id == video_id


class FinalAnswer(BaseModel):
    """Strict schema of the model's terminal JSON payload."""

    type: Literal["final"]
    answer: str = Field(min_length=1)
    citations: list[Citation] = Field(default_factory=list)


class ToolRequest(BaseModel):
    """Strict schema of a mid-conversation tool-request payload."""

    type: Literal["tool_request"]
    tool: str = Field(min_length=1)
    arguments: dict[str, Any] = Field(default_factory=dict)


class AgentResponse(BaseModel):
    """Validated agent answer returned to API clients."""

    answer: str = Field(min_length=1)
    citations: list[Citation] = Field(default_factory=list)


def parse_model_output(text: str) -> FinalAnswer | ToolRequest:
    """Parse and validate raw model text against the wire contract.

    Args:
        text: Raw text produced by the model; must be a single JSON object.

    Returns:
        A typed final answer or tool request.

    Raises:
        HarnessError: Category ``INVALID_MODEL_RESPONSE`` for non-JSON
            output, unknown payload types or schema violations.
    """
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise HarnessError(
            ErrorCategory.INVALID_MODEL_RESPONSE,
            "Model output is not valid JSON",
            details={"parse_error": str(exc)},
            cause=exc,
        ) from exc
    if not isinstance(data, dict):
        raise HarnessError(
            ErrorCategory.INVALID_MODEL_RESPONSE,
            "Model output must be a JSON object",
            details={"kind": type(data).__name__},
        )
    kind = data.get("type")
    try:
        if kind == "final":
            return FinalAnswer.model_validate(data)
        if kind == "tool_request":
            return ToolRequest.model_validate(data)
    except ValidationError as exc:
        raise HarnessError(
            ErrorCategory.INVALID_MODEL_RESPONSE,
            f"Model output failed {kind} schema validation",
            details={"errors": exc.errors(include_url=False)},
            cause=exc,
        ) from exc
    raise HarnessError(
        ErrorCategory.INVALID_MODEL_RESPONSE,
        f"Unknown model payload type: {kind!r}",
        details={"expected": ["final", "tool_request"]},
    )


def validate_agent_answer(answer: FinalAnswer, *, video_id: str) -> AgentResponse:
    """Enforce run-scoped rules on a validated final answer.

    Args:
        answer: Schema-valid final answer from the model.
        video_id: Video this run is authorized to discuss.

    Returns:
        Client-facing agent response.

    Raises:
        HarnessError: Category ``INVALID_MODEL_RESPONSE`` when any citation
            references a different video than the one authorized.
    """
    foreign = [c.model_dump() for c in answer.citations if not c.scoped_to(video_id)]
    if foreign:
        raise HarnessError(
            ErrorCategory.INVALID_MODEL_RESPONSE,
            "Model cited a video outside the authorized scope",
            details={"authorized_video_id": video_id, "foreign_citations": foreign},
        )
    return AgentResponse(answer=answer.answer, citations=list(answer.citations))
