"""Presigned GET playback tests for ``GET /videos/{id}/stream``.

Covers authentication, ownership, and URL signing for video playback. Uses
the shared ``clean_via_env`` fixture plus a moto-backed ``client`` and a
``seeded_video`` helper that creates a real ``VIDEO#id`` row so the
endpoint can presign its ``s3_key``.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient
from via_api.deps import _cached_repository, _cached_settings
from via_api.main import create_app
from via_db import VideoRecord


@pytest.fixture()
def client(monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    """Provide a test client wired to moto-backed DynamoDB and S3.

    Args:
        monkeypatch: Pytest environment patcher.

    Yields:
        Configured :class:`TestClient` with the mock active.
    """
    from moto import mock_aws

    with mock_aws():
        from via_db.client import get_dynamodb_resource
        from via_db.tables import create_table

        create_table(get_dynamodb_resource(region_name="us-east-1"), "via-api-test")
        monkeypatch.setenv("VIA_TABLE_NAME", "via-api-test")
        monkeypatch.setenv("VIA_BUCKET", "via-videos")
        monkeypatch.setenv("VIA_S3_PUBLIC_ENDPOINT_URL", "http://localhost:9000")
        _cached_settings.cache_clear()
        _cached_repository.cache_clear()
        yield TestClient(create_app())


@pytest.fixture()
def seeded_video(client: TestClient) -> VideoRecord:
    """Create one video row and return its stored record.

    Args:
        client: Test client with moto table already created.

    Returns:
        Persisted :class:`VideoRecord` for the default user.
    """
    body: dict[str, Any] = {"filename": "clip.mp4", "duration": 10.0}
    response = client.post("/videos", json=body, headers={"X-User-Id": "user-1"})
    assert response.status_code == 202, response.text
    video_id: str = response.json()["video_id"]
    settings = _cached_settings()
    repo = _cached_repository(settings.table_name, settings.dynamodb_endpoint_url)
    record = repo.get(video_id)
    assert record is not None
    return record


def test_stream_requires_auth(client: TestClient) -> None:
    """Unauthenticated access to ``/stream`` is rejected with 401 or 404."""
    response = client.get("/videos/abc/stream")
    assert response.status_code in (401, 404)


def test_stream_presigns(client: TestClient, seeded_video: VideoRecord) -> None:
    """Authenticated owner receives a presigned GET URL for playback.

    Args:
        client: Test client.
        seeded_video: Pre-created video owned by ``user-1``.
    """
    response = client.get(
        f"/videos/{seeded_video.video_id}/stream",
        headers={"X-User-Id": seeded_video.user_id},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert "X-Amz-Signature" in body["url"]
    assert body["expires_in_seconds"] == 900


def test_stream_forbidden_for_other_user(client: TestClient, seeded_video: VideoRecord) -> None:
    """Non-owner receives 403 when requesting another user's stream URL.

    Args:
        client: Test client.
        seeded_video: Pre-created video owned by ``user-1``.
    """
    response = client.get(
        f"/videos/{seeded_video.video_id}/stream",
        headers={"X-User-Id": "intruder"},
    )
    assert response.status_code == 403
