"""Tool discovery port and the in-process registry used for local runs.

The agent never imports tool functions directly - it asks a
:class:`ToolRegistry` which tools exist for a given authorization context.
The production implementation will be backed by Amazon Bedrock AgentCore
Gateway; local development uses :class:`InProcessToolRegistry`.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from via_harness.context import AuthorizationContext
from via_harness.errors import ErrorCategory, HarnessError
from via_harness.tools.base import Tool

__all__ = ["InProcessToolRegistry", "ToolRegistry"]


@runtime_checkable
class ToolRegistry(Protocol):
    """Port for tool discovery.

    Implementations return only tools whose ``required_permissions`` are
    satisfied by the supplied context; authorization enforcement itself is
    the policy layer's job and happens again at invocation time.
    """

    def get_tools(self, authz: AuthorizationContext) -> list[Tool]:
        """Return tools visible to the caller.

        Args:
            authz: Authorization context of the current interaction.

        Returns:
            Discoverable tools in stable (registration) order.
        """
        ...

    def get_tool(self, name: str) -> Tool | None:
        """Look up a single tool by name.

        Args:
            name: Contract name of the tool.

        Returns:
            The tool, or ``None`` when unknown to this registry.
        """
        ...


class InProcessToolRegistry:
    """Local development registry holding live tool instances."""

    def __init__(self) -> None:
        """Initialize an empty registry."""
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        """Register a tool instance under its contract name.

        Args:
            tool: Tool implementation with a valid contract.

        Raises:
            HarnessError: Category ``INTERNAL_ERROR`` on duplicate names,
                which indicates a wiring bug rather than a runtime condition.
        """
        if tool.contract.name in self._tools:
            raise HarnessError(
                ErrorCategory.INTERNAL_ERROR,
                f"Tool '{tool.contract.name}' is already registered",
                details={"tool": tool.contract.name},
            )
        self._tools[tool.contract.name] = tool

    def get_tools(self, authz: AuthorizationContext) -> list[Tool]:
        """Return registered tools permitted for the given context.

        Args:
            authz: Authorization context of the current interaction.

        Returns:
            Tools whose required permissions are all granted, in
            registration order.
        """
        return [
            tool
            for tool in self._tools.values()
            if authz.has_permissions(tool.contract.required_permissions)
        ]

    def get_tool(self, name: str) -> Tool | None:
        """Look up a registered tool by contract name.

        Args:
            name: Contract name of the tool.

        Returns:
            The tool instance, or ``None`` when not registered.
        """
        return self._tools.get(name)
