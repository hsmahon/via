"""Vertical Slice #1 tests: POST /videos contract.

Exercises the exact checklist from the slice spec plus the preserved
presigned-URL seam (bytes still go browser->S3; the API never proxies them).
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any
from unittest.mock import patch

import pytest
from botocore.exceptions import ClientError
from fastapi.testclient import TestClient
from via_api.deps import _cached_repository, _cached_settings
from via_api.main import create_app
from via_db import VideoStatus

USER = {"X-User-Id": "user-1"}


@pytest.fixture()
def client(monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    """Provide a TestClient over a moto-backed DynamoDB table.

    Yields:
        TestClient wired to an in-memory Via table.
    """
    from moto import mock_aws

    with mock_aws():
        from via_db.client import get_dynamodb_resource
        from via_db.tables import create_table

        create_table(get_dynamodb_resource(region_name="us-east-1"), "via-slice-test")
        monkeypatch.setenv("VIA_TABLE_NAME", "via-slice-test")
        monkeypatch.setenv("VIA_BUCKET", "via-videos")
        monkeypatch.setenv("VIA_S3_PUBLIC_ENDPOINT_URL", "http://localhost:9000")
        monkeypatch.setenv("VIA_MAX_VIDEOS_PER_USER", "2")
        _cached_settings.cache_clear()
        _cached_repository.cache_clear()
        yield TestClient(create_app())
        _cached_settings.cache_clear()
        _cached_repository.cache_clear()


def _post(client: TestClient, body: dict[str, Any], headers: dict[str, str] | None = None) -> Any:
    """POST /videos helper.

    Args:
        client: TestClient.
        body: JSON payload.
        headers: Optional header override (None -> ``USER``).

    Returns:
        Raw response.
    """
    headers = headers if headers is not None else USER
    return client.post("/videos", json=body, headers=headers)


class TestSuccessfulCreate:
    """Happy-path acceptance (202) and record shape."""

    def test_returns_202_with_video_id_and_uploading(self, client: TestClient) -> None:
        """Valid POST -> 202, video_id present, status UPLOADING."""
        response = _post(client, {"filename": "clip.mp4", "content_type": "video/mp4"})
        assert response.status_code == 202, response.text
        body = response.json()
        assert body["video_id"]
        assert isinstance(body["video_id"], str)
        assert body["status"] == VideoStatus.UPLOADING.value

    def test_legacy_video_name_alias_accepted(self, client: TestClient) -> None:
        """video_name is accepted as a backwards-compat alias for filename."""
        response = _post(client, {"video_name": "legacy.mp4"})
        assert response.status_code == 202, response.text
        assert response.json()["video_id"]

    def test_dynamodb_record_contains_expected_metadata(self, client: TestClient) -> None:
        """DynamoDB META row mirrors file_size, content_type, s3_key and ownership."""
        body: dict[str, Any] = {
            "filename": "clip.mp4",
            "content_type": "video/mp4",
            "file_size": 1234,
            "duration": 5.0,
        }
        created = _post(client, body).json()
        vid = created["video_id"]

        fetched = client.get(f"/videos/{vid}").json()
        assert fetched["video_id"] == vid
        assert fetched["filename"] == "clip.mp4"
        assert fetched["status"] == "UPLOADING"

        repo = _cached_repository("via-slice-test", None)  # type: ignore[arg-type]
        record = repo.get(vid)
        assert record is not None
        assert record.user_id == "user-1"
        assert record.filename == "clip.mp4"
        assert record.content_type == "video/mp4"
        assert record.file_size == 1234
        assert record.s3_key == f"videos/user-1/{vid}/clip.mp4"

    def test_each_video_gets_unique_id(self, client: TestClient) -> None:
        """Two creates produce distinct video_ids."""
        first = _post(client, {"filename": "a.mp4"}).json()["video_id"]
        second = _post(client, {"filename": "b.mp4"}).json()["video_id"]
        assert first != second

    def test_upload_target_attached(self, client: TestClient) -> None:
        """Presigned PUT target is present and plausibly shaped."""
        body = _post(client, {"filename": "clip.mp4"}).json()
        assert body["upload"]["method"] == "PUT"
        assert body["upload"]["url"].startswith("http")
        assert body["upload"]["expires_in_seconds"] == 900


class TestUnsupportedMediaType:
    """Content-type allow-list enforcement."""

    def test_rejected_when_not_in_allow_list(self, client: TestClient) -> None:
        """Unknown MIME -> 415 with no side-effect."""
        response = _post(client, {"filename": "x.mp4", "content_type": "image/png"})
        assert response.status_code == 415, response.text

    def test_accepted_when_in_allow_list(self, client: TestClient) -> None:
        """Known MIME -> 202."""
        assert _post(client, {"filename": "x.mp4", "content_type": "video/mp4"}).status_code == 202

    def test_missing_content_type_is_permitted(self, client: TestClient) -> None:
        """Omitted content_type is not rejected (client may not know it)."""
        assert _post(client, {"filename": "x.mp4"}).status_code == 202


class TestUnauthorized:
    """401 when no identity can be resolved."""

    def test_401_when_env_has_no_default_user(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Clear VIA_DEFAULT_USER_ID and omit X-User-Id -> 401."""
        monkeypatch.setenv("VIA_DEFAULT_USER_ID", "")
        _cached_settings.cache_clear()
        response = client.post("/videos", json={"filename": "x.mp4"}, headers={})
        assert response.status_code == 401, response.text
        assert "not authenticated" in response.text.lower()
        _cached_settings.cache_clear()

    def test_200_with_explicit_header(self, client: TestClient) -> None:
        """Explicit X-User-Id scopes the record to that user."""
        response = client.post(
            "/videos", json={"filename": "x.mp4"}, headers={"X-User-Id": "someone"}
        )
        assert response.status_code == 202
        assert response.json()["user_id"] == "someone"


