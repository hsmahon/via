"""``get_transcript`` - interface for the Amazon Transcribe integration.

The transcript pipeline (Transcribe job → artifact on S3 → DynamoDB
pointer) has not landed yet, so the tool reports itself as unavailable.
The contract below is final; only the execution body will change.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field
from via_harness import AuthorizationContext, ToolContract, ToolResult, ToolStatus
from via_harness.context import Permission

__all__ = ["GetTranscriptTool", "Segment", "TranscriptInput", "TranscriptOutput"]


class TranscriptInput(BaseModel):
    """Arguments for ``get_transcript`` (none required)."""


class Segment(BaseModel):
    """One timestamped transcript segment."""

    start: float = Field(ge=0.0)
    end: float = Field(ge=0.0)
    text: str = Field(min_length=1)


class TranscriptOutput(BaseModel):
    """Payload returned once transcripts exist."""

    language: str | None = None
    segments: list[Segment] = Field(default_factory=list)


class GetTranscriptTool:
    """Exposes the video transcript to models (pending integration)."""

    contract = ToolContract(
        name="get_transcript",
        description="Return the timestamped transcript of the current video when processing has produced one.",
        input_model=TranscriptInput,
        output_model=TranscriptOutput,
        required_permissions=frozenset({Permission.TRANSCRIPT_READ}),
        timeout_seconds=5.0,
        owner="via-media-ingest",
    )

    def execute(
        self, *, video_id: str, authz: AuthorizationContext, arguments: dict[str, Any]
    ) -> ToolResult:
        """Report the pending integration.

        Args:
            video_id: Target video from the authorized context.
            authz: Caller context (unused beyond signature conformance).
            arguments: Validated empty arguments.

        Returns:
            Unavailable result until Amazon Transcribe lands in v0.2.
        """
        _ = video_id, authz, arguments
        return ToolResult(
            status=ToolStatus.UNAVAILABLE,
            detail="transcripts are not available yet: the Amazon Transcribe integration is scheduled for v0.2",
        )
