"""Via agent harness.

The runtime boundary around Via's application logic: model, prompt, tool,
policy and observability are explicit ports with swappable implementations
(local for development; Amazon Bedrock / AgentCore in production). Via's
business logic depends only on the interfaces in this package - never on an
agent framework or a specific AWS SDK surface.
"""

from via_harness.context import (
    AuthorizationContext,
    Permission,
    RunContext,
    SessionContext,
)
from via_harness.errors import ErrorCategory, HarnessError, RunFailure
from via_harness.model.base import ModelClient, RetryPolicy
from via_harness.model.local import LocalModelClient
from via_harness.model.types import (
    ModelMessage,
    ModelRequest,
    ModelResponse,
    ModelRole,
    ModelToolSpec,
    StopReason,
    TokenUsage,
    ToolCallRequest,
)
from via_harness.policy import Authorizer, Decision, DefaultAuthorizer, VideoAccessChecker
from via_harness.prompts.base import Prompt, PromptEnvironment, PromptResolver, render_prompt
from via_harness.prompts.local import LocalPromptResolver
from via_harness.response import AgentResponse, Citation
from via_harness.runner import AgentRequest, AgentRunner, AgentRunResult, StepSummary
from via_harness.tools.base import Tool, ToolContract, ToolExecutionError, ToolResult, ToolStatus
from via_harness.tools.executor import ToolExecutor
from via_harness.tools.registry import InProcessToolRegistry, ToolRegistry
from via_harness.tracing import LocalMetrics, LocalTracer, MetricsSink, SpanRecord, Tracer

__version__ = "0.1.0"

__all__ = [
    "AgentRequest",
    "AgentResponse",
    "AgentRunResult",
    "AgentRunner",
    "AuthorizationContext",
    "Authorizer",
    "Citation",
    "Decision",
    "DefaultAuthorizer",
    "ErrorCategory",
    "HarnessError",
    "InProcessToolRegistry",
    "LocalMetrics",
    "LocalModelClient",
    "LocalPromptResolver",
    "LocalTracer",
    "MetricsSink",
    "ModelClient",
    "ModelMessage",
    "ModelRequest",
    "ModelResponse",
    "ModelRole",
    "ModelToolSpec",
    "Permission",
    "Prompt",
    "PromptEnvironment",
    "PromptResolver",
    "RetryPolicy",
    "RunContext",
    "RunFailure",
    "SessionContext",
    "SpanRecord",
    "StepSummary",
    "StopReason",
    "TokenUsage",
    "Tool",
    "ToolCallRequest",
    "ToolContract",
    "ToolExecutionError",
    "ToolExecutor",
    "ToolRegistry",
    "ToolResult",
    "ToolStatus",
    "Tracer",
    "VideoAccessChecker",
    "__version__",
    "render_prompt",
]
