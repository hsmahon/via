"""``analyze_video`` - interface for TwelveLabs Pegasus via Amazon Bedrock.

The deep video-understanding call is the production target of the harness's
``ModelClient``; this tool will invoke it server-side once credentials and
the Pegasus inference profile are provisioned. Until then it reports
unavailable. The contract is final.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field
from via_harness import AuthorizationContext, ToolContract, ToolResult, ToolStatus
from via_harness.context import Permission

__all__ = ["AnalyzeVideoTool", "AnswerOutput", "QuestionInput"]


class QuestionInput(BaseModel):
    """Arguments for ``analyze_video``."""

    question: str = Field(
        min_length=1, max_length=1000, description="What to analyze in the video."
    )


class AnswerOutput(BaseModel):
    """Payload returned once Pegasus analysis exists."""

    answer: str
    confidence: float | None = None


class AnalyzeVideoTool:
    """Deep video analysis through TwelveLabs Pegasus (pending integration)."""

    contract = ToolContract(
        name="analyze_video",
        description="Analyze the current video with a video-understanding model to answer open-ended questions about its content.",
        input_model=QuestionInput,
        output_model=AnswerOutput,
        required_permissions=frozenset({Permission.VIDEO_ANALYZE}),
        timeout_seconds=60.0,
        owner="via-agent-platform",
    )

    def execute(
        self, *, video_id: str, authz: AuthorizationContext, arguments: dict[str, Any]
    ) -> ToolResult:
        """Report the pending integration.

        Args:
            video_id: Target video from the authorized context.
            authz: Caller context (unused beyond signature conformance).
            arguments: Validated question arguments.

        Returns:
            Unavailable result until the Pegasus integration lands.
        """
        _ = video_id, authz, arguments
        return ToolResult(
            status=ToolStatus.UNAVAILABLE,
            detail="deep video analysis is not available yet: TwelveLabs Pegasus integration is scheduled for v0.2",
        )
