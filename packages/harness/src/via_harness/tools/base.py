"""Via-owned tool contract and invocation types.

A tool is a typed, permission-guarded capability with explicit operational
metadata (owner, timeout, version). The contract is deliberately narrow:
only capabilities Via actually needs become tools.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Protocol, runtime_checkable

from pydantic import BaseModel, Field

from via_harness.context import AuthorizationContext, Permission
from via_harness.errors import ErrorCategory, HarnessError

__all__ = [
    "Tool",
    "ToolContract",
    "ToolExecutionError",
    "ToolResult",
    "ToolStatus",
]


@dataclass(frozen=True)
class ToolContract:
    """Static metadata describing a tool.

    Attributes:
        name: Unique snake_case identifier (e.g. ``get_transcript``).
        description: Natural-language summary shown to models and operators.
        input_model: Pydantic model class validating arguments.
        output_model: Pydantic model class describing successful payloads.
        required_permissions: Permissions a caller must hold for this tool
            to run against the target video.
        version: Integer tool version; bump on behavior changes.
        timeout_seconds: Hard wall-clock budget enforced by the executor.
        owner: Team or service accountable for the tool.
    """

    name: str
    description: str
    input_model: type[BaseModel]
    output_model: type[BaseModel]
    required_permissions: frozenset[Permission] = field(default_factory=frozenset)
    version: int = 1
    timeout_seconds: float = 10.0
    owner: str = "via-agent-platform"

    def model_tool_spec(self) -> dict[str, Any]:
        """Render the provider-neutral tool spec for model requests.

        Returns:
            Dictionary with ``name``, ``description`` and JSON-Schema
            ``parameters_json_schema`` derived from ``input_model``.
        """
        return {
            "name": self.name,
            "description": self.description,
            "parameters_json_schema": self.input_model.model_json_schema(),
        }


class ToolStatus(StrEnum):
    """Outcome of a tool invocation.

    ``UNAVAILABLE`` signals a known-pending integration (e.g. transcripts
    before Amazon Transcribe is wired) - it is a valid, traceable result fed
    back to the model, not an error.
    """

    OK = "ok"
    UNAVAILABLE = "unavailable"


class ToolResult(BaseModel):
    """Normalized result of one tool invocation."""

    status: ToolStatus
    payload: dict[str, Any] | None = None
    detail: str | None = Field(
        default=None, description="Human-readable note, required when status is UNAVAILABLE."
    )
    latency_ms: int = Field(default=0, ge=0)


class ToolExecutionError(HarnessError):
    """Raised by tools or the executor when invocation fails."""

    def __init__(
        self,
        message: str,
        *,
        tool_name: str,
        run_id: str | None = None,
        cause: BaseException | None = None,
    ) -> None:
        """Initialize a tool execution failure.

        Args:
            message: Human-readable failure description.
            tool_name: Name from the tool contract.
            run_id: Agent run identifier for traceability.
            cause: Original exception when wrapping one.
        """
        super().__init__(
            ErrorCategory.TOOL_ERROR,
            message,
            run_id=run_id,
            details={"tool": tool_name},
            cause=cause,
        )
        self.tool_name = tool_name


@runtime_checkable
class Tool(Protocol):
    """Port every Via tool implements.

    Implementations own their :class:`ToolContract` as the class attribute
    ``contract`` and perform their work in :meth:`execute`, receiving the
    already-validated arguments plus the authorization context of the run.
    """

    contract: ToolContract

    def execute(
        self, *, video_id: str, authz: AuthorizationContext, arguments: dict[str, Any]
    ) -> ToolResult:
        """Run the tool against a specific video.

        Args:
            video_id: Target video, inherited from the authorized context.
            authz: Authorization context of the calling user.
            arguments: Validated arguments matching the contract's input model.

        Returns:
            Normalized tool result (``OK`` or ``UNAVAILABLE``).

        Raises:
            Exception: Unexpected failures; the executor normalizes them to
                ``ToolExecutionError`` so nothing is swallowed silently.
        """
        ...
