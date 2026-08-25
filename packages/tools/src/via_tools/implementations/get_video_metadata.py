"""``get_video_metadata`` - real implementation backed by application state.

The tool never receives user-controlled video ids: it operates on the
``video_id`` carried in the authorized context, and ownership has already
been enforced by the harness policy layer before execution.
"""

from __future__ import annotations

from typing import Any, Protocol

from pydantic import BaseModel
from via_harness import AuthorizationContext, ToolContract, ToolResult, ToolStatus
from via_harness.context import Permission

__all__ = [
    "GetVideoMetadataTool",
    "MetadataFetcher",
    "MetadataInput",
    "MetadataOutput",
    "VideoSnapshot",
]


class MetadataFetcher(Protocol):
    """Port the application wires in to supply stored video metadata."""

    def __call__(self, video_id: str) -> dict[str, Any] | None:
        """Fetch metadata for one video.

        Args:
            video_id: Video identifier.

        Returns:
            Metadata dictionary, or ``None`` when the video is unknown.
        """
        ...


class MetadataInput(BaseModel):
    """Arguments for ``get_video_metadata`` (none required)."""


class VideoSnapshot(BaseModel):
    """Video fields exposed to models."""

    video_id: str
    filename: str
    status: str
    duration: float | None = None
    created_at: str | None = None
    updated_at: str | None = None


class MetadataOutput(BaseModel):
    """Payload returned by a successful metadata lookup."""

    found: bool
    video: VideoSnapshot | None = None


class GetVideoMetadataTool:
    """Answers "what is this video?" from application state."""

    contract = ToolContract(
        name="get_video_metadata",
        description="Return stored metadata for the current video (filename, duration, processing status, timestamps).",
        input_model=MetadataInput,
        output_model=MetadataOutput,
        required_permissions=frozenset({Permission.VIDEO_READ}),
        timeout_seconds=5.0,
        owner="via-agent-platform",
    )

    def __init__(self, fetcher: MetadataFetcher | None = None) -> None:
        """Initialize the tool.

        Args:
            fetcher: Application-provided lookup; when ``None`` the tool
                reports itself unavailable instead of failing.
        """
        self._fetcher = fetcher

    def execute(
        self, *, video_id: str, authz: AuthorizationContext, arguments: dict[str, Any]
    ) -> ToolResult:
        """Fetch and normalize metadata for the authorized video.

        Args:
            video_id: Target video from the authorized context.
            authz: Caller context (unused beyond signature conformance).
            arguments: Validated empty arguments.

        Returns:
            Ok result with the snapshot, or unavailable when no store is
            wired or the video is missing.
        """
        _ = authz
        if self._fetcher is None:
            return ToolResult(
                status=ToolStatus.UNAVAILABLE,
                detail="metadata store is not wired into this deployment",
            )
        raw = self._fetcher(video_id)
        if raw is None:
            return ToolResult(
                status=ToolStatus.OK, payload=MetadataOutput(found=False).model_dump(mode="json")
            )
        snapshot = VideoSnapshot(
            video_id=str(raw.get("video_id", video_id)),
            filename=str(raw.get("filename", "")),
            status=str(raw.get("status", "")),
            duration=raw.get("duration"),
            created_at=raw.get("created_at"),
            updated_at=raw.get("updated_at"),
        )
        output = MetadataOutput(found=True, video=snapshot)
        return ToolResult(status=ToolStatus.OK, payload=output.model_dump(mode="json"))
