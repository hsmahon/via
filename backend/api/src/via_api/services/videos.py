"""Business rules for video creation (Vertical Slice #1).

Keeps the HTTP layer thin: validation that cannot be expressed in the schema,
quota enforcement, and the ordered construction of the DynamoDB write.

Ultra-thin wrapper around :meth:`VideoRepository.create` so the route
stays declarative and all non-trivial checks remain testable without FastAPI.
"""

from __future__ import annotations

import uuid

from fastapi import HTTPException
from via_db import VideoAlreadyExists, VideoRecord, VideoRepository, VideoStatus

from via_api.schemas import CreateVideoRequest
from via_api.settings import Settings


def _validate_media_type(body: CreateVideoRequest, settings: Settings) -> None:
    """Reject unsupported MIME types with 415.

    Args:
        body: Validated request payload.
        settings: Application settings (allow-list).

    Raises:
        HTTPException: 415 when the MIME type is not in the configured set.
    """
    allowed = settings.allowed_content_type_set
    if not allowed or not body.content_type:
        return
    normalized = body.content_type.strip().lower()
    if normalized not in allowed:
        raise HTTPException(status_code=415, detail=f"unsupported media type: {body.content_type}")


def _enforce_quota(repo: VideoRepository, user_id: str, settings: Settings) -> None:
    """Reject writes once the user's quota is exhausted (409).

    Args:
        repo: Video repository for counting.
        user_id: Acting user.
        settings: Application settings (quota cap).

    Raises:
        HTTPException: 409 when the cap has been reached.

    Note:
        A bounded ``Select=COUNT`` over GSI ``gsi1`` is cheaper than full
        scans and sufficient for the small quotas in v0.
    """
    limit = settings.max_videos_per_user
    if limit <= 0:
        return
    owned = repo.count_by_user(user_id)
    if owned >= limit:
        raise HTTPException(
            status_code=409,
            detail=f"video quota exceeded ({owned}/{limit})",
        )


def create_video_record(
    *,
    body: CreateVideoRequest,
    repo: VideoRepository,
    user_id: str,
    settings: Settings,
) -> tuple[VideoRecord, str]:
    """Create a DynamoDB record for a new upload.

    Args:
        body: Validated request payload.
        repo: Video repository (moto or real DynamoDB).
        user_id: Resolved owner.
        settings: Application settings (quota, allow-list, bucket name).

    Returns:
        ``(record, s3_key)`` where ``s3_key`` is the placeholder path that
        will hold the bytes when a presigned upload is issued.

    Raises:
        HTTPException: 400 for missing/invalid filename, 415 for
            unsupported media type, 409 for quota or id collision, 422 for
            domain validation failures.
    """
    filename = body.resolved_filename
    if not filename:
        raise HTTPException(status_code=400, detail="filename (or video_name) is required")
    duration = body.duration
    file_size = body.file_size
    content_type = body.content_type.strip() if body.content_type else None

    _validate_media_type(body, settings)
    _enforce_quota(repo, user_id, settings)

    video_id = uuid.uuid4().hex
    s3_key = f"videos/{user_id}/{video_id}/{filename}"

    try:
        record = repo.create(
            video_id=video_id,
            user_id=user_id,
            filename=filename,
            duration=duration,
            file_size=file_size,
            content_type=content_type,
            s3_key=s3_key,
            s3_bucket=settings.bucket,
            status=VideoStatus.UPLOADING,
        )
    except ValueError as exc:
        # Distinguish repository-level filename errors (400) from
        # generic validation (422) so callers obey the spec's 400 contract.
        msg = str(exc).lower()
        if "filename" in msg:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except VideoAlreadyExists as exc:  # pragma: no cover - astronomically unlikely
        raise HTTPException(status_code=409, detail="video id collision, retry") from exc

    return record, s3_key
