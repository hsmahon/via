"""Explicit error taxonomy for the agent harness.

Every failure surfaced by the harness carries a machine-readable
:class:`ErrorCategory` and, when known, the ``run_id`` of the agent run it
belongs to so that errors are always traceable back to an invocation.
Exceptions are never silently swallowed: unexpected errors are recorded on
the run trace and then re-raised.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field

__all__ = ["ErrorCategory", "HarnessError", "RunFailure"]


class ErrorCategory(StrEnum):
    """Closed set of harness failure categories.

    The categories are part of Via's public API surface: HTTP handlers,
    traces and client SDKs all key off these values.
    """

    MODEL_ERROR = "MODEL_ERROR"
    TOOL_ERROR = "TOOL_ERROR"
    AUTHORIZATION_ERROR = "AUTHORIZATION_ERROR"
    TIMEOUT = "TIMEOUT"
    INVALID_REQUEST = "INVALID_REQUEST"
    INVALID_TOOL_ARGUMENTS = "INVALID_TOOL_ARGUMENTS"
    INVALID_MODEL_RESPONSE = "INVALID_MODEL_RESPONSE"
    INTERNAL_ERROR = "INTERNAL_ERROR"


class HarnessError(Exception):
    """Base class for every error raised inside the agent harness.

    Attributes:
        category: Machine-readable failure category.
        message: Human-readable description safe to expose in API responses.
        run_id: Identifier of the agent run the error belongs to, if known.
        details: Optional structured context (tool name, model id, ...).
        retryable: Whether retrying the same operation may succeed. Only
            transient infrastructure failures (e.g. model throttling) set
            this to ``True``.
        cause: Original exception, if this error wraps one.
    """

    def __init__(
        self,
        category: ErrorCategory,
        message: str,
        *,
        run_id: str | None = None,
        details: dict[str, Any] | None = None,
        retryable: bool = False,
        cause: BaseException | None = None,
    ) -> None:
        """Initialize the error.

        Args:
            category: Failure category from :class:`ErrorCategory`.
            message: Human-readable description.
            run_id: Agent run identifier for traceability, when available.
            details: Optional structured metadata attached to traces.
            retryable: Set for transient failures where a retry may help.
            cause: Wrapped original exception, preserved via ``raise from``.
        """
        super().__init__(message)
        self.category = category
        self.message = message
        self.run_id = run_id
        self.details: dict[str, Any] = details or {}
        self.retryable = retryable
        self.__cause__ = cause

    def to_dict(self) -> dict[str, Any]:
        """Serialize the error into a JSON-safe dictionary.

        Returns:
            Dictionary with ``category``, ``message``, ``run_id`` and
            ``details`` keys suitable for trace records and API payloads.
        """
        return {
            "category": self.category.value,
            "message": self.message,
            "run_id": self.run_id,
            "details": self.details,
        }

    def __str__(self) -> str:
        """Return a compact human-readable representation.

        Returns:
            String in the form ``[CATEGORY] message (run_id=...)``.
        """
        run = f" run_id={self.run_id}" if self.run_id else ""
        return f"[{self.category.value}] {self.message}{run}"


class RunFailure(BaseModel):
    """Structured failure outcome attached to an agent run result."""

    category: ErrorCategory
    message: str = Field(min_length=1)
    details: dict[str, Any] = Field(default_factory=dict)

    @classmethod
    def from_error(cls, error: HarnessError) -> RunFailure:
        """Build a :class:`RunFailure` from a :class:`HarnessError`.

        Args:
            error: The harness error raised during execution.

        Returns:
            A serializable failure record preserving category and details.
        """
        return cls(
            category=error.category,
            message=error.message,
            details=error.details,
        )
