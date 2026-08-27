"""Pegasus helpers for the video worker."""

from __future__ import annotations

from pydantic import BaseModel, Field

__all__ = ["PegasusAnalysis", "VideoAnalysis", "analyze_with_pegasus"]


class PegasusAnalysis(BaseModel):
    """Result of a Pegasus analysis call."""

    answer: str = Field(min_length=1)


# Alias for early spec name.
VideoAnalysis = PegasusAnalysis


def analyze_with_pegasus(*, bucket: str, key: str, question: str | None = None) -> PegasusAnalysis:
    """Analyze a video with TwelveLabs Pegasus.

    Mock implementation: deterministic answer, no Bedrock call.
    Real ``bedrock-runtime:converse`` call will replace the body in v0.2
    (model ``us.twelvelabs.pegasus-1-2``).

    Args:
        bucket: Source bucket.
        key: Source object key.
        question: Optional steering question.

    Returns:
        Mock analysis result.

    Raises:
        ValueError: When bucket or key is empty.
    """
    if not bucket or not bucket.strip():
        raise ValueError("bucket must be a non-empty string")
    if not key or not key.strip():
        raise ValueError("key must be a non-empty string")
    q = f" question={question!r}" if question else ""
    answer = f"[mock Pegasus analysis for s3://{bucket}/{key}{q}]"
    return PegasusAnalysis(answer=answer)
