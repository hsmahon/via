"""Video lifecycle routes."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from via_db import (
    InvalidTransition,
    VideoAlreadyExists,
    VideoRecord,
    VideoRepository,
)

from via_api.deps import get_presigner, get_video_repository, user_id_header
from via_api.schemas import (
    CreateVideoRequest,
    CreateVideoResponse,
    UploadTarget,
    VideoListResponse,
    VideoResponse,
)
from via_api.storage import Presigner

router = APIRouter(prefix="/videos", tags=["videos"])


@router.post(
    "",
    response_model=CreateVideoResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create an upload session",
)
def create_video(
    body: CreateVideoRequest,
    repo: Annotated[VideoRepository, Depends(get_video_repository)],
    presigner: Annotated[Presigner, Depends(get_presigner)],
    user_id: Annotated[str, Depends(user_id_header)],
) -> CreateVideoResponse:
    """Register a new video and hand back a presigned upload target.

    The record starts in ``UPLOADING``; the storage layer's object-created
    event drives the transition to ``PROCESSING`` once bytes land.

    Args:
        body: Validated creation payload.
        repo: Video repository.
        presigner: S3 presigned-URL issuer.
        user_id: Acting user from the identity dependency.

    Returns:
        Created session including the PUT target.
    """
    video_id = uuid.uuid4().hex
    try:
        record = repo.create(
            video_id=video_id,
            user_id=user_id,
            filename=body.filename,
            duration=body.duration,
            s3_key=f"videos/{user_id}/{video_id}/{body.filename}",
        )
    except VideoAlreadyExists as exc:  # pragma: no cover - collision astronomically unlikely
        raise HTTPException(status_code=409, detail="video id collision, retry") from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    target = presigner.create_upload_target(
        user_id=user_id,
        video_id=video_id,
        filename=body.filename,
        content_type=body.content_type,
    )
    return CreateVideoResponse(
        video_id=record.video_id,
        user_id=record.user_id,
        status=record.status,
        upload=UploadTarget(**target),
    )


@router.get("", response_model=VideoListResponse, summary="List the acting user's videos")
def list_videos(
    repo: Annotated[VideoRepository, Depends(get_video_repository)],
    user_id: Annotated[str, Depends(user_id_header)],
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> VideoListResponse:
    """Return the acting user's videos newest-first.

    Args:
        repo: Video repository.
        user_id: Acting user from the identity dependency.
        limit: Page size ceiling.

    Returns:
        One page of videos.
    """
    items = repo.list_by_user(user_id, limit=limit)
    return VideoListResponse(items=[_to_response(r) for r in items], count=len(items))


@router.get("/{video_id}", response_model=VideoResponse, summary="Get one video")
def get_video(
    video_id: str,
    repo: Annotated[VideoRepository, Depends(get_video_repository)],
) -> VideoResponse:
    """Fetch one video by id.

    Args:
        video_id: Target video.
        repo: Video repository.

    Returns:
        The stored video.

    Raises:
        HTTPException: 404 when unknown.
    """
    record = repo.get(video_id)
    if record is None:
        raise HTTPException(status_code=404, detail="video not found")
    return _to_response(record)


@router.delete("/{video_id}", response_model=VideoResponse, summary="Soft-delete a video")
def delete_video(
    video_id: str,
    repo: Annotated[VideoRepository, Depends(get_video_repository)],
    user_id: Annotated[str, Depends(user_id_header)],
) -> VideoResponse:
    """Move a video to ``DELETED`` and record an audit event.

    Args:
        video_id: Target video.
        repo: Video repository.
        user_id: Acting user; must own the video.

    Returns:
        The deleted video record.

    Raises:
        HTTPException: 404 unknown, 403 non-owner, 409 invalid transition.
    """
    record = repo.get(video_id)
    if record is None:
        raise HTTPException(status_code=404, detail="video not found")
    if record.user_id != user_id:
        raise HTTPException(status_code=403, detail="not your video")
    try:
        updated = repo.soft_delete(video_id)
    except InvalidTransition as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    repo.append_event(video_id, "video.deleted", {"actor": user_id}, actor=user_id)
    return _to_response(updated)


def _to_response(record: VideoRecord) -> VideoResponse:
    """Convert a stored record into its API representation.

    Args:
        record: Stored video record.

    Returns:
        API response model.
    """
    return VideoResponse(
        video_id=record.video_id,
        user_id=record.user_id,
        filename=record.filename,
        duration=record.duration,
        status=record.status,
        created_at=record.created_at,
        updated_at=record.updated_at,
    )
