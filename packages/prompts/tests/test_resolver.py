"""FilePromptResolver adapter tests (prompt resolution port)."""

from __future__ import annotations

import pytest
from via_harness import ErrorCategory, HarnessError, PromptEnvironment
from via_prompts import FilePromptResolver, PromptStore


class TestFilePromptResolver:
    """Resolution semantics over file-backed content."""

    def test_resolves_latest_local_version(self, prompt_root) -> None:  # type: ignore[no-untyped-def]
        """Unpinned lookups return the highest version in scope."""
        resolver = FilePromptResolver(PromptStore(prompt_root))
        assert resolver.get_prompt("video_assistant").version == 2

    def test_resolves_pinned_version(self, prompt_root) -> None:  # type: ignore[no-untyped-def]
        """Explicit pins win over latest-version selection."""
        resolver = FilePromptResolver(PromptStore(prompt_root))
        assert resolver.get_prompt("video_assistant", version=1).version == 1

    def test_environment_scoping(self, prompt_root) -> None:  # type: ignore[no-untyped-def]
        """Prod-only prompts resolve only under the prod scope."""
        resolver = FilePromptResolver(PromptStore(prompt_root))
        prompt = resolver.get_prompt("transcript_summary", environment=PromptEnvironment.PROD)
        assert prompt.template.startswith("Summarize")
        with pytest.raises(HarnessError) as err:
            resolver.get_prompt("transcript_summary", environment=PromptEnvironment.LOCAL)
        assert err.value.category is ErrorCategory.INVALID_REQUEST

    def test_returns_harness_prompt_type(self, prompt_root) -> None:  # type: ignore[no-untyped-def]
        """Resolved objects satisfy the harness Prompt contract."""
        resolver = FilePromptResolver(PromptStore(prompt_root))
        prompt = resolver.get_prompt("video_assistant", version=1)
        assert prompt.name == "video_assistant"
        assert set(prompt.variables) == {"video_id", "user_id"}
