"""DynamoDB data model and repositories for Via.

Single-table design: one table (default name ``via``) stores video state,
audit events and analytics counters with typed key builders. Entities are
concrete Pydantic models - no generic entity abstraction.
"""

from via_db.analytics import AnalyticsRepository
from via_db.audit import AuditLog
from via_db.client import get_dynamodb_resource, get_table
from via_db.entities import ALLOWED_TRANSITIONS, AuditEvent, VideoRecord, VideoStatus
from via_db.errors import InvalidTransition, ViaDbError, VideoAlreadyExists, VideoNotFound
from via_db.tables import TABLE_DEFINITION, create_table
from via_db.videos import VideoRepository

__all__ = [
    "ALLOWED_TRANSITIONS",
    "TABLE_DEFINITION",
    "AnalyticsRepository",
    "AuditEvent",
    "AuditLog",
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
