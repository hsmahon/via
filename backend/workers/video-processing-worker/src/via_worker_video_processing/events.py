"""EventBridge event parsing for the video-processing worker.

Production path is ``S3 → EventBridge → VIA Worker → DynamoDB``.
The worker validates the EventBridge envelope directly — no MinIO
normalization layer.

Expected shape (AWS S3 via EventBridge):

    {
        "source": "aws.s3",
        "detail-type": "Object Created",
        "detail": {
            "bucket": {"name": "via-videos"},
            "object": {"key": "videos/<user>/<video>/<file>", "size": 123}
        }
    }

Both the native ``detail.bucket.name / detail.object.key`` nesting and
the flattened ``detail.bucket (str) / detail.key`` variants are accepted
so synthetic events and tests remain ergonomic. Keys are percent-decoded.
"""

from __future__ import annotations

from typing import Any
from urllib.parse import unquote

from pydantic import BaseModel, Field, ValidationError

__all__ = ["EventBridgeEvent", "EventDetail", "parse_eventbridge_event", "parse_video_id"]


class EventDetail(BaseModel):
    """Canonical detail payload for an S3 Object Created event."""

    bucket: str
    key: str
    size: int | None = None


class EventBridgeEvent(BaseModel):
    """Validated EventBridge S3 Object Created event."""

    source: str = "aws.s3"
    detail_type: str = Field(default="Object Created", alias="detail-type")
    detail: EventDetail

    model_config = {"populate_by_name": True}

    def parse_video_id(self) -> str | None:
        """Extract the video id from the object key layout.

        Expected key: ``videos/<user_id>/<video_id>/<filename>``.

        Returns:
            The video id segment, or None when the key doesn't match.
        """
        return parse_video_id(self.detail.key)


def parse_video_id(key: str) -> str | None:
    """Extract video id from an S3 object key.

    Args:
        key: S3 object key.

    Returns:
        Video id when the key matches ``videos/<user>/<video>/<file>``,
        otherwise None.
    """
    parts = key.split("/")
    if len(parts) >= 3 and parts[0] == "videos":
        return parts[2] or None
    return None


def _bucket_name(detail: dict[str, Any]) -> str | None:
    """Extract bucket name from either nesting convention.

    Args:
        detail: EventBridge detail object.

    Returns:
        Bucket name when present.
    """
    bucket = detail.get("bucket")
    if isinstance(bucket, dict):
        return bucket.get("name")
    return str(bucket) if bucket is not None else None


def _object_fields(detail: dict[str, Any]) -> tuple[str | None, int | None]:
    """Extract key and size from either nesting convention.

    Args:
        detail: EventBridge detail object.

    Returns:
        Tuple of (key, size).
    """
    obj = detail.get("object")
    if isinstance(obj, dict):
        size = obj.get("size")
        raw_key = obj.get("key")
        return unquote(str(raw_key)) if raw_key is not None else None, int(
            size
        ) if size is not None else None
    size = detail.get("size")
    raw_key = detail.get("key")
    return (unquote(str(raw_key)) if raw_key is not None else None), int(
        size
    ) if size is not None else None


def parse_eventbridge_event(payload: dict[str, Any]) -> EventBridgeEvent:
    """Validate an EventBridge S3 Object Created payload.

    Args:
        payload: Raw event JSON dictionary.

    Returns:
        Validated :class:`EventBridgeEvent`.

    Raises:
        ValueError: When the payload does not match the expected
            EventBridge shape or required fields are missing.
    """
    if "detail" not in payload:
        raise ValueError(
            f"unrecognized eventbridge payload: missing 'detail'; keys={sorted(payload)}"
        )
    raw_detail = payload.get("detail")
    if not isinstance(raw_detail, dict):
        raise ValueError("detail must be an object")
    # Optionally enforce detail-type and source when present.
    detail_type = payload.get("detail-type")
    if detail_type is not None and detail_type != "Object Created":
        raise ValueError(f"unexpected detail-type: {detail_type!r}")
    source = payload.get("source")
    if source is not None and source != "aws.s3":
        raise ValueError(f"unexpected source: {source!r}")

    try:
        key, size = _object_fields(raw_detail)
        bucket = _bucket_name(raw_detail)
        if not bucket or not key:
            raise ValueError(f"missing bucket or key; detail={raw_detail}")
        event = EventBridgeEvent(
            source=str(source) if source is not None else "aws.s3",
            **{"detail-type": str(detail_type) if detail_type is not None else "Object Created"},
            detail=EventDetail(bucket=str(bucket), key=str(key), size=size),
        )
        return event
    except (ValidationError, TypeError, ValueError) as exc:
        raise ValueError(f"unrecognized eventbridge payload: {exc}") from exc
