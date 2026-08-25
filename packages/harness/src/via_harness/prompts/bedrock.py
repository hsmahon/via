"""Amazon Bedrock Prompt Management implementation of the prompt port.

DEFERRED for v0.1: Via resolves prompts locally during development. When the
production deployment lands, this resolver will fetch immutable prompt
versions through the Bedrock Prompt Management control plane and cache them
by (name, version, environment). The interface below is final; only the
implementation body is pending. See ``docs/agent-harness.md`` for the
lifecycle mapping.
"""

from __future__ import annotations

from via_harness.prompts.base import Prompt, PromptEnvironment

__all__ = ["BedrockPromptManagementResolver"]


class BedrockPromptManagementResolver:
    """Placeholder production resolver backed by Bedrock Prompt Management."""

    def __init__(
        self, *, region: str, default_environment: PromptEnvironment = PromptEnvironment.PROD
    ) -> None:
        """Store connection parameters until the integration is implemented.

        Args:
            region: AWS region hosting the prompt resources.
            default_environment: Scope used when a lookup omits one.
        """
        self._region = region
        self._default_environment = default_environment

    def get_prompt(
        self, name: str, *, version: int | None = None, environment: PromptEnvironment | None = None
    ) -> Prompt:
        """Resolve a prompt from Bedrock Prompt Management.

        Args:
            name: Logical prompt name.
            version: Exact version; latest published when ``None``.
            environment: Scope; falls back to the configured default.

        Raises:
            NotImplementedError: Always, until the production integration
                ships (tracked in the harness roadmap).
        """
        raise NotImplementedError(
            "Bedrock Prompt Management resolution is deferred for v0.1; "
            "use LocalPromptResolver with via_prompts content files"
        )
