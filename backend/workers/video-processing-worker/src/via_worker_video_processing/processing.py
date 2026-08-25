"""Future AWS service hooks (interfaces only for v0.1).

When enabled, the worker calls these after accepting an object-created
event. Both are real integration points with deliberate bodies pending:
Amazon Transcribe for speech-to-text and TwelveLabs Pegasus via Amazon
Bedrock for deep video understanding. Failures propagate so the worker can
mark the video FAILED - nothing is swallowed silently.
"""

from __future__ import annotations

from pydantic import BaseModel

__all__ = ["PegasusAnalysis", "TranscriptionResult", "analyze_with_pegasus", "transcribe"]


class TranscriptionResult(BaseModel):
    """Outcome of a Transcribe job (v0.2 shape)."""

    job_name: str
    transcript_key: str | None = None


class PegasusAnalysis(BaseModel):
    """Outcome of a Pegasus analysis call (v0.2 shape)."""

    answer: str


def transcribe(*, bucket: str, key: str) -> TranscriptionResult:
    """Start an Amazon Transcribe job for the uploaded object.

    Args:
        bucket: Source bucket.
        key: Object key of the media file.

    Returns:
        Job identifier and transcript artifact location.

    Raises:
        NotImplementedError: Until the v0.2 integration lands.
    """
    raise NotImplementedError("Amazon Transcribe integration is scheduled for v0.2")


def analyze_with_pegasus(*, bucket: str, key: str, question: str | None = None) -> PegasusAnalysis:
    """Analyze the uploaded video through TwelveLabs Pegasus on Bedrock.

    Args:
        bucket: Source bucket.
        key: Object key of the media file.
        question: Optional steering question.

    Returns:
        Model answer about the video content.

    Raises:
        NotImplementedError: Until the v0.2 integration lands.
    """
    _ = question
    raise NotImplementedError("TwelveLabs Pegasus integration is scheduled for v0.2")
