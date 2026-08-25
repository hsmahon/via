"""DynamoDB data model and repositories for Via.

Single-table design: one table (``via-table`` contract) stores video state
with typed key builders. The only secondary access pattern is the
user-videos GSI (``USER#<user_id>`` → ``<created_at>#<video_id>``).
Entities are concrete Pydantic models — no generic entity abstraction.
"""

from via_db.client import get_dynamodb_resource, get_table
from via_db.entities import ALLOWED_TRANSITIONS, VideoRecord, VideoStatus
from via_db.errors import InvalidTransition, ViaDbError, VideoAlreadyExists, VideoNotFound
from via_db.tables import TABLE_DEFINITION, create_table
from via_db.videos import VideoRepository

__all__ = [
    "ALLOWED_TRANSITIONS",
    "TABLE_DEFINITION",
    "InvalidTransition",
    "ViaDbError",
    "VideoAlreadyExists",
    "VideoNotFound",
    "VideoRecord",
    "VideoRepository",
    "VideoStatus",
    "create_table",
    "get_dynamodb_resource",
    "get_table",
]
