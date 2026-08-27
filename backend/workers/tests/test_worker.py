"""Worker tests: EventBridge parsing, HTTP boundary, and idempotent transitions."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient
from via_worker_video_processing.events import parse_eventbridge_event, parse_video_id
from via_worker_video_processing.main import create_app
from via_worker_video_processing.settings import WorkerSettings

EVENTBRIDGE_EVENT = {
    "source": "aws.s3",
    "detail-type": "Object Created",
    "detail": {
        "bucket": {"name": "via-videos"},
        "object": {"key": "videos/user-1/v-123/clip.mp4", "size": 1024},
    },
}

EVENTBRIDGE_FLAT_BUCKET = {
    "source": "aws.s3",
    "detail-type": "Object Created",
    "detail": {
        "bucket": "via-videos",
        "object": {"key": "videos/user-1/v-123/clip.mp4", "size": 1024},
    },
}

EVENTBRIDGE_FLAT_KEY = {
    "source": "aws.s3",
    "detail-type": "Object Created",
    "detail": {
        "bucket": {"name": "via-videos"},
        "key": "videos/user-1/v-123/clip.mp4",
        "size": 1024,
    },
}

MINIO_RECORDS_EVENT = {
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

MINIO_FLAT_EVENT = {
    "EventName": "s3:ObjectCreated:Put",
    "Bucket": "via-videos",
    "Key": "videos%2Fu1%2Fv9%2Fa.mp4",
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
            "bucket": {"name": "via-videos"},
            "object": {"key": f"videos/user-1/{video_id}/clip.mp4", "size": 1024},
        },
    }


class TestParseEventbridgeEvent:
    """EventBridge validation accepts the production shape and rejects the rest."""

    def test_valid_event_extracts_video_id(self) -> None:
        """Valid EventBridge S3 Object Created event extracts correct video_id."""
        event = parse_eventbridge_event(EVENTBRIDGE_EVENT)
        assert event.source == "aws.s3"
        assert event.detail.bucket == "via-videos"
        assert event.detail.key == "videos/user-1/v-123/clip.mp4"
        assert event.detail.size == 1024
        assert event.parse_video_id() == "v-123"
        assert parse_video_id(event.detail.key) == "v-123"

    def test_flat_bucket_variant(self) -> None:
        """Flattened bucket string variant parses identically."""
        event = parse_eventbridge_event(EVENTBRIDGE_FLAT_BUCKET)
        assert event.detail.bucket == "via-videos"
        assert event.parse_video_id() == "v-123"

    def test_flat_key_variant(self) -> None:
        """Flattened detail.key variant (no object nesting) parses."""
        event = parse_eventbridge_event(EVENTBRIDGE_FLAT_KEY)
        assert event.detail.bucket == "via-videos"
        assert event.detail.key == "videos/user-1/v-123/clip.mp4"
        assert event.parse_video_id() == "v-123"

    def test_url_encoded_key_decoded(self) -> None:
        """Percent-encoded keys are decoded before video_id extraction."""
        payload = {
            "source": "aws.s3",
            "detail-type": "Object Created",
            "detail": {
                "bucket": {"name": "via-videos"},
                "object": {"key": "videos%2Fu1%2Fv9%2Fa.mp4", "size": 100},
            },
        }
        event = parse_eventbridge_event(payload)
        assert event.detail.key == "videos/u1/v9/a.mp4"
        assert event.parse_video_id() == "v9"

    def test_non_video_key_returns_none(self) -> None:
        """Keys not matching videos/<user>/<video>/<file> return None."""
        assert parse_video_id("other/prefix/file.mp4") is None
        assert parse_video_id("videos/only-two") is None
        payload = {
            "source": "aws.s3",
            "detail-type": "Object Created",
            "detail": {
                "bucket": {"name": "via-videos"},
                "object": {"key": "other/prefix/file.mp4", "size": 1},
            },
        }
        event = parse_eventbridge_event(payload)
        assert event.parse_video_id() is None

    def test_unknown_shape_raises(self) -> None:
        """Payloads without detail raise ValueError."""
        with pytest.raises(ValueError, match="missing 'detail'"):
            parse_eventbridge_event({"hello": "world"})

    def test_malformed_missing_bucket_or_key_raises(self) -> None:
        """Missing bucket or key is rejected."""
        with pytest.raises(ValueError):
            parse_eventbridge_event(
                {
                    "source": "aws.s3",
                    "detail-type": "Object Created",
                    "detail": {"bucket": {"name": "via-videos"}},
                }
            )
        with pytest.raises(ValueError):
            parse_eventbridge_event(
                {
                    "source": "aws.s3",
                    "detail-type": "Object Created",
                    "detail": {"object": {"key": "videos/u1/v1/f.mp4"}},
                }
            )

    def test_malformed_detail_not_object_raises(self) -> None:
        """Non-object detail is rejected."""
        with pytest.raises(ValueError, match="detail must be an object"):
            parse_eventbridge_event(
                {"source": "aws.s3", "detail-type": "Object Created", "detail": "oops"}
            )

    def test_unexpected_detail_type_rejected(self) -> None:
        """Wrong detail-type is rejected."""
        with pytest.raises(ValueError, match="unexpected detail-type"):
            parse_eventbridge_event(
                {
                    "source": "aws.s3",
                    "detail-type": "Object Deleted",
                    "detail": {
                        "bucket": {"name": "via-videos"},
                        "object": {"key": "videos/u1/v1/f.mp4"},
                    },
                }
            )

    def test_minio_native_shapes_rejected(self) -> None:
        """MinIO-native shapes are rejected as malformed for the prod path."""
        with pytest.raises(ValueError):
            parse_eventbridge_event(MINIO_RECORDS_EVENT)
        with pytest.raises(ValueError):
            parse_eventbridge_event(MINIO_FLAT_EVENT)


class TestWorkerEndpoints:
    """HTTP receiver drives real state transitions with idempotency."""

    def test_health(self) -> None:
        """GET /health reports ok."""
        client = TestClient(create_app(WorkerSettings(table_name="unused")))
        assert client.get("/health").json()["status"] == "ok"

    def test_object_created_processes_video(self, seeded: tuple[Any, Any]) -> None:
        """UPLOADING → PROCESSING → PROCESSED."""
        repo, vid = seeded
        app = create_app(WorkerSettings(table_name="ignored"))
        app.dependency_overrides.clear()
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

    def test_duplicate_event_does_not_transition_again(self, seeded: tuple[Any, Any]) -> None:
        """Duplicate delivery after transition is safely ignored."""
        repo, vid = seeded
        from via_worker_video_processing.handlers import handle_object_created

        event = parse_eventbridge_event(_event_for(vid))
        first = handle_object_created(
            bucket=event.detail.bucket, key=event.detail.key, repository=repo
        )
        assert first.status == "processed"
        assert repo.get(vid).status.value == "PROCESSED"

        # Second delivery of the same Object Created event.
        second = handle_object_created(
            bucket=event.detail.bucket, key=event.detail.key, repository=repo
        )
        assert second.status == "ignored"
        assert repo.get(vid).status.value == "PROCESSED"

    def test_duplicate_via_http_is_idempotent(self, seeded: tuple[Any, Any]) -> None:
        """Duplicate POST /events is idempotent and does not re-transition."""
        repo, vid = seeded
        app = create_app(WorkerSettings(table_name="ignored"))
        from via_worker_video_processing.main import _repository

        _repository.cache_clear()
        import via_worker_video_processing.main as worker_main

        worker_main._repository = lambda *a, **k: repo  # type: ignore[assignment]
        try:
            client = TestClient(app)
            first = client.post("/events", json=_event_for(vid))
            assert first.status_code == 200
            assert first.json()["status"] == "processed"
            second = client.post("/events", json=_event_for(vid))
            assert second.status_code == 200
            assert second.json()["status"] == "ignored"
            assert repo.get(vid).status.value == "PROCESSED"
        finally:
            worker_main._repository = _repository

    @pytest.mark.parametrize("target_status", ["PROCESSING", "PROCESSED", "FAILED"])
    def test_already_transitioned_cannot_go_back_to_processing(
        self, seeded: tuple[Any, Any], target_status: str
    ) -> None:
        """PROCESSING/PROCESSED/FAILED cannot be moved back to PROCESSING."""
        from via_db import VideoStatus
        from via_worker_video_processing.handlers import handle_object_created

        repo, vid = seeded
        # Drive the seeded UPLOADING video to the target state.
        if target_status == "PROCESSING":
            repo.mark_processing(vid)
        elif target_status == "PROCESSED":
            repo.mark_processing(vid)
            repo.update_status(vid, VideoStatus.PROCESSED)
        elif target_status == "FAILED":
            repo.mark_processing(vid)
            repo.update_status(vid, VideoStatus.FAILED)
        assert repo.get(vid).status.value == target_status

        event = parse_eventbridge_event(_event_for(vid))
        outcome = handle_object_created(
            bucket=event.detail.bucket, key=event.detail.key, repository=repo
        )
        assert outcome.status == "ignored"
        assert repo.get(vid).status.value == target_status

    def test_missing_video_handled_as_ignored(self) -> None:
        """Events for unknown videos are acknowledged as ignored."""
        from moto import mock_aws
        from via_db.client import get_dynamodb_resource
        from via_db.tables import create_table
        from via_db.videos import VideoRepository
        from via_worker_video_processing.handlers import handle_object_created

        with mock_aws():
            create_table(get_dynamodb_resource(region_name="us-east-1"), "t")
            repo = VideoRepository(get_dynamodb_resource(region_name="us-east-1").Table("t"))
            event = parse_eventbridge_event(EVENTBRIDGE_EVENT)
            outcome = handle_object_created(
                bucket=event.detail.bucket, key=event.detail.key, repository=repo
            )
            assert outcome.status == "ignored"
            assert outcome.video_id == "v-123"

    def test_non_video_key_is_ignored(self, seeded: tuple[Any, Any]) -> None:
        """Keys not matching the video convention are ignored without transition."""
        repo, _ = seeded
        from via_worker_video_processing.handlers import handle_object_created

        outcome = handle_object_created(
            bucket="via-videos", key="other/prefix/file.mp4", repository=repo
        )
        assert outcome.status == "ignored"
        assert outcome.video_id is None

    def test_malformed_event_returns_400(self, seeded: tuple[Any, Any]) -> None:
        """Malformed EventBridge payload is rejected with 400."""
        repo, _ = seeded
        app = create_app(WorkerSettings(table_name="ignored"))
        from via_worker_video_processing.main import _repository

        _repository.cache_clear()
        import via_worker_video_processing.main as worker_main

        worker_main._repository = lambda *a, **k: repo  # type: ignore[assignment]
        try:
            client = TestClient(app)
            response = client.post("/events", json={"hello": "world"})
            assert response.status_code == 400
            # MinIO Records shape is also rejected on the prod path.
            response2 = client.post("/events", json=MINIO_RECORDS_EVENT)
            assert response2.status_code == 400
            response3 = client.post("/events/minio", json=MINIO_RECORDS_EVENT)
            assert response3.status_code == 400
        finally:
            worker_main._repository = _repository

    def test_hooks_enabled_with_mock_processes_video(self, seeded: tuple[Any, Any]) -> None:
        """With hooks on, mock Transcribe/Pegasus completes the video."""
        repo, vid = seeded
        from via_worker_video_processing.handlers import handle_object_created

        event = parse_eventbridge_event(_event_for(vid))
        outcome = handle_object_created(
            bucket=event.detail.bucket,
            key=event.detail.key,
            repository=repo,
            hooks_enabled=True,
        )
        assert outcome.status == "processed"
        assert repo.get(vid).status.value == "PROCESSED"

    def test_hooks_enabled_marks_failed(
        self, seeded: tuple[Any, Any], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """With hooks on, a failing Transcribe marks the video FAILED."""
        repo, vid = seeded
        from via_worker_video_processing import handlers as handlers_mod
        from via_worker_video_processing.handlers import handle_object_created

        def _fail(*_a: object, **_kw: object) -> None:
            raise NotImplementedError("Amazon Transcribe integration is scheduled for v0.2")

        monkeypatch.setattr(handlers_mod, "transcribe", _fail)
        event = parse_eventbridge_event(_event_for(vid))
        outcome = handle_object_created(
            bucket=event.detail.bucket,
            key=event.detail.key,
            repository=repo,
            hooks_enabled=True,
        )
        assert outcome.status == "failed"
        assert outcome.detail
        assert repo.get(vid).status.value == "FAILED"

    def test_mock_failure_marks_failed(
        self, seeded: tuple[Any, Any], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Injected mock failure marks the video FAILED."""
        repo, vid = seeded
        from via_worker_video_processing import handlers as handlers_mod
        from via_worker_video_processing.handlers import handle_object_created

        def _fail(*_a: object, **_kw: object) -> None:
            raise RuntimeError("mock transcribe failure (injected)")

        monkeypatch.setattr(handlers_mod, "transcribe", _fail)
        event = parse_eventbridge_event(_event_for(vid))
        outcome = handle_object_created(
            bucket=event.detail.bucket,
            key=event.detail.key,
            repository=repo,
            hooks_enabled=True,
        )
        assert outcome.status == "failed"
        assert repo.get(vid).status.value == "FAILED"

    def test_unknown_video_ignored(self) -> None:
        """Events for unknown videos are acknowledged as ignored (compat)."""
        from moto import mock_aws
        from via_db.client import get_dynamodb_resource
        from via_db.tables import create_table
        from via_db.videos import VideoRepository
        from via_worker_video_processing.handlers import handle_object_created

        with mock_aws():
            create_table(get_dynamodb_resource(region_name="us-east-1"), "t")
            repo = VideoRepository(get_dynamodb_resource(region_name="us-east-1").Table("t"))
            event = parse_eventbridge_event(EVENTBRIDGE_EVENT)
            outcome = handle_object_created(
                bucket=event.detail.bucket, key=event.detail.key, repository=repo
            )
            assert outcome.status == "ignored"


