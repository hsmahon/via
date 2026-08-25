"""Shared fixtures for prompts tests."""

from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture()
def prompt_root(tmp_path: Path) -> Path:
    """Create a populated prompt directory tree.

    Args:
        tmp_path: Pytest temporary directory.

    Returns:
        Root path containing two prompts across versions/environments.
    """
    root = tmp_path / "prompts"
    (root / "video_assistant").mkdir(parents=True)
    (root / "transcript_summary").mkdir()
    (root / "video_assistant" / "v1.yaml").write_text(
        "name: video_assistant\nversion: 1\nenvironment: local\n"
        'template: "Video {{video_id}} for user {{user_id}}."\n'
        "variables: [video_id, user_id]\nmetadata: {task: video-qa}\n",
        encoding="utf-8",
    )
    (root / "video_assistant" / "v2.yaml").write_text(
        "name: video_assistant\nversion: 2\nenvironment: local\n"
        'template: "Video {{video_id}} v2."\nvariables: [video_id]\n',
        encoding="utf-8",
    )
    (root / "transcript_summary" / "v1.yaml").write_text(
        "name: transcript_summary\nversion: 1\nenvironment: prod\n"
        'template: "Summarize {{transcript}}."\nvariables: [transcript]\n',
        encoding="utf-8",
    )
    return root
