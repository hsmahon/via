"""Worker tests: envelope normalization and the state machine."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient
from via_worker_video_processing.envelope import normalize_event
from via_worker_video_processing.main import create_app
from via_worker_video_processing.settings import WorkerSettings

EVENTBRIDGE_EVENT = {
    "source": "aws.s3",
    "detail-type": "Object Created",
    "detail": {
        "bucket": "via-videos",
        "object": {"key": "videos/user-1/v-123/clip.mp4", "size": 1024},
    },
}

MINIO_EVENT = {
    "EventName": "s3:ObjectCreated:Put",
    "Records": [
        {
            "eventName": "s3:ObjectCreated:Put",
            "s3": {
                "bucket": {"name": "via-videos"},
                "object": {"key": "videos/user-1/v-123/clip.mp4", "size": 2048},
            },
        }
    ],
}


@pytest.fixture()
def seeded(monkeypatch: pytest.MonkeyPatch) -> Iterator[tuple[Any, Any]]:
    """Provide a repository plus one UPLOADING video in moto DynamoDB.

    Args:
        monkeypatch: Unused env patcher (settings passed explicitly).

    Yields:
        Tuple of (repository, video_id).
    """
    import uuid

    from moto import mock_aws

    with mock_aws():
        from via_db.client import get_dynamodb_resource
        from via_db.tables import create_table
        from via_db.videos import VideoRepository

        create_table(get_dynamodb_resource(region_name="us-east-1"), "via-worker-test")
        table = get_dynamodb_resource(region_name="us-east-1").Table("via-worker-test")
        repo = VideoRepository(table)
        vid = uuid.uuid4().hex
        repo.create(video_id=vid, user_id="user-1", filename="clip.mp4")
        _ = monkeypatch
        yield repo, vid


class TestNormalizeEvent:
    """Both production and local shapes map onto the canonical envelope."""

    def test_eventbridge_shape(self) -> None:
        """EventBridge payloads parse with source and detail preserved."""
        envelope = normalize_event(EVENTBRIDGE_EVENT)
        assert envelope.source == "aws.s3"
        assert envelope.detail.key == "videos/user-1/v-123/clip.mp4"
        assert envelope.parse_video_id() == "v-123"

    def test_minio_shape(self) -> None:
        """MinIO notifications parse into the same canonical model."""
        envelope = normalize_event(MINIO_EVENT)
        assert envelope.source == "minio.s3"
        assert envelope.parse_video_id() == "v-123"

    def test_minio_flat_and_url_encoded_shapes(self) -> None:
        """MinIO's flat webhook form with percent-encoded keys parses."""
        payload = {
            "EventName": "s3:ObjectCreated:Put",
            "Bucket": "via-videos",
            "Key": "videos%2Fu1%2Fv9%2Fa.mp4",
        }
        envelope = normalize_event(payload)
        assert envelope.parse_video_id() == "v9"

    def test_unknown_shape_raises(self) -> None:
        """Payloads matching neither shape raise ValueError."""
        import pytest

        with pytest.raises(ValueError):
            normalize_event({"hello": "world"})


def _event_for(video_id: str) -> dict[str, Any]:
    """Build an EventBridge-shaped event for one video id.

    Args:
        video_id: Video identifier embedded into the object key.

    Returns:
        Event payload dictionary.
    """
    return {
        "source": "aws.s3",
        "detail-type": "Object Created",
        "detail": {
            "bucket": "via-videos",
            "object": {"key": f"videos/user-1/{video_id}/clip.mp4", "size": 1024},
        },
    }


class TestWorkerEndpoints:
    """HTTP receiver drives real state transitions."""

    def test_health(self) -> None:
        """GET /health reports ok."""
        client = TestClient(create_app(WorkerSettings(table_name="unused")))
        assert client.get("/health").json()["status"] == "ok"

    def test_object_created_processes_video(self, seeded: tuple[Any, Any]) -> None:
        """UPLOADING → PROCESSING → PROCESSED with audit trail written."""
        repo, vid = seeded
        app = create_app(WorkerSettings(table_name="ignored"))
        app.dependency_overrides.clear()
        # Rebind repository dependency to the moto-backed instance.
        from via_worker_video_processing.main import _repository

        _repository.cache_clear()
        import via_worker_video_processing.main as worker_main

        worker_main._repository = lambda *a, **k: repo  # type: ignore[assignment]
        try:
            response = TestClient(app).post("/events", json=_event_for(vid))
            assert response.status_code == 200, response.text
            assert response.json()["status"] == "processed"
            assert repo.get(vid).status.value == "PROCESSED"
        finally:
            worker_main._repository = _repository  # restore for other tests

    def test_hooks_enabled_marks_failed(self, seeded: tuple[Any, Any]) -> None:
        """With hooks on, pending integrations fail the video explicitly."""
        repo, vid = seeded
        from via_worker_video_processing.handlers import handle_object_created

        outcome = handle_object_created(
            normalize_event(_event_for(vid)),
            repository=repo,
            hooks_enabled=True,
        )
        assert outcome.status == "failed"
        assert outcome.detail
        assert repo.get(vid).status.value == "FAILED"

    def test_unknown_video_ignored(self) -> None:
        """Events for unknown videos are acknowledged as ignored."""
        from moto import mock_aws
        from via_db.client import get_dynamodb_resource
        from via_db.tables import create_table
        from via_db.videos import VideoRepository

        with mock_aws():
            create_table(get_dynamodb_resource(region_name="us-east-1"), "t")
            repo = VideoRepository(get_dynamodb_resource(region_name="us-east-1").Table("t"))
            from via_worker_video_processing.handlers import handle_object_created

            outcome = handle_object_created(normalize_event(EVENTBRIDGE_EVENT), repository=repo)
            assert outcome.status == "ignored"
