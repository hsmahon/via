"""Prompt resolution tests (required area 1)."""

from __future__ import annotations

import pytest
from via_harness import Prompt, PromptEnvironment, render_prompt
from via_harness.errors import ErrorCategory, HarnessError
from via_harness.prompts.local import LocalPromptResolver


def _prompt(name: str = "video_assistant", version: int = 1) -> Prompt:
    """Build a minimal local-scope prompt.

    Args:
        name: Prompt name.
        version: Prompt version.

    Returns:
        Prompt declaring a single ``video_id`` variable.
    """
    return Prompt(
        name=name,
        version=version,
        environment=PromptEnvironment.LOCAL,
        template="You assist with video {{video_id}}.",
        variables=("video_id",),
    )


class TestLocalPromptResolver:
    """Resolution semantics of the file-free local resolver."""

    def test_resolves_latest_version_when_unpinned(self) -> None:
        """Returns the highest version for a name when version is omitted."""
        resolver = LocalPromptResolver([_prompt(version=1), _prompt(version=3), _prompt(version=2)])
        assert resolver.get_prompt("video_assistant").version == 3

    def test_resolves_exact_pinned_version(self) -> None:
        """Returns the exact requested version when pinned."""
        resolver = LocalPromptResolver([_prompt(version=1), _prompt(version=2)])
        assert resolver.get_prompt("video_assistant", version=1).version == 1

    def test_respects_environment_scope(self) -> None:
        """Only resolves prompts published to the requested environment."""
        prod = Prompt(
            name="video_assistant",
            version=9,
            environment=PromptEnvironment.PROD,
            template="t",
            variables=(),
        )
        resolver = LocalPromptResolver([_prompt(version=1), prod])
        assert (
            resolver.get_prompt("video_assistant", environment=PromptEnvironment.PROD).version == 9
        )
        with pytest.raises(HarnessError) as err:
            resolver.get_prompt("video_assistant", environment=PromptEnvironment.STAGING)
        assert err.value.category is ErrorCategory.INVALID_REQUEST

    def test_unknown_prompt_raises_invalid_request(self) -> None:
        """Missing names surface INVALID_REQUEST with known-prompt details."""
        resolver = LocalPromptResolver([])
        with pytest.raises(HarnessError) as err:
            resolver.get_prompt("nope")
        assert err.value.category is ErrorCategory.INVALID_REQUEST
        assert "known_prompts" in err.value.details


class TestRenderPrompt:
    """Template rendering validation."""

    def test_renders_declared_variables(self) -> None:
        """Substitutes declared placeholders."""
        prompt = _prompt()
        rendered = render_prompt(prompt, video_id="v-42")
        assert rendered == "You assist with video v-42."

    def test_variable_mismatch_raises(self) -> None:
        """Missing or extra variables are rejected before any rendering."""
        prompt = _prompt()
        with pytest.raises(HarnessError):
            render_prompt(prompt)
        with pytest.raises(HarnessError):
            render_prompt(prompt, video_id="v", unexpected="x")
