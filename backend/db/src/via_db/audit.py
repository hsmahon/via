"""Audit trail queries (append handled by :class:`VideoRepository`)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from via_db.keys import video_pk

if TYPE_CHECKING:  # pragma: no cover - typing only
    from mypy_boto3_dynamodb.service_resource import Table

__all__ = ["AuditLog"]


class AuditLog:
    """Read-side access to a video's append-only audit events."""

    def __init__(self, table: Table) -> None:
        """Initialize the log.

        Args:
            table: DynamoDB table handle.
        """
        self._table = table

    def list_for_video(self, video_id: str, *, limit: int = 50) -> list[dict[str, Any]]:
        """Return audit events for one video, newest first.

        Args:
            video_id: Owning video.
            limit: Maximum number of events.

        Returns:
            Raw event items ordered newest-first.
        """
        response = self._table.query(
            KeyConditionExpression="#p = :v AND begins_with(#s, :prefix)",
            ExpressionAttributeNames={"#p": "pk", "#s": "sk"},
            ExpressionAttributeValues={":v": video_pk(video_id), ":prefix": "AUDIT#"},
            ScanIndexForward=False,
            Limit=max(1, min(limit, 100)),
        )
        return [dict(item) for item in response.get("Items", [])]
