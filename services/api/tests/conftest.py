"""Shared fixtures for API tests."""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def clean_via_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep host `.env` values (e.g. DynamoDB Local endpoints) out of tests.

    Args:
        monkeypatch: Pytest environment patcher.
    """
    import via_api.deps as deps

    for var in ("VIA_DYNAMODB_ENDPOINT_URL", "VIA_S3_ENDPOINT_URL", "VIA_S3_PUBLIC_ENDPOINT_URL"):
        monkeypatch.setenv(var, "")
    deps._cached_settings.cache_clear()
    deps._cached_repository.cache_clear()
    yield
    deps._cached_settings.cache_clear()
    deps._cached_repository.cache_clear()
