"""Concrete DynamoDB key layout for the single Via table.

v0.1 persistence is intentionally minimal: one table ``via-table`` holding
only video metadata plus a single GSI for the ``GET /videos`` access pattern.

======== ========== ===========================
PK       SK         Item
======== ========== ===========================
video_id user_id    VideoRecord (see :mod:`via_db.entities`)
======== ========== ===========================

GSI ``gsi1`` (``GSI1PK=user_id`` → ``GSI1SK=<created_at>#<video_id>``) supports
"list a user's videos, newest first" without a table Scan.
"""

from __future__ import annotations

__all__ = [
    "gsi1_pk",
    "gsi1_sk",
    "meta_sk",
    "parse_video_pk",
    "video_pk",
]


def video_pk(video_id: str) -> str:
    """Build the partition key for a video's item.

    In v0.1 this is the raw video id (the table's PK is the video's own
    identity). Retains the ``VIDEO#`` prefix convention so existing tests and
    Terraform state carry over without a migration.

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
