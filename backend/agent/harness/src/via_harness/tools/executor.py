"""Tool invocation mechanics: validation, timeout and error normalization.

The executor is the single place where tool arguments are validated against
the contract's input model, the wall-clock timeout is enforced, and any
exception is normalized into the harness error taxonomy. Tools themselves
stay free of cross-cutting concerns.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeoutError
from typing import Any

from pydantic import TypeAdapter, ValidationError

from via_harness.context import AuthorizationContext
from via_harness.errors import ErrorCategory, HarnessError
from via_harness.tools.base import Tool, ToolExecutionError, ToolResult

__all__ = ["ToolExecutor"]

_ADAPTER_CACHE: dict[int, TypeAdapter[Any]] = {}


class ToolExecutor:
    """Runs tools with contract-driven guards.

    Timeouts are enforced with a worker thread pool: a timed-out call's
    thread may linger until the underlying operation returns, but the agent
    run proceeds immediately with a ``TIMEOUT`` failure. This is acceptable
    for v0.1's short-lived local tools and documented in
    ``docs/agent-harness.md``.
    """

    def __init__(self, *, max_workers: int = 4) -> None:
        """Initialize the executor.

        Args:
            max_workers: Upper bound on concurrently executing tool calls.
        """
        self._pool = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="via-tool")

    def execute(
        self,
        tool: Tool,
        *,
        video_id: str,
        authz: AuthorizationContext,
        arguments: dict[str, Any],
        run_id: str | None = None,
    ) -> ToolResult:
        """Validate, run and normalize one tool invocation.

        Args:
            tool: Registered tool to invoke.
            video_id: Target video from the authorized context.
            authz: Authorization context of the calling user.
            arguments: Raw arguments as produced by the model.
            run_id: Agent run identifier attached to raised errors.

        Returns:
            Normalized :class:`ToolResult`.

        Raises:
            HarnessError: ``INVALID_TOOL_ARGUMENTS`` for schema violations,
                ``TIMEOUT`` when the contract deadline lapses, or
                ``TOOL_ERROR`` (wrapped cause preserved) for unexpected
                failures. None of these are swallowed.
        """
        validated = self._validate(tool, arguments, run_id)
        future = self._pool.submit(
            tool.execute, video_id=video_id, authz=authz, arguments=validated
        )
        try:
            result = future.result(timeout=tool.contract.timeout_seconds)
        except FutureTimeoutError as exc:
            raise HarnessError(
                ErrorCategory.TIMEOUT,
                f"Tool '{tool.contract.name}' exceeded {tool.contract.timeout_seconds:.1f}s",
                run_id=run_id,
                details={"tool": tool.contract.name},
                cause=exc,
            ) from exc
        except Exception as exc:
            raise ToolExecutionError(
                f"Tool '{tool.contract.name}' failed: {exc}",
                tool_name=tool.contract.name,
                run_id=run_id,
                cause=exc,
            ) from exc
        return result

    def _validate(
        self, tool: Tool, arguments: dict[str, Any], run_id: str | None
    ) -> dict[str, Any]:
        """Validate raw arguments against the contract input model.

        Args:
            tool: Tool whose contract declares the input schema.
            arguments: Raw model-produced arguments.
            run_id: Agent run identifier attached to raised errors.

        Returns:
            Validated argument dictionary.

        Raises:
            HarnessError: Category ``INVALID_TOOL_ARGUMENTS`` describing the
                pydantic validation failure.
        """
        adapter = _ADAPTER_CACHE.get(id(tool.contract.input_model))
        if adapter is None:
            adapter = TypeAdapter(tool.contract.input_model)
            _ADAPTER_CACHE[id(tool.contract.input_model)] = adapter
        try:
            model = adapter.validate_python(arguments)
        except ValidationError as exc:
            raise HarnessError(
                ErrorCategory.INVALID_TOOL_ARGUMENTS,
                f"Invalid arguments for tool '{tool.contract.name}'",
                run_id=run_id,
                details={"tool": tool.contract.name, "errors": exc.errors(include_url=False)},
                cause=exc,
            ) from exc
        dumped: dict[str, Any] = model.model_dump(mode="json")
        return dumped
