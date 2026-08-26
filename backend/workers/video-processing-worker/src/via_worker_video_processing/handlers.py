"""Event handlers driving the video state machine."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from via_db import InvalidTransition, VideoNotFound, VideoRepository, VideoStatus

from via_worker_video_processing.events import parse_video_id
from via_worker_video_processing.processing import analyze_with_pegasus, transcribe

logger = logging.getLogger("via.worker")


@dataclass(frozen=True)
class HandlerOutcome:
    """Result of processing one event (for tests and tracing)."""

    status: str  # "processed" | "failed" | "ignored"
    video_id: str | None = None
    detail: str | None = None


def handle_object_created(
    *,
    bucket: str,
    key: str,
    repository: VideoRepository,
    hooks_enabled: bool = False,
) -> HandlerOutcome:
    """Drive UPLOADING → PROCESSING → PROCESSED for an uploaded object.

    The ``UPLOADING → PROCESSING`` transition is performed as an atomic
    DynamoDB conditional update (``status = UPLOADING``). Duplicate
    deliveries therefore fail the condition and are treated as safely
    handled rather than retried.

    Unknown videos and non-video keys are ignored (acknowledged without
    action) so replayed or unrelated events never wedge the pipeline.

    Args:
        bucket: S3 bucket containing the object.
        key: S3 object key (``videos/<user>/<video>/<file>``).
        repository: Video repository for state transitions.
        hooks_enabled: When True, invoke the pending Transcribe/Pegasus
            interfaces; their NotImplementedError marks the video FAILED.

    Returns:
        Structured outcome describing what happened.
    """
    video_id = parse_video_id(key)
    if video_id is None:
        return HandlerOutcome(status="ignored", detail=f"key not a video object: {key}")

    try:
        repository.mark_processing(video_id)
    except VideoNotFound:
        logger.warning("event for unknown video %s ignored", video_id)
        return HandlerOutcome(status="ignored", video_id=video_id, detail="unknown video")
    except InvalidTransition as exc:
        return HandlerOutcome(status="ignored", video_id=video_id, detail=str(exc))

    if hooks_enabled:
        try:
            transcribe(bucket=bucket, key=key)
            analyze_with_pegasus(bucket=bucket, key=key)
        except NotImplementedError as exc:
            failed = repository.update_status(video_id, VideoStatus.FAILED)
            return HandlerOutcome(status="failed", video_id=failed.video_id, detail=str(exc))

    processed = repository.update_status(video_id, VideoStatus.PROCESSED)
    logger.info("video %s processed", video_id)
    return HandlerOutcome(status="processed", video_id=processed.video_id)
