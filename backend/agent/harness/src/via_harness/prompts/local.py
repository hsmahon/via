"""In-memory prompt resolver backed by pre-loaded :class:`Prompt` objects.

This is the local/development implementation of the ``PromptResolver`` port.
It is deliberately trivial: the application wires it with prompts loaded
from files (``via_prompts``) or tests construct them inline. Production
resolves the same interface from Amazon Bedrock Prompt Management.
"""

from __future__ import annotations

from via_harness.errors import ErrorCategory, HarnessError
from via_harness.prompts.base import Prompt, PromptEnvironment

__all__ = ["LocalPromptResolver"]


class LocalPromptResolver:
    """Deterministic resolver over an in-memory prompt collection."""

    def __init__(
        self,
        prompts: list[Prompt],
        default_environment: PromptEnvironment = PromptEnvironment.LOCAL,
    ) -> None:
        """Initialize the resolver.

        Args:
            prompts: Available prompts; may span names, versions and scopes.
            default_environment: Scope used when a lookup omits one.
        """
        self._default_environment = default_environment
        self._index: dict[tuple[str, PromptEnvironment, int], Prompt] = {}
        for prompt in prompts:
            self._index[(prompt.name, prompt.environment, prompt.version)] = prompt

    def get_prompt(
        self, name: str, *, version: int | None = None, environment: PromptEnvironment | None = None
    ) -> Prompt:
        """Resolve a prompt version from the in-memory index.

        Args:
            name: Logical prompt name.
            version: Exact version; highest available when ``None``.
            environment: Scope; falls back to the configured default.

        Returns:
            The resolved immutable prompt.

        Raises:
            HarnessError: Category ``INVALID_REQUEST`` when no matching
                prompt exists (message lists what was found).
        """
        env = environment or self._default_environment
        if version is not None:
            prompt = self._index.get((name, env, version))
            if prompt is None:
                raise self._not_found(name, env, version)
            return prompt

        versions = sorted(v for (n, e, v) in self._index if n == name and e == env)
        if not versions:
            raise self._not_found(name, env, None)
        return self._index[(name, env, versions[-1])]

    def _not_found(
        self, name: str, environment: PromptEnvironment, version: int | None
    ) -> HarnessError:
        """Build the standardized not-found error.

        Args:
            name: Requested prompt name.
            environment: Requested scope.
            version: Requested version, if pinned.

        Returns:
            Harness error carrying resolution details for traces.
        """
        known = sorted({(n, e.value, v) for (n, e, v) in self._index})
        return HarnessError(
            ErrorCategory.INVALID_REQUEST,
            f"Prompt not found: {name!r} version={version} environment={environment.value}",
            details={"known_prompts": [list(k) for k in known]},
        )
