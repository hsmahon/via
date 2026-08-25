"""Tracing and metrics ports plus the OpenTelemetry-compatible data model.

Every agent invocation produces a trace: a root ``agent.run`` span with
child spans for model calls, tool calls, prompt resolution and response
validation. Span records use OTel naming (``trace_id`` 32-hex,
``span_id`` 16-hex, nanosecond timestamps, structured attributes) so a
production exporter (Amazon Bedrock AgentCore Observability / CloudWatch
via the OpenTelemetry SDK) can be attached later without touching business
logic. The v0.1 implementation ships an in-process tracer that also emits
structured log lines.
"""

from __future__ import annotations

import logging
import secrets
import threading
from collections import deque
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Protocol, runtime_checkable

from via_harness.errors import ErrorCategory

__all__ = ["LocalMetrics", "LocalTracer", "SpanHandle", "SpanRecord", "new_span_id", "new_trace_id"]

_HEX_SPAN_BYTES = 8  # 16 hex chars, OTel span-id width
_HEX_TRACE_BYTES = 16  # 32 hex chars, OTel trace-id width


def new_trace_id() -> str:
    """Generate an OpenTelemetry-compatible trace id.

    Returns:
        Random 32-character lowercase hex string.
    """
    return secrets.token_hex(_HEX_TRACE_BYTES)


def new_span_id() -> str:
    """Generate an OpenTelemetry-compatible span id.

    Returns:
        Random 16-character lowercase hex string.
    """
    return secrets.token_hex(_HEX_SPAN_BYTES)


@dataclass
class SpanRecord:
    """One finished or in-flight span of an agent run.

    Attributes:
        run_id: Agent run this span belongs to.
        trace_id: Run-scoped OTel-compatible trace id.
        span_id: Unique id of this span.
        parent_span_id: Parent span id, ``None`` for the root.
        name: Hierarchical name such as ``agent.run`` or ``tool.invoke``.
        attributes: Structured key/value context (model, tool, usage, ...).
        status: ``ok`` or ``error`` once ended; in-flight spans are ``ok``
            until marked otherwise.
        error_category: Error taxonomy category when the span failed.
        error_message: Error message when the span failed.
        started_at: UTC start timestamp.
        ended_at: UTC end timestamp, ``None`` while in flight.
        duration_ms: Wall-clock duration, ``None`` while in flight.
    """

    run_id: str
    trace_id: str
    span_id: str = field(default_factory=new_span_id)
    parent_span_id: str | None = None
    name: str = ""
    attributes: dict[str, Any] = field(default_factory=dict)
    status: str = "ok"
    error_category: str | None = None
    error_message: str | None = None
    started_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    ended_at: datetime | None = None
    duration_ms: float | None = None


class SpanHandle(Protocol):
    """Mutable handle returned by :meth:`Tracer.span`."""

    def set_attribute(self, key: str, value: Any) -> None:
        """Attach structured metadata to the span.

        Args:
            key: Attribute name in dot-notation (e.g. ``tool.name``).
            value: JSON-safe attribute value.
        """
        ...

    def record_error(self, category: ErrorCategory, message: str) -> None:
        """Mark the span as failed.

        Args:
            category: Harness error category.
            message: Error description.
        """
        ...


@runtime_checkable
class Tracer(Protocol):
    """Port producing hierarchical, correlated spans."""

    def start_span(
        self,
        *,
        run_id: str,
        trace_id: str,
        name: str,
        parent_span_id: str | None = None,
        **attributes: Any,
    ) -> tuple[SpanRecord, SpanHandle]:
        """Open a new span.

        Args:
            run_id: Owning agent run.
            trace_id: Trace shared by all spans of the run.
            name: Span name.
            parent_span_id: Parent span, if nested.
            **attributes: Initial structured attributes.

        Returns:
            The live record plus a handle for mutating/ending it.
        """
        ...

    def end_span(self, record: SpanRecord) -> None:
        """Close a span, computing duration and emitting telemetry.

        Args:
            record: The span previously returned by :meth:`start_span`.
        """
        ...

    def query(self, run_id: str) -> list[SpanRecord]:
        """Return all recorded spans for one run.

        Args:
            run_id: Agent run identifier.

        Returns:
            Spans ordered by start time.
        """
        ...


