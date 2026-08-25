"""Event handlers driving the video state machine."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from via_db import InvalidTransition, VideoNotFound, VideoRepository, VideoStatus

from via_worker_video_processing.envelope import EventEnvelope
from via_worker_video_processing.processing import analyze_with_pegasus, transcribe

logger = logging.getLogger("via.worker")


@dataclass(frozen=True)
class HandlerOutcome:
    """Result of processing one event (for tests and tracing)."""

    status: str  # "processed" | "failed" | "ignored"
    video_id: str | None = None
    detail: str | None = None


def handle_object_created(
    envelope: EventEnvelope,
    *,
    repository: VideoRepository,
    hooks_enabled: bool = False,
) -> HandlerOutcome:
    """Drive UPLOADING → PROCESSING → PROCESSED for an uploaded object.

    Unknown videos and non-video keys are ignored (acknowledged without
    action) so replayed or unrelated events never wedge the pipeline.

    Args:
        envelope: Canonical event.
        repository: Video repository for state transitions.
        hooks_enabled: When True, invoke the pending Transcribe/Pegasus
            interfaces; their NotImplementedError marks the video FAILED.

    Returns:
        Structured outcome describing what happened.
    """
    video_id = envelope.parse_video_id()
    if video_id is None:
        return HandlerOutcome(
            status="ignored", detail=f"key not a video object: {envelope.detail.key}"
        )

    try:
        repository.update_status(video_id, VideoStatus.PROCESSING)
    except VideoNotFound:
        logger.warning("event for unknown video %s ignored", video_id)
        return HandlerOutcome(status="ignored", video_id=video_id, detail="unknown video")
    except InvalidTransition as exc:
        return HandlerOutcome(status="ignored", video_id=video_id, detail=str(exc))

    if hooks_enabled:
        try:
            transcribe(bucket=envelope.detail.bucket, key=envelope.detail.key)
            analyze_with_pegasus(bucket=envelope.detail.bucket, key=envelope.detail.key)
        except NotImplementedError as exc:
            failed = repository.update_status(video_id, VideoStatus.FAILED)
            return HandlerOutcome(status="failed", video_id=failed.video_id, detail=str(exc))

    processed = repository.update_status(video_id, VideoStatus.PROCESSED)
    logger.info("video %s processed", video_id)
    return HandlerOutcome(status="processed", video_id=processed.video_id)
