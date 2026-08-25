"""Shared fixtures for agent service tests."""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def clean_via_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep host `.env` values out of tests so wiring sees only explicit settings.

    Args:
        monkeypatch: Pytest environment patcher.
    """
    for var in ("VIA_DYNAMODB_ENDPOINT_URL", "VIA_S3_ENDPOINT_URL"):
        monkeypatch.setenv(var, "")