class _LocalSpanHandle:
    """Concrete handle mutating an in-memory :class:`SpanRecord`."""

    def __init__(self, record: SpanRecord, lock: threading.Lock) -> None:
        """Initialize the handle.

        Args:
            record: Live span record to mutate.
            lock: Shared registry lock guarding concurrent mutation.
        """
        self._record = record
        self._lock = lock

    def set_attribute(self, key: str, value: Any) -> None:
        """Attach structured metadata to the span.

        Args:
            key: Attribute name in dot-notation.
            value: JSON-safe attribute value.
        """
        with self._lock:
            self._record.attributes[key] = value

    def record_error(self, category: ErrorCategory, message: str) -> None:
        """Mark the span failed with category and message.

        Args:
            category: Harness error category.
            message: Error description.
        """
        with self._lock:
            self._record.status = "error"
            self._record.error_category = category.value
            self._record.error_message = message


class LocalTracer:
    """Thread-safe in-memory tracer emitting structured log lines.

    Suitable for local development, integration tests and the debug trace
    endpoint; production replaces it via the ``Tracer`` port without any
    change to the runner.
    """

    def __init__(self, *, capacity: int = 4096) -> None:
        """Initialize the tracer.

        Args:
            capacity: Maximum number of retained spans across runs.
        """
        self._lock = threading.Lock()
        self._spans: deque[SpanRecord] = deque(maxlen=capacity)

    def start_span(
        self,
        *,
        run_id: str,
        trace_id: str,
        name: str,
        parent_span_id: str | None = None,
        **attributes: Any,
    ) -> tuple[SpanRecord, SpanHandle]:
        """Create and retain a new in-flight span.

        Args:
            run_id: Owning agent run.
            trace_id: Trace shared by all spans of the run.
            name: Span name.
            parent_span_id: Parent span, if nested.
            **attributes: Initial structured attributes.

        Returns:
            The live record and its mutation handle.
        """
        record = SpanRecord(
            run_id=run_id,
            trace_id=trace_id,
            name=name,
            parent_span_id=parent_span_id,
            attributes=dict(attributes),
        )
        with self._lock:
            self._spans.append(record)
        return record, _LocalSpanHandle(record, self._lock)

    def end_span(self, record: SpanRecord) -> None:
        """Stamp end time/duration and emit a structured log record.

        Args:
            record: The span to finalize.
        """
        with self._lock:
            record.ended_at = datetime.now(UTC)
            delta = record.ended_at - record.started_at
            record.duration_ms = round(delta.total_seconds() * 1000, 3)
        logging.getLogger("via.harness.trace").info(
            "span.finished %s run_id=%s trace_id=%s span_id=%s status=%s duration_ms=%s attrs=%s",
            record.name,
            record.run_id,
            record.trace_id,
            record.span_id,
            record.status,
            record.duration_ms,
            _safe_attributes(record.attributes),
        )

    def query(self, run_id: str) -> list[SpanRecord]:
        """Return recorded spans for a run in start order.

        Args:
            run_id: Agent run identifier.

        Returns:
            Matching spans (shallow copies of records are not made; treat
            results as read-only).
        """
        with self._lock:
            spans = [s for s in self._spans if s.run_id == run_id]
        return sorted(spans, key=lambda s: s.started_at)


def _safe_attributes(attributes: dict[str, Any]) -> dict[str, Any]:
    """Flatten span attributes into log-safe keyword arguments.

    Args:
        attributes: Raw span attribute dictionary.

    Returns:
        Copy with dots replaced by underscores for logger compatibility.
    """
    return {key.replace(".", "_"): value for key, value in attributes.items()}


class MetricsSink(Protocol):
    """Minimal metrics port (counter-style) for harness telemetry."""

    def increment(self, name: str, *, value: int = 1, tags: dict[str, str] | None = None) -> None:
        """Increment a named metric.

        Args:
            name: Metric name (e.g. ``agent.runs.completed``).
            value: Delta to add.
            tags: Optional dimension tags.
        """
        ...


class LocalMetrics:
    """In-memory counter sink with snapshot support for tests/debug."""

    def __init__(self) -> None:
        """Initialize empty counters."""
        self._lock = threading.Lock()
        self._counters: dict[tuple[str, tuple[tuple[str, str], ...]], float] = {}

    def increment(self, name: str, *, value: int = 1, tags: dict[str, str] | None = None) -> None:
        """Add to a tagged counter.

        Args:
            name: Metric name.
            value: Delta to add.
            tags: Dimension tags; ordering-normalized internally.
        """
        key_tags = tuple(sorted((tags or {}).items()))
        with self._lock:
            key = (name, key_tags)
            self._counters[key] = self._counters.get(key, 0) + value

    def snapshot(self) -> dict[str, float]:
        """Return all counters flattened to ``name{tag=value,...}`` keys.

        Returns:
            Dictionary of current counter values.
        """
        with self._lock:
            flat: dict[str, float] = {}
            for (name, tags), value in self._counters.items():
                label = ",".join(f"{k}={v}" for k, v in tags)
                key = f"{name}{{{label}}}" if label else name
                flat[key] = value
            return flat
