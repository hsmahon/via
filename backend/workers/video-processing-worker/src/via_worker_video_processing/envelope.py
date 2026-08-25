"""Event envelope models and normalization.

The canonical wire format is the EventBridge envelope used in production:

    {"source": "aws.s3", "detail-type": "Object Created", "detail": {...}}

MinIO webhooks carry a different shape locally; ``normalize`` maps both
onto one internal model so handlers never branch on environment.
"""

from __future__ import annotations

from typing import Any
from urllib.parse import unquote

from pydantic import BaseModel, Field, ValidationError

__all__ = ["EventEnvelope", "normalize_event"]


class EventDetail(BaseModel):
    """Canonical detail payload for object-created events."""

    bucket: str
    key: str
    size: int | None = None


class EventEnvelope(BaseModel):
    """Internal representation of a lifecycle event."""

    source: str = "via.local"
    event_type: str = Field(default="Object Created")
    detail: EventDetail

    def parse_video_id(self) -> str | None:
        """Extract the video id from the object key layout.

        Expected key: ``videos/<user_id>/<video_id>/<filename>``.

        Returns:
            The video id segment, or None when the key doesn't match.
        """
        parts = self.detail.key.split("/")
        if len(parts) >= 3 and parts[0] == "videos":
            return parts[2] or None
        return None


def _bucket_name(detail: dict[str, Any]) -> str | None:
    """Extract the bucket name from either nesting convention.

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


def normalize_event(payload: dict[str, Any]) -> EventEnvelope:
    """Map EventBridge or MinIO payloads onto the canonical envelope.

    Accepts both the native S3 notification layout
    (``detail.bucket.name`` / ``detail.object.key``) and flattened variants
    (``detail.bucket`` / ``detail.key``).

    Args:
        payload: Raw webhook/event JSON dictionary.

    Returns:
        Canonical :class:`EventEnvelope`.

    Raises:
        ValueError: When neither recognized shape can be parsed.
    """
    # Production: EventBridge S3 notification.
    if "detail-type" in payload or "detail" in payload:
        try:
            raw_detail = payload.get("detail") or {}
            if not isinstance(raw_detail, dict):
                raise ValueError("detail must be an object")
            key, size = _object_fields(raw_detail)
            bucket = _bucket_name(raw_detail)
            return EventEnvelope(
                source=str(payload.get("source", "aws.s3")),
                event_type=str(payload.get("detail-type", "Object Created")),
                detail=EventDetail(bucket=str(bucket), key=str(key), size=size),
            )
        except (ValidationError, TypeError, ValueError) as exc:
            raise ValueError(f"unrecognized eventbridge payload: {exc}") from exc
    # Local: MinIO bucket notification (array form).
    records = payload.get("Records")
    if records:
        record = records[0]
        try:
            s3 = record["s3"]
            size = s3["object"].get("size")
            return EventEnvelope(
                source="minio.s3",
                event_type=str(record.get("eventName", "s3:ObjectCreated")),
                detail=EventDetail(
                    bucket=str(s3["bucket"]["name"]),
                    key=unquote(str(s3["object"]["key"])),
                    size=int(size) if size is not None else None,
                ),
            )
        except (KeyError, TypeError, ValidationError, ValueError) as exc:
            raise ValueError(f"unrecognized minio payload: {exc}") from exc
    # Local: MinIO webhook flat form ({"EventName": ..., "Key": ...}).
    if "EventName" in payload and "Key" in payload:
        try:
            return EventEnvelope(
                source="minio.s3",
                event_type=str(payload["EventName"]),
                detail=EventDetail(
                    bucket=str(payload.get("Bucket", "")),
                    key=unquote(str(payload["Key"])),
                    size=payload.get("Size"),
                ),
            )
        except (ValidationError, TypeError, ValueError) as exc:
            raise ValueError(f"unrecognized minio payload: {exc}") from exc
    raise ValueError(
        f"payload matches neither EventBridge nor MinIO notification shapes; keys={sorted(payload)}"
    )
