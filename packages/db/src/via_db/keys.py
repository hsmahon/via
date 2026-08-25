"""Concrete DynamoDB key layout for the single Via table.

Key schema (deliberately explicit - no generic entity framework):

===== ======== =========================================
PK    SK       Item
===== ======== =========================================
VIDEO#<id>  META     VideoRecord (current state)
VIDEO#<id>  AUDIT#<ts>  AuditEvent (append-only)
ANALYTICS#<scope>  COUNTER#<name>  monotonically increasing counter
===== ======== =========================================

GSI ``gsi1`` (USER#<user_id> → <created_at>#<video_id>) supports
"list a user's videos, newest first".
"""

from __future__ import annotations

__all__ = [
    "analytics_pk",
    "audit_sk",
    "counter_sk",
    "gsi1_pk",
    "gsi1_sk",
    "meta_sk",
    "parse_video_pk",
    "video_pk",
]


def video_pk(video_id: str) -> str:
    """Build the partition key for all items of one video.

    Args:
        video_id: Video identifier.

    Returns:
        Partition key string ``VIDEO#<id>``.
    """
    return f"VIDEO#{video_id}"


def meta_sk() -> str:
    """Build the sort key of a video's metadata item.

    Returns:
        Constant string ``META``.
    """
    return "META"


def audit_sk(occurred_at: str) -> str:
    """Build the sort key for an audit event.

    Args:
        occurred_at: ISO-8601 UTC timestamp with microsecond precision.

    Returns:
        Sort key ``AUDIT#<occurred_at>``.
    """
    return f"AUDIT#{occurred_at}"


def analytics_pk(scope: str) -> str:
    """Build the partition key for one analytics scope.

    Args:
        scope: Scope identifier such as ``GLOBAL`` or ``USER#<id>``.

    Returns:
        Partition key string ``ANALYTICS#<scope>``.
    """
    return f"ANALYTICS#{scope}"


def counter_sk(name: str) -> str:
    """Build the sort key for one named counter.

    Args:
        name: Counter name such as ``videos_uploaded``.

    Returns:
        Sort key ``COUNTER#<name>``.
    """
    return f"COUNTER#{name}"


def gsi1_pk(user_id: str) -> str:
    """Build the GSI partition key grouping a user's videos.

    Args:
        user_id: Owner identifier.

    Returns:
        GSI partition key ``USER#<id>``.
    """
    return f"USER#{user_id}"


def gsi1_sk(created_at: str, video_id: str) -> str:
    """Build the GSI sort key ordering videos newest-first.

    Args:
        created_at: ISO-8601 creation timestamp.
        video_id: Video identifier ensuring uniqueness within a timestamp.

    Returns:
        GSI sort key ``<created_at>#<video_id>``.
    """
    return f"{created_at}#{video_id}"


def parse_video_pk(pk: str) -> str:
    """Extract the video id from a partition key.

    Args:
        pk: Partition key of the form ``VIDEO#<id>``.

    Returns:
        The video identifier portion.

    Raises:
        ValueError: If the key does not follow the expected format.
    """
    prefix = "VIDEO#"
    if not pk.startswith(prefix):
        raise ValueError(f"not a video partition key: {pk!r}")
    return pk[len(prefix) :]