class TestQuota:
    """Quota -> 409 Conflict."""

    def test_quota_exceeded_returns_409(self, client: TestClient) -> None:
        """After max_videos_per_user (2) further creates -> 409."""
        assert _post(client, {"filename": "one.mp4"}).status_code == 202
        assert _post(client, {"filename": "two.mp4"}).status_code == 202
        third = _post(client, {"filename": "three.mp4"})
        assert third.status_code == 409, third.text
        assert "quota" in third.text.lower()

    def test_other_user_not_affected_by_quota(self, client: TestClient) -> None:
        """Quota is per-user."""
        _post(client, {"filename": "a.mp4"})
        _post(client, {"filename": "b.mp4"})
        assert (
            _post(client, {"filename": "c.mp4"}, headers={"X-User-Id": "other"}).status_code == 202
        )


class TestBadRequest:
    """400/422 for missing or malformed inputs."""

    def test_missing_filename_returns_400_or_422(self, client: TestClient) -> None:
        """No filename or alias -> error."""
        response = client.post("/videos", json={"duration": 5}, headers=USER)
        assert response.status_code in (400, 422), response.text

    def test_path_traversal_filename_returns_400(self, client: TestClient) -> None:
        """Filename containing path separators -> 400."""
        response = _post(client, {"filename": "../etc/passwd"})
        assert response.status_code == 400, response.text


class TestDynamoSafety:
    """DynamoDB guard rails."""

    def test_duplicate_video_id_cannot_overwrite(self) -> None:
        """Direct repo duplicate -> VideoAlreadyExists (conditional put)."""
        from moto import mock_aws
        from via_db.client import get_dynamodb_resource
        from via_db.tables import create_table
        from via_db.videos import VideoRepository

        with mock_aws():
            resource = get_dynamodb_resource(region_name="us-east-1")
            create_table(resource, "via-dup-test")
            repo = VideoRepository(resource.Table("via-dup-test"))
            repo.create(video_id="dup", user_id="u1", filename="a.mp4")
            from via_db import VideoAlreadyExists

            with pytest.raises(VideoAlreadyExists):
                repo.create(video_id="dup", user_id="u2", filename="b.mp4")

    def test_dynamodb_failure_via_dependency_override_maps_to_500(self, client: TestClient) -> None:
        """Repository failure during create surfaces as 500."""
        with patch(
            "via_api.services.videos.VideoRepository.create",
            side_effect=RuntimeError("dynamo down"),
        ):
            response = client.post("/videos", json={"filename": "y.mp4"}, headers=USER)
            assert response.status_code == 500, response.text

    def test_presign_failure_after_write_maps_to_500(self, client: TestClient) -> None:
        """S3 presign failure after DynamoDB success -> 500 (no silent 202)."""
        with patch(
            "via_api.storage.Presigner.create_upload_target",
            side_effect=ClientError({"Error": {"Code": "X", "Message": "x"}}, "Put"),
        ):
            response = _post(client, {"filename": "presign_fail.mp4"})
            assert response.status_code == 500, response.text
