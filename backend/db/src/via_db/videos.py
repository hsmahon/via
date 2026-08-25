"""Video repository: CRUD plus guarded lifecycle transitions."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any

from via_db.entities import ALLOWED_TRANSITIONS, VideoRecord, VideoStatus
from via_db.errors import InvalidTransition, VideoAlreadyExists, VideoNotFound
from via_db.keys import audit_sk, gsi1_pk, gsi1_sk, meta_sk, parse_video_pk, video_pk

if TYPE_CHECKING:  # pragma: no cover - typing only
    from mypy_boto3_dynamodb.service_resource import Table

__all__ = ["VideoRepository"]

_SAFE_FILENAME = re.compile(r"^[^/\\]{1,255}$")


class VideoRepository:
    """Data access for video records and their audit trails."""

    def __init__(self, table: Table) -> None:
        """Initialize the repository.

        Args:
            table: DynamoDB table handle (single-table layout).
        """
        self._table = table

    # ------------------------------------------------------------------
    # Commands
    # ------------------------------------------------------------------

    def create(
        self,
        *,
        video_id: str,
        user_id: str,
        filename: str,
        duration: float | None = None,
        s3_bucket: str | None = None,
        s3_key: str | None = None,
        file_size: int | None = None,
        content_type: str | None = None,
        status: VideoStatus = VideoStatus.UPLOADING,
    ) -> VideoRecord:
        """Create a new video record with a conditional put.

        Args:
            video_id: Fresh unique identifier.
            user_id: Owning user.
            filename: Original file name (path separators rejected).
            duration: Optional duration in seconds.
            s3_bucket: Bucket that will receive the upload.
            s3_key: Object key for the upload.
            file_size: Declared file size in bytes.
            content_type: Declared MIME type.
            status: Initial status; ``UPLOADING`` by convention.

        Returns:
            The stored record.

        Raises:
            ValueError: When the filename contains path separators.
            VideoAlreadyExists: On an id collision (extremely unlikely).
        """
        if not _SAFE_FILENAME.match(filename):
            raise ValueError(f"filename rejected: {filename!r}")
        now = VideoRecord.now_iso()
        record = VideoRecord(
            video_id=video_id,
            user_id=user_id,
            filename=filename,
            duration=duration,
            status=status,
            s3_bucket=s3_bucket,
            s3_key=s3_key,
            file_size=file_size,
            content_type=content_type,
            video_name=filename,
            upload_date=now,
            created_at=now,
            updated_at=now,
        )
        item = record.to_item()
        item.update(
            {
                "pk": video_pk(video_id),
                "sk": meta_sk(),
                "gsi1pk": gsi1_pk(user_id),
                "gsi1sk": gsi1_sk(now, video_id),
            }
        )
        try:
            self._table.put_item(Item=item, ConditionExpression="attribute_not_exists(pk)")
        except self._table.meta.client.exceptions.ConditionalCheckFailedException as exc:
            raise VideoAlreadyExists(video_id) from exc
        return record

    def update_status(
        self,
        video_id: str,
        to_status: VideoStatus,
        *,
        actor: str = "system",
        expected_current: set[VideoStatus] | None = None,
    ) -> VideoRecord:
        """Move a video to a new lifecycle state with race-safe guards.

        Validates against :data:`ALLOWED_TRANSITIONS`, then performs a
        conditional update so concurrent writers cannot interleave states.

        Args:
            video_id: Target video.
            to_status: Requested next status.
            actor: Identity performing the transition.
            expected_current: Optional narrowing of allowed source states.

        Returns:
            The updated record.

        Raises:
            VideoNotFound: Unknown video.
            InvalidTransition: Move not permitted by the lifecycle table.
        """
        current_record = self.get(video_id)
        if current_record is None:
            raise VideoNotFound(video_id)
        current = current_record.status
        if to_status not in ALLOWED_TRANSITIONS[current]:
            raise InvalidTransition(video_id, current, to_status)
        if expected_current is not None and current not in expected_current:
            raise InvalidTransition(video_id, current, to_status)

        now = VideoRecord.now_iso()
        try:
            response = self._table.update_item(
                Key={"pk": video_pk(video_id), "sk": meta_sk()},
                UpdateExpression="SET #s = :to, #u = :now",
                ConditionExpression="#s = :cur",
                ExpressionAttributeNames={"#s": "status", "#u": "updated_at"},
                ExpressionAttributeValues={
                    ":to": to_status.value,
                    ":now": now,
                    ":cur": current.value,
                },
                ReturnValues="ALL_NEW",
            )
        except self._table.meta.client.exceptions.ConditionalCheckFailedException as exc:
            raise InvalidTransition(video_id, current, to_status) from exc
        item = dict(response["Attributes"])
        item["video_id"] = video_id
        _ = actor
        return VideoRecord.from_item(item)

    def soft_delete(self, video_id: str) -> VideoRecord:
        """Soft-delete a video by moving it to the DELETED state.

        Args:
            video_id: Target video.

        Returns:
            The updated record with status ``DELETED``.

        Raises:
            VideoNotFound: Unknown video.
            InvalidTransition: Already deleted or otherwise disallowed.
        """
        return self.update_status(video_id, VideoStatus.DELETED)

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def get(self, video_id: str) -> VideoRecord | None:
        """Fetch one video's current state.

        Args:
            video_id: Target video.

        Returns:
            The record, or ``None`` when absent.
        """
        response = self._table.get_item(Key={"pk": video_pk(video_id), "sk": meta_sk()})
        item = response.get("Item")
        return VideoRecord.from_item(dict(item)) if item else None

    def list_by_user(self, user_id: str, *, limit: int = 20) -> list[VideoRecord]:
        """List a user's videos newest-first through GSI ``gsi1``.

        Args:
            user_id: Owner identifier.
            limit: Page size ceiling (clamped to DynamoDB maximum).

        Returns:
            Records ordered newest-first.
        """
        clamped = max(1, min(limit, 100))
        response = self._table.query(
            IndexName="gsi1",
            KeyConditionExpression="#p = :u",
            ExpressionAttributeNames={"#p": "gsi1pk"},
            ExpressionAttributeValues={":u": gsi1_pk(user_id)},
            ScanIndexForward=False,
            Limit=clamped,
        )
        records: list[VideoRecord] = []
        for raw in response.get("Items", []):
            item = dict(raw)
            item["video_id"] = parse_video_pk(str(item.get("pk", "")))
            records.append(VideoRecord.from_item(item))
        return records

    def count_by_user(self, user_id: str) -> int:
        """Count how many videos a user owns (for quota checks).

        Args:
            user_id: Owner identifier.

        Returns:
            Number of ``META`` items owned by the user (up to quota scale).

        Note:
            Implemented as a ``Select=COUNT`` query over ``gsi1`` so small
            quotas stay cheap even without a separate counter item.
        """
        response = self._table.query(
            IndexName="gsi1",
            KeyConditionExpression="#p = :u",
            ExpressionAttributeNames={"#p": "gsi1pk"},
            ExpressionAttributeValues={":u": gsi1_pk(user_id)},
            Select="COUNT",
        )
        return int(response.get("Count", 0))

    def append_event(
        self, video_id: str, event_type: str, payload: dict[str, Any], *, actor: str = "system"
    ) -> None:
        """Append one audit event under the video's partition.

        Args:
            video_id: Owning video.
            event_type: Dotted event name.
            payload: JSON-safe structured details.
            actor: Identity causing the event.
        """
        from via_db.entities import AuditEvent

        event = AuditEvent(event_type=event_type, payload=payload, actor=actor)
        self._table.put_item(
            Item={"pk": video_pk(video_id), "sk": audit_sk(event.occurred_at), **event.to_item()}
        )
