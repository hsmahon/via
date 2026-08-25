"""Tests for the Via API service."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient
from via_api.deps import _cached_repository, _cached_settings
from via_api.main import create_app

USER = {"X-User-Id": "user-1"}


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


def _create(client: TestClient, **overrides: Any) -> dict[str, Any]:
    """Create one video through the API.

    Args:
        client: HTTP client.
        **overrides: Body overrides merged into defaults.

    Returns:
        Parsed JSON response body.
    """
    body: dict[str, Any] = {"filename": "clip.mp4", "duration": 10.0}
    body.update(overrides)
    response = client.post("/videos", json=body, headers=USER)
    assert response.status_code == 202, response.text
    return response.json()


class TestHealth:
    """System endpoints."""

    def test_health_ok(self, client: TestClient) -> None:
        """GET /health reports ok."""
        assert client.get("/health").json()["status"] == "ok"


class TestVideoCrud:
    """REST lifecycle over /videos."""

    def test_create_returns_uploading_and_presigned_put(self, client: TestClient) -> None:
        """Creation returns UPLOADING status plus an upload target."""
        payload = _create(client)
        assert payload["status"] == "UPLOADING"
        assert payload["upload"]["method"] == "PUT"
        assert payload["upload"]["url"].startswith("http")

    def test_get_round_trip(self, client: TestClient) -> None:
        """Created videos are retrievable by id."""
        created = _create(client)
        fetched = client.get(f"/videos/{created['video_id']}")
        assert fetched.status_code == 200
        assert fetched.json()["filename"] == "clip.mp4"

    def test_get_unknown_404(self, client: TestClient) -> None:
        """Unknown ids produce 404."""
        assert client.get("/videos/nope").status_code == 404

    def test_list_is_scoped_and_sorted(self, client: TestClient) -> None:
        """Listing shows only the acting user's videos, newest first."""
        first = _create(client, filename="one.mp4")
        second = _create(client, filename="two.mp4")
        listed = client.get("/videos", headers=USER).json()
        assert [i["video_id"] for i in listed["items"]] == [second["video_id"], first["video_id"]]
        other = client.get("/videos", headers={"X-User-Id": "intruder"}).json()
        assert other["items"] == []

    def test_delete_requires_owner(self, client: TestClient) -> None:
        """Non-owners receive 403 on delete."""
        created = _create(client)
        response = client.delete(
            f"/videos/{created['video_id']}", headers={"X-User-Id": "intruder"}
        )
        assert response.status_code == 403

    def test_delete_soft_deletes_then_conflicts(self, client: TestClient) -> None:
        """First delete succeeds (DELETED); second conflicts (409)."""
        vid = _create(client)["video_id"]
        assert client.delete(f"/videos/{vid}", headers=USER).json()["status"] == "DELETED"
        assert client.delete(f"/videos/{vid}", headers=USER).status_code == 409
