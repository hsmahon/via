"""Shared fixtures for harness tests."""

from __future__ import annotations

from typing import Any

import pytest
from pydantic import BaseModel, Field
from via_harness import (
    AgentRunner,
    AuthorizationContext,
    DefaultAuthorizer,
    InProcessToolRegistry,
    LocalMetrics,
    LocalPromptResolver,
    LocalTracer,
    Permission,
    Prompt,
    PromptEnvironment,
    SessionContext,
    ToolContract,
    ToolExecutor,
    ToolResult,
    ToolStatus,
)
from via_harness.model.local import LocalModelClient


class EchoInput(BaseModel):
    """Input schema for the echo test tool."""

    text: str = Field(min_length=1)


class EchoOutput(BaseModel):
    """Output schema for the echo test tool."""

    echoed: str


class EchoTool:
    """Deterministic test tool returning its input."""

    contract = ToolContract(
        name="echo",
        description="Echoes the provided text back to the caller.",
        input_model=EchoInput,
        output_model=EchoOutput,
    )

    def __init__(self, *, fail: bool = False) -> None:
        """Initialize the tool.

        Args:
            fail: When True, execute raises to exercise error paths.
        """
        self._fail = fail

    def execute(
        self, *, video_id: str, authz: AuthorizationContext, arguments: dict[str, Any]
    ) -> ToolResult:
        """Echo the call, or raise when constructed with ``fail=True``.

        Args:
            video_id: Target video id.
            authz: Caller authorization context.
            arguments: Validated tool arguments.

        Returns:
            Echoed payload.

        Raises:
            RuntimeError: When built with ``fail=True``.
        """
        _ = video_id, authz
        if self._fail:
            raise RuntimeError("boom")
        return ToolResult(status=ToolStatus.OK, payload={"echoed": arguments.get("text", "")})


class AllowAllChecker:
    """Ownership checker granting every request (tests only)."""

    def check(self, *, user_id: str, video_id: str) -> bool:
        """Grant access unconditionally.

        Args:
            user_id: Authenticated subject.
            video_id: Video under question.

        Returns:
            Always True.
        """
        _ = user_id, video_id
        return True


def make_prompt(
    name: str = "video_assistant", version: int = 1, variables: tuple[str, ...] = ("video_id",)
) -> Prompt:
    """Build a minimal valid prompt for runner tests.

    Args:
        name: Prompt name.
        version: Prompt version.
        variables: Template variables declared by the prompt.

    Returns:
        A prompt whose template renders ``video_id``.
    """
    placeholders = ", ".join("{{" + v + "}}" for v in variables)
    template = f"You assist with {placeholders}." if variables else "You are helpful."
    return Prompt(
        name=name,
        version=version,
        environment=PromptEnvironment.LOCAL,
        template=template,
        variables=variables,
        metadata={"task": "test"},
    )


@pytest.fixture()
def tracer() -> LocalTracer:
    """Provide a fresh local tracer.

    Returns:
        Empty :class:`LocalTracer`.
    """
    return LocalTracer()


@pytest.fixture()
def metrics() -> LocalMetrics:
    """Provide a fresh metrics sink.

    Returns:
        Empty :class:`LocalMetrics`.
    """
    return LocalMetrics()


@pytest.fixture()
def registry() -> InProcessToolRegistry:
    """Provide an empty in-process registry.

    Returns:
        Empty :class:`InProcessToolRegistry`.
    """
    return InProcessToolRegistry()


@pytest.fixture()
def executor() -> ToolExecutor:
    """Provide a shared tool executor.

    Returns:
        :class:`ToolExecutor` with default worker count.
    """
    return ToolExecutor()


@pytest.fixture()
def authz() -> AuthorizationContext:
    """Provide a fully-permitted authorization context.

    Returns:
        Context for ``user-1`` on ``video-1`` with all permissions.
    """
    return AuthorizationContext(
        user_id="user-1",
        video_id="video-1",
        permissions=frozenset(
            {Permission.VIDEO_READ, Permission.TRANSCRIPT_READ, Permission.VIDEO_ANALYZE}
        ),
    )


@pytest.fixture()
def session() -> SessionContext:
    """Provide a test session context.

    Returns:
        Session for ``user-1``.
    """
    return SessionContext(session_id="sess-test", user_id="user-1")


@pytest.fixture()
def runner_factory(
    registry: InProcessToolRegistry, tracer: LocalTracer, metrics: LocalMetrics
) -> Any:
    """Factory building runners wired to the shared fixtures.

    Args:
        registry: Shared tool registry.
        tracer: Shared tracer.
        metrics: Shared metrics.

    Returns:
        Callable accepting keyword overrides for model/prompts/tools/etc.
    """

    def factory(**overrides: Any) -> AgentRunner:
        """Build an AgentRunner with fixture defaults and overrides.

        Args:
            **overrides: Constructor kwargs applied over the defaults.

        Returns:
            Configured :class:`AgentRunner`.
        """
        kwargs: dict[str, Any] = {
            "model": LocalModelClient(),
            "prompts": LocalPromptResolver([make_prompt()]),
            "tools": registry,
            "authorizer": DefaultAuthorizer(AllowAllChecker()),
            "tracer": tracer,
            "metrics": metrics,
        }
        kwargs.update(overrides)
        return AgentRunner(**kwargs)

    return factory


@pytest.fixture()
def echo_tool_cls() -> type[EchoTool]:
    """Expose the echo tool class to tests.

    Returns:
        The :class:`EchoTool` class defined in this module.
    """
    return EchoTool
