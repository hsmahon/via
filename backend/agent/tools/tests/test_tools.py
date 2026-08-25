"""Tests for Via's initial tool implementations."""

from __future__ import annotations

from via_harness import AuthorizationContext, Permission, ToolStatus


class TestDefaultRegistry:
    """The default tool set and its behaviors."""

    def test_registers_three_tools_in_order(self) -> None:
        """All three initial tools are present in stable order."""
        from via_tools import build_default_registry

        registry = build_default_registry()
        names = [t.contract.name for t in registry.get_tools(_full_authz())]
        assert names == ["get_video_metadata", "get_transcript", "analyze_video"]

    def test_metadata_tool_reports_found(self, authz: AuthorizationContext) -> None:
        """A wired fetcher returns the video snapshot."""
        from via_tools import build_default_registry

        registry = build_default_registry(
            fetch_metadata=lambda vid: {
                "video_id": vid,
                "filename": "a.mp4",
                "status": "PROCESSED",
                "duration": 8.0,
            }
        )
        result = registry.get_tool("get_video_metadata").execute(
            video_id="v1", authz=authz, arguments={}
        )  # type: ignore[union-attr]
        assert result.status is ToolStatus.OK
        assert result.payload is not None
        assert result.payload["found"] is True
        assert result.payload["video"]["filename"] == "a.mp4"

    def test_metadata_tool_handles_missing_video(self, authz: AuthorizationContext) -> None:
        """Unknown videos return found=False rather than erroring."""
        from via_tools import build_default_registry

        registry = build_default_registry(fetch_metadata=lambda _vid: None)
        result = registry.get_tool("get_video_metadata").execute(
            video_id="missing", authz=authz, arguments={}
        )  # type: ignore[union-attr]
        assert result.payload is not None
        assert result.payload["found"] is False

    def test_pending_integrations_report_unavailable(self, authz: AuthorizationContext) -> None:
        """Transcript and analysis tools signal their pending integrations."""
        from via_tools import build_default_registry

        registry = build_default_registry()
        for name in ("get_transcript", "analyze_video"):
            tool = registry.get_tool(name)
            assert tool is not None
            args = {"question": "what?"} if name == "analyze_video" else {}
            result = tool.execute(video_id="v1", authz=authz, arguments=args)
            assert result.status is ToolStatus.UNAVAILABLE
            assert result.detail


def _full_authz() -> AuthorizationContext:
    """Build a fully-permitted authorization context.

    Returns:
        Context granting every harness permission.
    """
    return AuthorizationContext(
        user_id="u",
        video_id="v",
        permissions=frozenset(
            {Permission.VIDEO_READ, Permission.TRANSCRIPT_READ, Permission.VIDEO_ANALYZE}
        ),
    )
