"""Registry factory wiring Via's default tool set."""

from __future__ import annotations

from via_harness import InProcessToolRegistry

from via_tools.implementations.analyze_video import AnalyzeVideoTool
from via_tools.implementations.get_transcript import GetTranscriptTool
from via_tools.implementations.get_video_metadata import GetVideoMetadataTool, MetadataFetcher

__all__ = ["build_default_registry"]


def build_default_registry(fetch_metadata: MetadataFetcher | None = None) -> InProcessToolRegistry:
    """Create the local registry with Via's three initial tools.

    Args:
        fetch_metadata: Optional application-provided metadata lookup; when
            omitted, ``get_video_metadata`` reports itself unavailable.

    Returns:
        Registry containing ``get_video_metadata``, ``get_transcript`` and
        ``analyze_video`` in stable order.
    """
    registry = InProcessToolRegistry()
    registry.register(GetVideoMetadataTool(fetcher=fetch_metadata))
    registry.register(GetTranscriptTool())
    registry.register(AnalyzeVideoTool())
    return registry
