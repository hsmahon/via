"""Via's initial video-understanding tools.

Tools implement the harness ``Tool`` protocol and are registered into an
``InProcessToolRegistry`` locally; production will expose the same three
capabilities through Amazon Bedrock AgentCore Gateway.
"""

from via_tools.implementations.analyze_video import AnalyzeVideoTool, AnswerOutput, QuestionInput
from via_tools.implementations.get_transcript import (
    GetTranscriptTool,
    TranscriptInput,
    TranscriptOutput,
)
from via_tools.implementations.get_video_metadata import (
    GetVideoMetadataTool,
    MetadataFetcher,
    MetadataInput,
    MetadataOutput,
    VideoSnapshot,
)
from via_tools.registry import build_default_registry

__all__ = [
    "AnalyzeVideoTool",
    "AnswerOutput",
    "GetTranscriptTool",
    "GetVideoMetadataTool",
    "MetadataFetcher",
    "MetadataInput",
    "MetadataOutput",
    "QuestionInput",
    "TranscriptInput",
    "TranscriptOutput",
    "VideoSnapshot",
    "build_default_registry",
]
