"""HTTP schemas for the agent service."""

from __future__ import annotations

from pydantic import BaseModel, Field
from via_harness import Citation, StepSummary, TokenUsage

__all__ = ["ErrorResponse", "HealthResponse", "InvokeRequest", "InvokeResponse", "TraceResponse"]


class InvokeRequest(BaseModel):
    """Body of ``POST /agent/invoke``."""

    message: str = Field(min_length=1, max_length=4000)
    video_id: str = Field(min_length=1)
    session_id: str | None = None
    prompt_name: str = Field(default="video_assistant")


class InvokeResponse(BaseModel):
    """Successful agent invocation."""

    run_id: str
    trace_id: str
    session_id: str
    answer: str
    citations: list[Citation]
    steps: list[StepSummary]
    usage: TokenUsage


class TraceResponse(BaseModel):
    """Debug payload exposing recorded spans for one run."""

    run_id: str
    spans: list[dict[str, object]]


class HealthResponse(BaseModel):
    """Liveness payload."""

    service: str
    status: str
    version: str


class ErrorResponse(BaseModel):
    """Standard error envelope."""

    detail: str
    category: str | None = None
    run_id: str | None = None
