"""Pydantic request/response schemas for the public REST surface."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field
from via_db import VideoStatus

__all__ = [
    "CreateVideoRequest",
    "CreateVideoResponse",
    "ErrorResponse",
    "HealthResponse",
    "UploadTarget",
    "VideoListResponse",
    "VideoResponse",
]


class CreateVideoRequest(BaseModel):
    """Body of ``POST /videos``."""

    filename: str = Field(min_length=1, max_length=255, description="Original file name.")
    duration: float | None = Field(
        default=None, gt=0.0, description="Duration in seconds, if known client-side."
    )
    content_type: str | None = Field(
        default=None, max_length=100, description='MIME type, e.g. "video/mp4".'
    )


class UploadTarget(BaseModel):
    """Where and how the client should upload the bytes."""

    url: str
    method: str = "PUT"
    expires_in_seconds: int


class CreateVideoResponse(BaseModel):
    """Response of ``POST /videos`` - a fresh upload session."""

    video_id: str
    user_id: str
    status: VideoStatus
    upload: UploadTarget


class VideoResponse(BaseModel):
    """One stored video."""

    video_id: str
    user_id: str
    filename: str
    duration: float | None
    status: VideoStatus
    created_at: datetime
    updated_at: datetime


class VideoListResponse(BaseModel):
    """Page of videos for one user."""

    items: list[VideoResponse]
    count: int


class HealthResponse(BaseModel):
    """Liveness payload."""

    service: str
    status: str
    version: str


class ErrorResponse(BaseModel):
    """Standard error envelope."""

    detail: str
