"""Transcribe helpers for the video worker."""

from __future__ import annotations

import hashlib

from pydantic import BaseModel, Field

__all__ = ["TranscriptionResult", "transcribe"]


class TranscriptionResult(BaseModel):
    """Result of starting a transcription job."""

    job_name: str = Field(min_length=1)
    transcript_key: str | None = None
    status: str = Field(default="COMPLETED", min_length=1)


def transcribe(*, bucket: str, key: str) -> TranscriptionResult:
    """Kick off transcription for an S3 object.

    Mock implementation: no AWS call, deterministic job name and key so
    tests and local runs behave predictably. The real Transcribe call
    will replace the body in v0.2.

    Args:
        bucket: Source bucket.
        key: Source object key.

    Returns:
        Mock job metadata.

    Raises:
        ValueError: When bucket or key is empty.
    """
    if not bucket or not bucket.strip():
        raise ValueError("bucket must be a non-empty string")
    if not key or not key.strip():
        raise ValueError("key must be a non-empty string")

    from via_worker_video_processing.events import parse_video_id

    video_id = parse_video_id(key)
    suffix = hashlib.sha256(f"{bucket}/{key}".encode()).hexdigest()[:8]
    job_name = f"mock-transcribe-{video_id or suffix}"
    transcript_key = f"transcripts/{video_id}/transcript.json" if video_id else None
    return TranscriptionResult(job_name=job_name, transcript_key=transcript_key, status="COMPLETED")
