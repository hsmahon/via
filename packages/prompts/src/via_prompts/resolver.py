"""Adapter implementing the harness ``PromptResolver`` port over the store."""

from __future__ import annotations

from via_harness import ErrorCategory, HarnessError, Prompt, PromptEnvironment

from via_prompts.store import PromptDefinition, PromptStore

__all__ = ["FilePromptResolver"]


class FilePromptResolver:
    """Local resolver serving immutable prompt versions from YAML files.

    This is the development implementation of prompt resolution; production
    resolves through Amazon Bedrock Prompt Management behind the same port.
    """

    def __init__(self, store: PromptStore, default_environment: str = "local") -> None:
        """Initialize and eagerly load the store.

        Args:
            store: Content store to serve.
            default_environment: Scope used when lookups omit one.
        """
        self._default = default_environment
        self._definitions: dict[tuple[str, str, int], PromptDefinition] = {}
        for definition in store.load_all():
            self._definitions[(definition.name, definition.environment, definition.version)] = (
                definition
            )

    def get_prompt(
        self, name: str, *, version: int | None = None, environment: PromptEnvironment | None = None
    ) -> Prompt:
        """Resolve a prompt version from loaded content.

        Args:
            name: Logical prompt name.
            version: Exact version; highest available when ``None``.
            environment: Scope; falls back to the configured default.

        Returns:
            The harness :class:`Prompt`.

        Raises:
            HarnessError: Category ``INVALID_REQUEST`` when nothing matches.
        """
        env = environment.value if environment else self._default
        versions = sorted(v for (n, e, v) in self._definitions if n == name and e == env)
        chosen = version if version is not None else (versions[-1] if versions else None)
        definition = self._definitions.get((name, env, chosen)) if chosen is not None else None
        if definition is None:
            raise HarnessError(
                ErrorCategory.INVALID_REQUEST,
                f"Prompt not found: {name!r} version={version} environment={env}",
                details={"known": sorted([n, e, v] for (n, e, v) in self._definitions)},
            )
        return Prompt(
            name=definition.name,
            version=definition.version,
            environment=PromptEnvironment(definition.environment),
            template=definition.template,
            variables=definition.variables,
            metadata=definition.metadata,
        )
