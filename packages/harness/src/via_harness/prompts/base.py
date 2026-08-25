"""Prompt resolution port.

Prompts are named, versioned, environment-scoped artifacts. The application
never hardcodes prompt text in agent code - it resolves immutable versions
through :class:`PromptResolver`. The production implementation is Amazon
Bedrock Prompt Management; local development uses a file-backed resolver.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any, Protocol

from pydantic import BaseModel, ConfigDict, Field

from via_harness.errors import ErrorCategory, HarnessError

__all__ = ["Prompt", "PromptEnvironment", "PromptResolver", "render_prompt"]


class PromptEnvironment(StrEnum):
    """Deployment scopes a prompt version can be published to."""

    LOCAL = "local"
    DEV = "dev"
    STAGING = "staging"
    PROD = "prod"


class Prompt(BaseModel):
    """An immutable, resolved prompt version.

    Attributes:
        name: Stable logical name (e.g. ``video_assistant``).
        version: Monotonic integer version.
        environment: Environment this version is published to.
        template: Prompt body with ``{{variable}}`` placeholders.
        variables: Placeholder names declared by the template.
        metadata: Free-form metadata (task, language, owner, ...).
    """

    model_config = ConfigDict(frozen=True)

    name: str = Field(min_length=1)
    version: int = Field(ge=1)
    environment: PromptEnvironment
    template: str = Field(min_length=1)
    variables: tuple[str, ...] = Field(default=())
    metadata: dict[str, str] = Field(default_factory=dict)


class PromptResolver(Protocol):
    """Port for resolving immutable prompt versions.

    Implementations: file-backed local resolver (development) and Amazon
    Bedrock Prompt Management (production, planned). Resolution must be
    deterministic for a given (name, version, environment) triple.
    """

    def get_prompt(
        self, name: str, *, version: int | None = None, environment: PromptEnvironment | None = None
    ) -> Prompt:
        """Resolve a prompt by name, optionally pinned to a version.

        Args:
            name: Logical prompt name.
            version: Exact version; latest published when ``None``.
            environment: Scope; implementation default when ``None``.

        Returns:
            The immutable resolved prompt.

        Raises:
            HarnessError: Category ``INVALID_REQUEST`` when the prompt or
                version does not exist in the requested scope.
        """
        ...


def render_prompt(prompt: Prompt, **variables: Any) -> str:
    """Render a prompt template with validated variable substitution.

    Args:
        prompt: Resolved prompt whose template should be rendered.
        variables: Values keyed by placeholder name.

    Returns:
        Rendered prompt text.

    Raises:
        HarnessError: Category ``INVALID_REQUEST`` when required variables
            are missing or unexpected variables are supplied.
    """
    missing = [v for v in prompt.variables if v not in variables]
    extra = [k for k in variables if k not in prompt.variables]
    if missing or extra:
        raise HarnessError(
            ErrorCategory.INVALID_REQUEST,
            f"Prompt '{prompt.name}' variable mismatch",
            details={"missing": missing, "unexpected": extra},
        )
    rendered = prompt.template
    for key, value in variables.items():
        rendered = rendered.replace("{{" + key + "}}", str(value))
    return rendered
