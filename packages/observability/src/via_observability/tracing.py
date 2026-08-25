"""Tracing adapters implementing the harness ports.

Bridges ``via-harness`` trace/metrics records onto Via's structured logging
pipeline. Span records are OpenTelemetry-compatible (trace_id/span_id/
parent/duration/attributes) so a production exporter - Amazon Bedrock
AgentCore Observability or CloudWatch via the OpenTelemetry SDK - can be
attached later without touching the runner or business logic.
"""

from __future__ import annotations

import logging

from via_harness import LocalMetrics, LocalTracer  # re-exports for wiring convenience

__all__ = ["LocalMetrics", "LocalTracer", "configure_trace_logging"]


def configure_trace_logging(*, level: str = "INFO") -> None:
    """Route harness span logs through the service's JSON formatter level.

    Args:
        level: Level applied to the ``via.harness.trace`` logger.
    """
    logging.getLogger("via.harness.trace").setLevel(level.upper())