class TestV02MockedProcessing:
    """V0.2: deterministic mocks with dependency boundaries, no AWS calls."""

    def test_transcribe_deterministic_mock(self) -> None:
        """Transcribe returns deterministic job_name and transcript_key."""
        from via_worker_video_processing.transcribe import transcribe

        r1 = transcribe(bucket="via-videos", key="videos/u1/v-abc/clip.mp4")
        r2 = transcribe(bucket="via-videos", key="videos/u1/v-abc/clip.mp4")
        assert r1.job_name == r2.job_name == "mock-transcribe-v-abc"
        assert r1.transcript_key == "transcripts/v-abc/transcript.json"
        assert r1.status == "COMPLETED"
        r3 = transcribe(bucket="via-videos", key="videos/u1/v-abc/other.mp4")
        assert r3.job_name == r1.job_name

        # Non-video key still deterministic via hash suffix.
        r4 = transcribe(bucket="b", key="other/prefix/file.mp4")
        r5 = transcribe(bucket="b", key="other/prefix/file.mp4")
        assert r4.job_name == r5.job_name
        assert r4.transcript_key is None or r4.transcript_key.startswith("transcripts/")

    def test_pegasus_deterministic_mock(self) -> None:
        """analyze_with_pegasus returns deterministic answer."""
        from via_worker_video_processing.pegasus import analyze_with_pegasus

        a1 = analyze_with_pegasus(bucket="b", key="videos/u1/v1/clip.mp4")
        a2 = analyze_with_pegasus(bucket="b", key="videos/u1/v1/clip.mp4")
        assert a1.answer == a2.answer
        assert "s3://b/videos/u1/v1/clip.mp4" in a1.answer

        a3 = analyze_with_pegasus(bucket="b", key="videos/u1/v1/clip.mp4", question="what?")
        assert "what?" in a3.answer

    def test_handler_orchestrates_both_on_valid_event(self, seeded: tuple[Any, Any]) -> None:
        """Valid EventBridge event triggers both transcribe and pegasus via boundaries."""
        repo, vid = seeded
        from via_worker_video_processing.handlers import handle_object_created
        from via_worker_video_processing.pegasus import PegasusAnalysis
        from via_worker_video_processing.transcribe import TranscriptionResult

        event = parse_eventbridge_event(_event_for(vid))
        calls: list[tuple[str, str, str]] = []

        def _mock_transcribe(*, bucket: str, key: str) -> TranscriptionResult:
            calls.append(("transcribe", bucket, key))
            return TranscriptionResult(
                job_name="mock-job", transcript_key="transcripts/x.json", status="COMPLETED"
            )

        def _mock_analyze(*, bucket: str, key: str, question: str | None = None) -> PegasusAnalysis:
            _ = question
            calls.append(("pegasus", bucket, key))
            return PegasusAnalysis(answer="ok")

        outcome = handle_object_created(
            bucket=event.detail.bucket,
            key=event.detail.key,
            repository=repo,
            hooks_enabled=True,
            transcribe_fn=_mock_transcribe,
            analyze_fn=_mock_analyze,
        )
        assert outcome.status == "processed"
        assert repo.get(vid).status.value == "PROCESSED"
        assert calls == [
            ("transcribe", event.detail.bucket, event.detail.key),
            ("pegasus", event.detail.bucket, event.detail.key),
        ]

    def test_handler_transcribe_failure_marks_failed(self, seeded: tuple[Any, Any]) -> None:
        """Transcribe failure via boundary marks video FAILED."""
        repo, vid = seeded
        from via_worker_video_processing.handlers import handle_object_created

        event = parse_eventbridge_event(_event_for(vid))

        def _fail_transcribe(*, bucket: str, key: str) -> None:
            _ = (bucket, key)
            raise RuntimeError("transcribe boom")

        outcome = handle_object_created(
            bucket=event.detail.bucket,
            key=event.detail.key,
            repository=repo,
            hooks_enabled=True,
            transcribe_fn=_fail_transcribe,
        )
        assert outcome.status == "failed"
        assert "transcribe boom" in (outcome.detail or "")
        assert repo.get(vid).status.value == "FAILED"

    def test_handler_pegasus_failure_marks_failed(self, seeded: tuple[Any, Any]) -> None:
        """Pegasus failure via boundary marks video FAILED (after transcribe)."""
        repo, vid = seeded
        from via_worker_video_processing.handlers import handle_object_created
        from via_worker_video_processing.transcribe import TranscriptionResult

        event = parse_eventbridge_event(_event_for(vid))

        def _ok_transcribe(*, bucket: str, key: str) -> TranscriptionResult:
            _ = (bucket, key)
            return TranscriptionResult(job_name="mock", transcript_key=None, status="COMPLETED")

        def _fail_analyze(*, bucket: str, key: str, question: str | None = None) -> None:
            _ = (bucket, key, question)
            raise RuntimeError("pegasus boom")

        outcome = handle_object_created(
            bucket=event.detail.bucket,
            key=event.detail.key,
            repository=repo,
            hooks_enabled=True,
            transcribe_fn=_ok_transcribe,
            analyze_fn=_fail_analyze,
        )
        assert outcome.status == "failed"
        assert "pegasus boom" in (outcome.detail or "")
        assert repo.get(vid).status.value == "FAILED"

    def test_handler_does_not_call_processing_when_hooks_disabled(
        self, seeded: tuple[Any, Any]
    ) -> None:
        """When hooks are disabled, processing boundaries are not invoked."""
        repo, vid = seeded
        from via_worker_video_processing.handlers import handle_object_created

        event = parse_eventbridge_event(_event_for(vid))

        def _fail_transcribe(*, bucket: str, key: str) -> None:
            _ = (bucket, key)
            raise AssertionError("should not be called")

        def _fail_analyze(*, bucket: str, key: str, question: str | None = None) -> None:
            _ = (bucket, key, question)
            raise AssertionError("should not be called")

        outcome = handle_object_created(
            bucket=event.detail.bucket,
            key=event.detail.key,
            repository=repo,
            hooks_enabled=False,
            transcribe_fn=_fail_transcribe,
            analyze_fn=_fail_analyze,
        )
        assert outcome.status == "processed"
        assert repo.get(vid).status.value == "PROCESSED"
