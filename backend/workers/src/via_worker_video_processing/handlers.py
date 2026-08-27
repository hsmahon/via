"""Event handlers driving the video state machine."""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from via_db import InvalidTransition, VideoNotFound, VideoRepository, VideoStatus

from via_worker_video_processing.events import parse_video_id
from via_worker_video_processing.pegasus import PegasusAnalysis, analyze_with_pegasus
from via_worker_video_processing.transcribe import TranscriptionResult, transcribe

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
    transcribe_fn: Callable[..., TranscriptionResult] | None = None,
    analyze_fn: Callable[..., PegasusAnalysis] | None = None,
) -> HandlerOutcome:
    """Drive UPLOADING → PROCESSING → PROCESSED for an uploaded object.

    Dependency boundaries for external processing are exposed via
    ``transcribe_fn`` and ``analyze_fn``. Production code uses the
    default :func:`transcribe` / :func:`analyze_with_pegasus` (deterministic
    mocks in V0.1, real AWS calls in V0.2). Tests inject mocked callables
    to verify orchestration and failure handling without AWS.

    Args:
        bucket: S3 bucket containing the object.
        key: S3 object key (``videos/<user>/<video>/<file>``).
        repository: Video repository for state transitions.
        hooks_enabled: When True, kick off Transcribe and Pegasus.
        transcribe_fn: Optional override for :func:`transcribe` (tests).
        analyze_fn: Optional override for :func:`analyze_with_pegasus` (tests).

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
        _transcribe: Callable[..., Any] = transcribe_fn if transcribe_fn is not None else transcribe
        _analyze: Callable[..., Any] = (
            analyze_fn if analyze_fn is not None else analyze_with_pegasus
        )
        try:
            _transcribe(bucket=bucket, key=key)
            _analyze(bucket=bucket, key=key)
        except Exception as exc:
            logger.warning("processing hooks failed for video %s: %s", video_id, exc)
            failed = repository.update_status(video_id, VideoStatus.FAILED)
            return HandlerOutcome(status="failed", video_id=failed.video_id, detail=str(exc))

    processed = repository.update_status(video_id, VideoStatus.PROCESSED)
    logger.info("video %s processed", video_id)
    return HandlerOutcome(status="processed", video_id=processed.video_id)
