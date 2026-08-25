"""Prompt content store tests."""

from __future__ import annotations

import pytest
from via_prompts import PromptStore, StoreError


class TestPromptStore:
    """Discovery and validation of versioned YAML content."""

    def test_loads_all_definitions(self, prompt_root) -> None:  # type: ignore[no-untyped-def]
        """Every valid YAML file under the root is discovered."""
        definitions = PromptStore(prompt_root).load_all()
        assert len(definitions) == 3
        names = {d.name for d in definitions}
        assert names == {"video_assistant", "transcript_summary"}

    def test_variables_default_to_placeholders(self, prompt_root) -> None:  # type: ignore[no-untyped-def]
        """Omitted variable lists are derived from template placeholders."""
        definitions = PromptStore(prompt_root).load_all()
        v2 = next(d for d in definitions if d.version == 2)
        assert v2.variables == ("video_id",)

    def test_missing_root_raises(self, tmp_path) -> None:  # type: ignore[no-untyped-def]
        """A nonexistent root is a configuration error."""
        with pytest.raises(StoreError):
            PromptStore(tmp_path / "missing").load_all()

    def test_invalid_yaml_raises(self, prompt_root) -> None:  # type: ignore[no-untyped-def]
        """Malformed YAML surfaces as StoreError with the file named."""
        bad = prompt_root / "broken" / "v1.yaml"
        bad.parent.mkdir()
        bad.write_text("name: [unclosed", encoding="utf-8")
        with pytest.raises(StoreError):
            PromptStore(prompt_root).load_all()

    def test_layout_mismatch_raises(self, prompt_root) -> None:  # type: ignore[no-untyped-def]
        """Version/name embedded in YAML must match the file layout."""
        wrong = prompt_root / "video_assistant" / "v9.yaml"
        wrong.write_text("name: video_assistant\nversion: 3\ntemplate: x\n", encoding="utf-8")
        with pytest.raises(StoreError) as err:
            PromptStore(prompt_root).load_all()
        assert "layout" in str(err.value)
