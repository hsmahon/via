"""Composition root: bind local or production implementations to the ports.

This is the ONLY module that knows which concrete implementations are in
play. Swapping LocalModelClient for BedrockConverseClient, or the in-process
tool registry for an AgentCore Gateway adapter, changes nothing above the
``AgentRunner`` interface.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from via_db import VideoRepository, get_table
from via_harness import (
    AgentRunner,
    AuthorizationContext,
    DefaultAuthorizer,
    ErrorCategory,
    HarnessError,
    LocalMetrics,
    LocalTracer,
    ModelClient,
    Permission,
)
from via_prompts import FilePromptResolver, PromptStore
from via_tools import MetadataFetcher, build_default_registry

from via_agent.settings import Settings

__all__ = ["ServiceContext", "build_authorization_context", "build_context"]

_PROMPTS_DIR = (
    Path(__file__).resolve().parents[4] / "agent" / "prompts" / "src" / "via_prompts" / "prompts"
)


class DbVideoAccessChecker:
    """Harness port backed by DynamoDB ownership lookup."""

    def __init__(self, repository: VideoRepository) -> None:
        """Initialize the checker.

        Args:
            repository: Video repository answering ownership queries.
        """
        self._repository = repository

    def check(self, *, user_id: str, video_id: str) -> bool:
        """Grant access iff the stored video belongs to the user.

        Args:
            user_id: Authenticated subject.
            video_id: Video under question.

        Returns:
            True when the user owns the video.
        """
        record = self._repository.get(video_id)
        return record is not None and record.user_id == user_id


class ServiceContext:
    """Bundle of wired collaborators handed to route handlers."""

    def __init__(
        self,
        *,
        runner: AgentRunner,
        tracer: LocalTracer,
        metrics: LocalMetrics,
        settings: Settings,
    ) -> None:
        """Initialize the context.

        Args:
            runner: Ready-to-use agent runner.
            tracer: Local tracer backing the debug trace endpoint.
            metrics: Counter sink.
            settings: Parsed settings.
        """
        self.runner = runner
        self.tracer = tracer
        self.metrics = metrics
        self.settings = settings


def build_context(settings: Settings | None = None) -> ServiceContext:
    """Wire every harness implementation according to settings.

    Args:
        settings: Optional override (tests); defaults to env.

    Returns:
        Fully wired :class:`ServiceContext`.

    Raises:
        HarnessError: When ``model_backend=bedrock`` is selected without a
            configured Pegasus model id.
    """
    resolved = settings or Settings()
    table = get_table(resolved.table_name, endpoint_url=resolved.dynamodb_endpoint_url)
    repository = VideoRepository(table)

    registry = build_default_registry(fetch_metadata=_metadata_fetcher(repository))
    prompts = FilePromptResolver(PromptStore(_prompts_root()), default_environment=resolved.env)
    tracer = LocalTracer()
    metrics = LocalMetrics()
    model = _build_model(resolved)

    runner = AgentRunner(
        model=model,
        prompts=prompts,
        tools=registry,
        authorizer=DefaultAuthorizer(DbVideoAccessChecker(repository)),
        tracer=tracer,
        metrics=metrics,
        agent_version=resolved.agent_version,
        prompt_globals={"environment": resolved.env},
    )
    return ServiceContext(runner=runner, tracer=tracer, metrics=metrics, settings=resolved)


def build_authorization_context(
    ctx: ServiceContext, *, user_id: str, video_id: str
) -> AuthorizationContext:
    """Build the authorization context with Via's v0.1 permission policy.

    Authenticated users hold every read/analyze permission; actual access is
    enforced per-video by the ownership checker inside the authorizer.

    Args:
        ctx: Wired service context (settings source).
        user_id: Authenticated subject.
        video_id: Video this interaction targets.

    Returns:
        Authorization context for one agent invocation.
    """
    _ = ctx
    return AuthorizationContext(
        user_id=user_id,
        video_id=video_id,
        permissions=frozenset(
            {Permission.VIDEO_READ, Permission.TRANSCRIPT_READ, Permission.VIDEO_ANALYZE}
        ),
    )


def _metadata_fetcher(repository: VideoRepository) -> MetadataFetcher:
    """Adapt the video repository to the metadata tool's fetcher port.

    Args:
        repository: Video repository.

    Returns:
        Callable mapping video id to metadata dict or None.
    """

    def fetch(video_id: str) -> dict[str, Any] | None:
        """Fetch one video as a plain dictionary.

        Args:
            video_id: Target video.

        Returns:
            Metadata mapping, or None when unknown.
        """
        record = repository.get(video_id)
        dumped: dict[str, Any] | None = record.model_dump(mode="json") if record else None
        return dumped

    return fetch


def _build_model(settings: Settings) -> ModelClient:
    """Instantiate the configured ModelClient implementation.

    Args:
        settings: Parsed settings selecting the backend.

    Returns:
        A harness ModelClient implementation.

    Raises:
        HarnessError: On Bedrock selection without a model id.
    """
    if settings.model_backend == "local":
        from via_harness import LocalModelClient

        local: ModelClient = LocalModelClient(model_id="via-local-model")
        return local
    if not settings.pegasus_model_id:
        raise HarnessError(
            ErrorCategory.INTERNAL_ERROR,
            "VIA_PEGASUS_MODEL_ID must be set when VIA_MODEL_BACKEND=bedrock",
        )
    from via_harness.model.bedrock import BedrockConverseClient

    return BedrockConverseClient.from_region(
        settings.aws_region, model_id=settings.pegasus_model_id
    )


def _prompts_root() -> Path:
    """Locate packaged prompt content across dev and container layouts.

    Returns:
        Directory containing ``<name>/v<version>.yaml`` files.
    """
    candidates = [
        Path.cwd() / "backend" / "agent" / "prompts" / "src" / "via_prompts" / "prompts",
        _PROMPTS_DIR,
        Path(__file__).resolve().parent.parent / "prompts",  # installed wheel layout
        Path("/app/prompts"),
    ]
    for candidate in candidates:
        if candidate.is_dir():
            return candidate
    raise RuntimeError(f"prompt content directory not found; tried {[str(c) for c in candidates]}")
