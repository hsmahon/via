"""Typed entities and the explicit video lifecycle state machine."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any, cast

from pydantic import BaseModel, ConfigDict, Field

__all__ = ["ALLOWED_TRANSITIONS", "AuditEvent", "VideoRecord", "VideoStatus"]


def _to_decimal(value: Any) -> Any:
    """Convert floats to Decimal for DynamoDB storage.

    Args:
        value: Arbitrary JSON-safe structure.

    Returns:
        Structure with every float replaced by ``Decimal``.
    """
    if isinstance(value, float):
        return Decimal(str(value))
    if isinstance(value, dict):
        return {k: _to_decimal(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_to_decimal(v) for v in value]
    return value


def _from_decimal(value: Any) -> Any:
    """Convert Decimals back into JSON-safe numbers.

    Args:
        value: Structure returned by DynamoDB.

    Returns:
        Structure with ``Decimal`` replaced by int/float.
    """
    if isinstance(value, Decimal):
        number = float(value)
        return int(number) if number.is_integer() and abs(number) < 1e15 else number
    if isinstance(value, dict):
        return {k: _from_decimal(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_from_decimal(v) for v in value]
    return value


class VideoStatus(StrEnum):
    """Lifecycle states of a video.

    ``UPLOADING``  - upload session created, bytes not yet fully received.
    ``PROCESSING`` - worker accepted the object-created event.
    ``PROCESSED``  - pipeline finished (transcripts/artifacts ready).
    ``FAILED``     - terminal failure; retry flows arrive later.
    ``DELETED``    - soft-deleted; metadata retained for auditability.
    """

    UPLOADING = "UPLOADING"
    PROCESSING = "PROCESSING"
    PROCESSED = "PROCESSED"
    FAILED = "FAILED"
    DELETED = "DELETED"


#: Explicit transition table. Anything absent is rejected at runtime.
ALLOWED_TRANSITIONS: dict[VideoStatus, frozenset[VideoStatus]] = {
    VideoStatus.UPLOADING: frozenset(
        {VideoStatus.PROCESSING, VideoStatus.FAILED, VideoStatus.DELETED}
    ),
    VideoStatus.PROCESSING: frozenset({VideoStatus.PROCESSED, VideoStatus.FAILED}),
    VideoStatus.PROCESSED: frozenset({VideoStatus.DELETED}),
    VideoStatus.FAILED: frozenset({VideoStatus.DELETED}),
    VideoStatus.DELETED: frozenset(),
}


class VideoRecord(BaseModel):
    """Current state of one uploaded video.

    Attributes:
        video_id: Unique identifier (ULID-style string).
        user_id: Owning user.
        filename: Original file name as uploaded.
        duration: Media duration in seconds, when known.
        status: Current lifecycle state.
        s3_bucket: Bucket holding the object.
        s3_key: Object key inside the bucket.
        file_size: Declared upload size in bytes, when known.
        content_type: MIME type declared at creation, when known.
        video_name: Legacy alias for filename (mirrors ``filename`` when set).
        upload_date: Legacy alias for created_at (ISO-8601 UTC).
        created_at: ISO-8601 UTC creation timestamp.
        updated_at: ISO-8601 UTC last-update timestamp.
    """

    model_config = ConfigDict(frozen=True)

    video_id: str = Field(min_length=1)
    user_id: str = Field(min_length=1)
    filename: str = Field(min_length=1, max_length=255)
    duration: float | None = Field(default=None, gt=0.0)
    status: VideoStatus
    s3_bucket: str | None = None
    s3_key: str | None = None
    file_size: int | None = Field(default=None, ge=0, description="Declared file size in bytes.")
    content_type: str | None = Field(default=None, max_length=100, description="MIME type.")
    video_name: str | None = Field(
        default=None, max_length=255, description="Legacy alias for filename."
    )
    upload_date: str | None = Field(
        default=None, description="Legacy alias for created_at (ISO-8601 UTC)."
    )
    created_at: str
    updated_at: str

    def to_item(self) -> dict[str, Any]:
        """Serialize into a DynamoDB item.

        Returns:
            DynamoDB-safe dictionary (floats encoded as ``Decimal``).
        """
        item = self.model_dump(mode="json")
        item["status"] = self.status.value
        return cast("dict[str, Any]", _to_decimal(item))

    @classmethod
    def from_item(cls, item: dict[str, Any]) -> VideoRecord:
        """Rebuild a record from a stored DynamoDB item.

        Args:
            item: Raw item dictionary (may contain ``Decimal`` values).

        Returns:
            Parsed :class:`VideoRecord`.

        Raises:
            ValidationError: When stored data does not match the schema.
        """
        return cls.model_validate(_from_decimal(item))

    @staticmethod
    def now_iso() -> str:
        """Return the current UTC time in ISO-8601 format.

        Returns:
            Timestamp string with microsecond precision.
        """
        return datetime.now(UTC).isoformat()


class AuditEvent(BaseModel):
    """Append-only event recorded on a video's audit trail."""

    model_config = ConfigDict(frozen=True)

    event_type: str = Field(
        min_length=1, description="Dotted event name such as 'video.status_changed'."
    )
    occurred_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    actor: str = Field(default="system", description="Identity that caused the event.")
    payload: dict[str, Any] = Field(default_factory=dict)

    def to_item(self) -> dict[str, Any]:
        """Serialize into a DynamoDB item.

        Returns:
            DynamoDB-safe dictionary of the event.
        """
        return cast("dict[str, Any]", _to_decimal(self.model_dump(mode="json")))
