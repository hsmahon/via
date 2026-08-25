"""Video lifecycle routes."""

from __future__ import annotations

import logging
from typing import Annotated

from botocore.exceptions import BotoCoreError, ClientError
from fastapi import APIRouter, Depends, HTTPException, Query, status
from via_db import (
    InvalidTransition,
    VideoRecord,
    VideoRepository,
)

from via_api.deps import get_presigner, get_settings, get_video_repository, user_id_header
from via_api.schemas import (
    CreateVideoRequest,
    CreateVideoResponse,
    UploadTarget,
    VideoListResponse,
    VideoResponse,
)
from via_api.services.videos import create_video_record
from via_api.settings import Settings
from via_api.storage import Presigner

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/videos", tags=["videos"])


@router.post(
    "",
    response_model=CreateVideoResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Accept a video for upload",
)
def create_video(
    body: CreateVideoRequest,
    repo: Annotated[VideoRepository, Depends(get_video_repository)],
    presigner: Annotated[Presigner, Depends(get_presigner)],
    settings: Annotated[Settings, Depends(get_settings)],
    user_id: Annotated[str, Depends(user_id_header)],
) -> CreateVideoResponse:
    """Create a video record in ``UPLOADING`` and return its opaque id.

    The body is validated by Pydantic, media type against the allow-list
    and quota before any write. The row is inserted with
    ``ConditionExpression=attribute_not_exists(pk)`` so a video_id collision
    never silently overwrites an existing item.

    In this slice the HTTP transaction ends after the conditional write.
    Bytes are **not** proxied through the API, so the minimal response is
    ``{video_id, status}``; a short-lived presigned PUT target is attached
    when the deployment is configured to issue one.

    Args:
        body: Validated creation payload.
        repo: Video repository.
        presigner: S3 presigned-URL issuer.
        settings: Application settings (quota + bucket).
        user_id: Acting user from the identity dependency.

    Returns:
        Acceptance payload carrying the server-generated video_id.

    Raises:
        HTTPException: 400/409/415/500 mapped from service and storage errors.
    """
    # Fail-fast for empty alias without touching domain logic.
    if not body.resolved_filename:
        raise HTTPException(status_code=400, detail="filename (or video_name) is required")

    try:
        record, _s3_key = create_video_record(
            body=body,
            repo=repo,
            user_id=user_id,
            settings=settings,
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("video create failed (DynamoDB path)")
        raise HTTPException(status_code=500, detail="internal error") from exc

    filename = body.resolved_filename
    try:
        target = presigner.create_upload_target(
            user_id=user_id,
            video_id=record.video_id,
            filename=filename,
            content_type=body.content_type,
        )
    except (ClientError, BotoCoreError, Exception) as exc:
        logger.exception("presign failed after successful DynamoDB write")
        raise HTTPException(status_code=500, detail="failed to issue upload target") from exc

    upload = UploadTarget(**target) if target else None
    return CreateVideoResponse(
        video_id=record.video_id,
        user_id=record.user_id,
        status=record.status,
        upload=upload,
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
    """Move a video to ``DELETED``.

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
