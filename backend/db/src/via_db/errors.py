"""Repository-level error types."""

from __future__ import annotations

from via_db.entities import VideoStatus

__all__ = ["InvalidTransition", "ViaDbError", "VideoAlreadyExists", "VideoNotFound"]


class ViaDbError(Exception):
    """Base class for data-layer failures."""


class VideoNotFound(ViaDbError):
    """The requested video does not exist."""


class VideoAlreadyExists(ViaDbError):
    """A video with the same identifier was already created."""


class InvalidTransition(ViaDbError):
    """A status change outside the explicit lifecycle table was attempted."""

    def __init__(self, video_id: str, current: VideoStatus, requested: VideoStatus) -> None:
        """Initialize the transition error.

        Args:
            video_id: Video whose state change was rejected.
            current: Status the video actually had.
            requested: Status the caller tried to move to.
        """
        super().__init__(
            f"invalid status transition for {video_id}: {current.value} -> {requested.value}"
        )
        self.video_id = video_id
        self.current = current
        self.requested = requested
