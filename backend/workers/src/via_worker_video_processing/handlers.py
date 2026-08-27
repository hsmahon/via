"""Event handlers driving the video state machine.

Exports :class:`HandlerOutcome` and :func:`handle_object_created` which drives ``UPLOADING`` → ``PROCESSING`` → ``PROCESSED``/``FAILED`` via :class:`VideoRepository` with idempotent handling and optional Pegasus analysis.
Depends on :mod:`via_db` for state transitions and :mod:`via_worker_video_processing.pegasus` for video analysis.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from via_db import InvalidTransition, VideoNotFound, VideoRepository, VideoStatus

from via_worker_video_processing.events import parse_video_id
from via_worker_video_processing.pegasus import PegasusAnalysis, analyze_with_pegasus

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
    analyze_fn: Callable[..., PegasusAnalysis] | None = None,
) -> HandlerOutcome:
    """Drive UPLOADING → PROCESSING → PROCESSED for an uploaded object.

    Dependency boundary for video analysis is exposed via ``analyze_fn``.
    Production code uses the default :func:`analyze_with_pegasus` which
    invokes TwelveLabs Pegasus 1.2 via Bedrock ``InvokeModel`` with
    ``mediaSource.s3Location.uri`` without downloading the object.
    Tests inject a mocked callable to verify orchestration without
    external calls.

    Args:
        bucket: S3 bucket containing the object.
        key: S3 object key (``videos/<user>/<video>/<file>``).
        repository: Video repository for state transitions.
        hooks_enabled: When True, run Pegasus analysis.
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
        _analyze: Callable[..., Any] = (
            analyze_fn if analyze_fn is not None else analyze_with_pegasus
        )
        try:
            _analyze(bucket=bucket, key=key)
        except Exception as exc:
            logger.warning("processing hooks failed for video %s: %s", video_id, exc)
            failed = repository.update_status(video_id, VideoStatus.FAILED)
            return HandlerOutcome(status="failed", video_id=failed.video_id, detail=str(exc))

    processed = repository.update_status(video_id, VideoStatus.PROCESSED)
    logger.info("video %s processed", video_id)
    return HandlerOutcome(status="processed", video_id=processed.video_id)
