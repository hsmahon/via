"""Provider-agnostic model invocation types.

These models define the wire contract between the agent runner and any
model backend (local stub, Amazon Bedrock / TwelveLabs Pegasus, future
providers). Bedrock-specific shapes never leak past :mod:`via_harness.model`.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field

__all__ = [
    "ModelMessage",
    "ModelRequest",
    "ModelResponse",
    "ModelRole",
    "ModelToolSpec",
    "StopReason",
    "TokenUsage",
    "ToolCallRequest",
]


class ModelRole(StrEnum):
    """Roles supported in the harness conversation format."""

    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"


class ToolCallRequest(BaseModel):
    """A tool invocation requested by the model."""

    call_id: str = Field(
        min_length=1, description="Opaque id used to correlate the follow-up tool result."
    )
    name: str = Field(min_length=1)
    arguments: dict[str, Any] = Field(default_factory=dict)


class ModelMessage(BaseModel):
    """One message in a model conversation.

    For ``role == TOOL`` the ``content`` carries a JSON-encoded
    ``{"type": "tool_result", ...}`` payload and ``tool_call_id`` references
    the originating :class:`ToolCallRequest`.
    """

    role: ModelRole
    content: str = ""
    tool_call_id: str | None = None


class ModelToolSpec(BaseModel):
    """Tool description handed to the model provider.

    ``parameters_json_schema`` is a standard JSON Schema object derived from
    the tool's typed input model; providers map it to their native formats.
    """

    name: str = Field(min_length=1)
    description: str = Field(min_length=1)
    parameters_json_schema: dict[str, Any]


class TokenUsage(BaseModel):
    """Token accounting reported by the provider, when available."""

    input_tokens: int | None = None
    output_tokens: int | None = None

    def merged(self, other: TokenUsage | None) -> TokenUsage:
        """Sum two usage records, treating missing values as zero.

        Args:
            other: Usage to add; ``None`` returns an equivalent copy.

        Returns:
            Aggregated token usage.
        """
        if other is None:
            return self.model_copy()
        return TokenUsage(
            input_tokens=(self.input_tokens or 0) + (other.input_tokens or 0),
            output_tokens=(self.output_tokens or 0) + (other.output_tokens or 0),
        )


class StopReason(StrEnum):
    """Why the provider stopped generating."""

    END_TURN = "end_turn"
    TOOL_USE = "tool_use"
    MAX_TOKENS = "max_tokens"
    ERROR = "error"


class ModelRequest(BaseModel):
    """A complete request to a model client.

    Attributes:
        messages: Conversation so far, oldest first. System text travels in
            ``system`` (providers that lack a system slot prepend it).
        system: Rendered system prompt for this run.
        tools: Tools discoverable by the model in this run.
        max_tokens: Generation budget per invocation.
        temperature: Sampling temperature; ``None`` uses the provider default.
    """

    messages: list[ModelMessage] = Field(min_length=1)
    system: str | None = None
    tools: list[ModelToolSpec] = Field(default_factory=list)
    max_tokens: int = Field(default=1024, ge=1)
    temperature: float | None = Field(default=None, ge=0.0, le=2.0)


class ModelResponse(BaseModel):
    """Normalized response from any model backend."""

    text: str | None = None
    tool_calls: list[ToolCallRequest] = Field(default_factory=list)
    stop_reason: StopReason
    usage: TokenUsage | None = None
    model_id: str | None = None


def last_user_message(request: ModelRequest) -> str:
    """Return the most recent user message content.

    Args:
        request: The outgoing model request.

    Returns:
        Text of the newest user message, or an empty string when absent.
    """
    for message in reversed(request.messages):
        if message.role is ModelRole.USER:
            return message.content
    return ""


def required_argument_fillers(spec: ModelToolSpec, user_text: str) -> dict[str, Any]:
    """Build minimal arguments satisfying a tool schema's required fields.

    Used by the deterministic local model client so scripted-free local runs
    can exercise real tools end-to-end. Only well-known argument names are
    auto-filled; anything else stays empty and surfaces as an invalid-tool-
    argument trace instead of guessing.

    Args:
        spec: The tool specification the model appears to be calling.
        user_text: Latest user message, used to fill free-text arguments.

    Returns:
        Arguments dictionary keyed by the schema's required property names.
    """
    schema = spec.parameters_json_schema
    required = schema.get("required", []) if isinstance(schema, dict) else []
    fillers: dict[str, Any] = {}
    for key in required:
        if key in {"question", "prompt", "query"}:
            fillers[key] = user_text[:1000]
    return fillers
