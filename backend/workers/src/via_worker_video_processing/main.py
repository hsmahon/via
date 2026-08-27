"""FastAPI application factory for the video-processing worker.

Exposes the HTTP event receiver at ``POST /events`` (EventBridge S3 Object
Created) and health at ``GET /health``, wiring :class:`WorkerSettings` and
:class:`VideoRepository` into request handling. Delegates object-created events
to :mod:`via_worker_video_processing.handlers` for state transitions.
"""

from __future__ import annotations

import logging
from functools import lru_cache
from typing import Any

from fastapi import APIRouter, Depends, FastAPI, HTTPException
from pydantic import BaseModel
from via_observability import RequestContextMiddleware, configure_logging

from via_worker_video_processing.events import parse_eventbridge_event
from via_worker_video_processing.handlers import HandlerOutcome, handle_object_created
from via_worker_video_processing.settings import WorkerSettings

__all__ = ["create_app"]


class Health(BaseModel):
    """Liveness payload."""

    service: str
    status: str


@lru_cache(maxsize=1)
def _settings() -> WorkerSettings:
    """Build process-wide worker settings.

    Returns:
        Parsed :class:`WorkerSettings`.
    """
    return WorkerSettings()


@lru_cache(maxsize=1)
def _repository(table_name: str, endpoint_url: str | None) -> Any:
    """Build the process-wide video repository.

    Args:
        table_name: DynamoDB table name.
        endpoint_url: Optional DynamoDB Local endpoint.

    Returns:
        Configured :class:`VideoRepository`.
    """
    from via_db import VideoRepository, get_table

    return VideoRepository(get_table(table_name, endpoint_url=endpoint_url))


def create_app(settings: WorkerSettings | None = None) -> FastAPI:
    """Build the configured worker application.

    The worker exposes an HTTP event receiver: locally MinIO webhooks post
    here; in production EventBridge → Step Functions tasks call the same
    handlers, so the state machine logic is identical.

    Args:
        settings: Optional settings override (tests).

    Returns:
        Assembled FastAPI app.
    """
    resolved = settings or _settings()
    configure_logging(resolved.service_name, level=resolved.log_level)
    app = FastAPI(title="Via Video Processing Worker", version="0.1.0")
    app.add_middleware(RequestContextMiddleware, service_name=resolved.service_name)
    router = APIRouter(tags=["events"])

    def repo() -> Any:
        """Resolve the video repository dependency.

        Returns:
            Configured repository.
        """
        return _repository(resolved.table_name, resolved.dynamodb_endpoint_url)

    @router.post("/events")
    def receive_event(payload: dict[str, Any], repository: Any = Depends(repo)) -> HandlerOutcome:
        """Accept an EventBridge S3 Object Created event.

        Args:
            payload: Raw EventBridge event JSON.
            repository: Video repository.

        Returns:
            Handler outcome.

        Raises:
            HTTPException: 400 for unrecognized payloads.
        """
        return _process(payload, repository)

    @router.post("/events/minio")
    def receive_minio_event(
        payload: dict[str, Any], repository: Any = Depends(repo)
    ) -> HandlerOutcome:
        """Accept an S3 event via the local MinIO compatibility route.

        Local MinIO webhooks should send the EventBridge shape; MinIO-native
        ``Records``/flat shapes are rejected as malformed (400).

        Args:
            payload: EventBridge-shaped JSON.
            repository: Video repository.

        Returns:
            Handler outcome.

        Raises:
            HTTPException: 400 for unrecognized payloads.
        """
        return _process(payload, repository)

    def _process(payload: dict[str, Any], repository: Any) -> HandlerOutcome:
        """Validate an EventBridge payload and handle the object-created event.

        Args:
            payload: Raw EventBridge event JSON.
            repository: Video repository.

        Returns:
            Handler outcome.

        Raises:
            HTTPException: 400 when validation fails.
        """
        try:
            event = parse_eventbridge_event(payload)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        outcome = handle_object_created(
            bucket=event.detail.bucket,
            key=event.detail.key,
            repository=repository,
            hooks_enabled=resolved.processing_hooks_enabled,
        )
        logging.getLogger("via.worker").info(
            "event handled: %s key=%s", outcome.status, event.detail.key
        )
        return outcome

    @app.get("/health", response_model=Health)
    def health() -> Health:
        """Report liveness.

        Returns:
            Static healthy payload.
        """
        return Health(service=resolved.service_name, status="ok")

    app.include_router(router)
    return app


app = create_app()
