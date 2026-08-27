"""Compatibility shim re-exporting Pegasus helpers.

Re-exports :class:`PegasusAnalysis`, ``VideoAnalysis`` alias, and
:func:`analyze_with_pegasus` from :mod:`via_worker_video_processing.pegasus`
for backward compatibility. Consumers should import from :mod:`pegasus` directly.
"""

from __future__ import annotations

from via_worker_video_processing.pegasus import (
    PegasusAnalysis,
    VideoAnalysis,
    analyze_with_pegasus,
)

__all__ = [
    "PegasusAnalysis",
    "VideoAnalysis",
    "analyze_with_pegasus",
]
