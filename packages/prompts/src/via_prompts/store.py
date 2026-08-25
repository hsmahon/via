"""Prompt content models and file-backed registry.

Via separates prompt *content* (this package: versioned YAML files) from
prompt *resolution mechanics* (the ``via-harness`` ``PromptResolver`` port).
``FilePromptResolver`` adapts one to the other; production will swap the
resolver for Amazon Bedrock Prompt Management without touching content.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError

__all__ = ["PromptDefinition", "PromptStore", "StoreError"]

_PLACEHOLDER = re.compile(r"\{\{\s*([a-z_][a-z0-9_]*)\s*\}\}")


class PromptDefinition(BaseModel):
    """One immutable prompt version loaded from YAML.

    Attributes:
        name: Stable logical name.
        version: Monotonic integer version.
        environment: Deployment scope this version targets.
        description: Human-readable purpose of the prompt.
        template: Body containing ``{{variable}}`` placeholders.
        variables: Placeholder names derived from the template.
        metadata: Free-form operational metadata (task, language, owner).
    """

    model_config = ConfigDict(frozen=True)

    name: str = Field(min_length=1)
    version: int = Field(ge=1)
    environment: str = Field(default="local")
    description: str = ""
    template: str = Field(min_length=1)
    variables: tuple[str, ...] = ()
    metadata: dict[str, str] = Field(default_factory=dict)


class StoreError(Exception):
    """Raised when prompt content cannot be discovered or parsed."""

    def __init__(self, message: str, *, cause: BaseException | None = None) -> None:
        """Initialize the store error.

        Args:
            message: Human-readable description.
            cause: Wrapped parse/validation exception.
        """
        super().__init__(message)
        self.__cause__ = cause


class PromptStore:
    """Loads versioned prompt definitions from a directory tree.

    Layout convention::

        <root>/<prompt_name>/v<version>.yaml
    """

    def __init__(self, root: Path | str) -> None:
        """Initialize the store.

        Args:
            root: Directory containing ``<name>/v<int>.yaml`` entries.
        """
        self._root = Path(root)

    def load_all(self) -> list[PromptDefinition]:
        """Discover and parse every prompt file under the root.

        Returns:
            All valid definitions sorted by (name, environment, version).

        Raises:
            StoreError: When the root is missing or any file is invalid.
        """
        if not self._root.is_dir():
            raise StoreError(f"prompt root does not exist: {self._root}")
        definitions: list[PromptDefinition] = []
        for path in sorted(self._root.glob("*/*.yaml")):
            definitions.append(self._load_file(path))
        return definitions

    def _load_file(self, path: Path) -> PromptDefinition:
        """Parse and validate one prompt YAML file.

        Args:
            path: Path to the YAML file.

        Returns:
            The validated definition.

        Raises:
            StoreError: On YAML/schema errors or placeholder mismatches.
        """
        try:
            raw: dict[str, Any] = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        except yaml.YAMLError as exc:
            raise StoreError(f"invalid YAML in {path}", cause=exc) from exc
        declared = tuple(raw.get("variables") or ())
        found = tuple(dict.fromkeys(_PLACEHOLDER.findall(raw.get("template", ""))))
        variables = declared or found
        if set(declared or found) != set(found):
            raise StoreError(
                f"declared variables {declared} do not match template placeholders {found} in {path}"
            )
        try:
            definition = PromptDefinition(
                name=str(raw["name"]),
                version=int(raw.get("version", 1)),
                environment=str(raw.get("environment", "local")),
                description=str(raw.get("description", "")),
                template=str(raw["template"]),
                variables=variables,
                metadata={str(k): str(v) for k, v in (raw.get("metadata") or {}).items()},
            )
        except (KeyError, ValidationError, TypeError, ValueError) as exc:
            raise StoreError(f"invalid prompt schema in {path}: {exc}", cause=exc) from exc
        stem = path.parent.name
        expected_version_file = f"v{definition.version}.yaml"
        if path.name != expected_version_file or stem != definition.name:
            raise StoreError(
                f"file layout mismatch for prompt '{definition.name}' v{definition.version}: expected {stem}/{expected_version_file}"
            )
        return definition


def derive_variables(template: str) -> tuple[str, ...]:
    """Extract placeholder names from a template string.

    Args:
        template: Template containing ``{{variable}}`` placeholders.

    Returns:
        Placeholder names in order of first appearance.
    """
    return tuple(dict.fromkeys(_PLACEHOLDER.findall(template)))
