"""Compatibility shim re-exporting transcribe and pegasus helpers."""

from __future__ import annotations

from via_worker_video_processing.pegasus import (
    PegasusAnalysis,
    VideoAnalysis,
    analyze_with_pegasus,
)
from via_worker_video_processing.transcribe import TranscriptionResult, transcribe

__all__ = [
    "PegasusAnalysis",
    "TranscriptionResult",
    "VideoAnalysis",
    "analyze_with_pegasus",
    "transcribe",
]
