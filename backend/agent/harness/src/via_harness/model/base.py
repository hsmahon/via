"""Model client port - the harness boundary to any LLM/video-model backend.

Via's business logic depends only on :class:`ModelClient`. Concrete
implementations (local deterministic stub, Amazon Bedrock with TwelveLabs
Pegasus) live beside it and are selected at wiring time, never inside the
agent runner.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from via_harness.model.types import ModelRequest, ModelResponse

__all__ = ["ModelClient", "RetryPolicy"]


@runtime_checkable
class ModelClient(Protocol):
    """Port every model backend must satisfy.

    Implementations translate :class:`ModelRequest` into their native API,
    normalize the reply into :class:`ModelResponse`, and raise
    ``HarnessError`` with category ``MODEL_ERROR`` on failure. Timeouts are
    expressed in seconds and enforced by the implementation.
    """

    def invoke(
        self, request: ModelRequest, *, timeout_seconds: float | None = None
    ) -> ModelResponse:
        """Perform a single completion request.

        Args:
            request: Normalized conversation request.
            timeout_seconds: Wall-clock budget; ``None`` means the
                implementation default.

        Returns:
            Normalized model response.

        Raises:
            HarnessError: Category ``MODEL_ERROR`` (retryable for transient
                provider failures), or ``TIMEOUT`` when the deadline lapses.
        """
        ...

    def stream(
        self, request: ModelRequest, *, timeout_seconds: float | None = None
    ) -> Iterator[str]:
        """Stream partial text chunks for a completion request.

        The v0.1 contract returns an iterator of string chunks; streaming is
        not yet consumed by the agent runner but the seam exists so response
        streaming can be added without touching business logic.

        Args:
            request: Normalized conversation request.
            timeout_seconds: Wall-clock budget; ``None`` means default.

        Returns:
            Iterable of incremental text chunks.

        Raises:
            HarnessError: Same semantics as :meth:`invoke`.
        """
        ...


@dataclass(frozen=True)
class RetryPolicy:
    """Retry configuration for transient provider failures.

    Only errors marked retryable by the implementation (throttling, transient
    service errors) are retried. Deterministic failures such as invalid model
    output never retry.
    """

    max_attempts: int = 1
    initial_backoff_seconds: float = 0.25
    multiplier: float = 2.0

    def validated(self) -> RetryPolicy:
        """Return a sanitized copy of the policy.

        Returns:
            Policy with ``max_attempts >= 1`` and positive backoff values.
        """
        return RetryPolicy(
            max_attempts=max(1, self.max_attempts),
            initial_backoff_seconds=max(0.0, self.initial_backoff_seconds),
            multiplier=max(1.0, self.multiplier),
        )
