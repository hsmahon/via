"""Video repository and lifecycle tests (v0.1: single via-table, no audit/analytics)."""

from __future__ import annotations

import pytest
from via_db import InvalidTransition, VideoAlreadyExists, VideoNotFound, VideoRecord, VideoStatus
from via_db.errors import ViaDbError
from via_db.keys import parse_video_pk, video_pk


class TestKeys:
    """Key builder round-trips."""

    def test_parse_video_pk_round_trip(self) -> None:
        """parse_video_pk inverts video_pk."""
        assert parse_video_pk(video_pk("abc")) == "abc"

    def test_parse_rejects_foreign_pk(self) -> None:
        """Non-video partition keys are rejected loudly."""
        with pytest.raises(ValueError):
            parse_video_pk("USER#u1")


class TestVideoLifecycle:
    """Create/get/list plus the explicit status machine."""

    def test_create_and_get(self, videos) -> None:  # type: ignore[no-untyped-def]
        """A created video is retrievable with identical fields."""
        record = videos.create(
            video_id="v1",
            user_id="u1",
            filename="clip.mp4",
            duration=12.5,
            s3_bucket="b",
            s3_key="k",
        )
        fetched = videos.get("v1")
        assert fetched == record
        assert fetched is not None
        assert fetched.status is VideoStatus.UPLOADING

    def test_create_writes_to_via_table_only(self, ddb_table, videos) -> None:  # type: ignore[no-untyped-def]
        """Creation writes exactly one META item to via-table."""
        videos.create(video_id="only-meta", user_id="u1", filename="a.mp4")
        items = list(ddb_table.scan().get("Items", []))
        # Only the META item; no AUDIT# or ANALYTICS# rows.
        assert len(items) == 1
        item = items[0]
        assert item["sk"] == "META"
        assert item["pk"] == video_pk("only-meta")
        assert item["status"] == VideoStatus.UPLOADING.value

    def test_duplicate_create_does_not_overwrite(self, videos, ddb_table) -> None:  # type: ignore[no-untyped-def]
        """Id collisions raise and do not mutate the original row."""
        original = videos.create(video_id="dup2", user_id="u1", filename="a.mp4")
        with pytest.raises(VideoAlreadyExists):
            videos.create(video_id="dup2", user_id="u2", filename="b.mp4")
        fetched = videos.get("dup2")
        assert fetched == original
        assert fetched.user_id == "u1"
        assert fetched.filename == "a.mp4"

    def test_get_missing_returns_none(self, videos) -> None:  # type: ignore[no-untyped-def]
        """Unknown ids return None instead of raising."""
        assert videos.get("ghost") is None

    def test_duplicate_create_raises(self, videos) -> None:  # type: ignore[no-untyped-def]
        """Id collisions raise VideoAlreadyExists (conditional put)."""
        videos.create(video_id="dup", user_id="u1", filename="a.mp4")
        with pytest.raises(VideoAlreadyExists):
            videos.create(video_id="dup", user_id="u2", filename="b.mp4")

    def test_filename_with_path_rejected(self, videos) -> None:  # type: ignore[no-untyped-def]
        """Path separators in filenames are rejected at the boundary."""
        with pytest.raises(ValueError):
            videos.create(video_id="evil", user_id="u1", filename="../../etc/passwd")

    def test_list_by_user_newest_first(self, videos) -> None:  # type: ignore[no-untyped-def]
        """GSI listing returns the newest video first."""
        videos.create(video_id="older", user_id="u1", filename="old.mp4")
        videos.create(video_id="newer", user_id="u1", filename="new.mp4")
        listed = videos.list_by_user("u1")
        assert [r.video_id for r in listed] == ["newer", "older"]

    def test_list_by_user_uses_gsi(self, videos) -> None:  # type: ignore[no-untyped-def]
        """GSI query returns only the requesting user's videos."""
        videos.create(video_id="v-a", user_id="alice", filename="a.mp4")
        videos.create(video_id="v-b", user_id="bob", filename="b.mp4")
        alice = videos.list_by_user("alice")
        bob = videos.list_by_user("bob")
        assert [r.video_id for r in alice] == ["v-a"]
        assert [r.video_id for r in bob] == ["v-b"]

    def test_happy_path_transitions(self, videos) -> None:  # type: ignore[no-untyped-def]
        """UPLOADING → PROCESSING → PROCESSED is permitted end-to-end."""
        videos.create(video_id="flow", user_id="u1", filename="f.mp4")
        videos.update_status("flow", VideoStatus.PROCESSING)
        final = videos.update_status("flow", VideoStatus.PROCESSED)
        assert final.status is VideoStatus.PROCESSED
        assert final.updated_at >= final.created_at

    def test_illegal_transition_rejected(self, videos) -> None:  # type: ignore[no-untyped-def]
        """UPLOADING → PROCESSED skips PROCESSING and must fail."""
        videos.create(video_id="jump", user_id="u1", filename="j.mp4")
        with pytest.raises(InvalidTransition):
            videos.update_status("jump", VideoStatus.PROCESSED)

    def test_transition_on_missing_video_raises_not_found(self, videos) -> None:  # type: ignore[no-untyped-def]
        """Transitions for unknown ids raise VideoNotFound."""
        with pytest.raises(VideoNotFound):
            videos.update_status("ghost", VideoStatus.PROCESSING)

    def test_delete_then_delete_conflict(self, videos) -> None:  # type: ignore[no-untyped-def]
        """DELETED is terminal; deleting twice raises InvalidTransition."""
        videos.create(video_id="del", user_id="u1", filename="d.mp4")
        deleted = videos.soft_delete("del")
        assert deleted.status is VideoStatus.DELETED
        with pytest.raises(InvalidTransition):
            videos.soft_delete("del")

    def test_delete_sets_status_without_audit_side_effects(self, videos, ddb_table) -> None:  # type: ignore[no-untyped-def]
        """Soft-delete flips status to DELETED and writes no audit rows."""
        videos.create(video_id="del2", user_id="u1", filename="d2.mp4")
        videos.soft_delete("del2")
        fetched = videos.get("del2")
        assert fetched is not None
        assert fetched.status is VideoStatus.DELETED
        items = list(ddb_table.scan().get("Items", []))
        # One META item, no AUDIT# rows.
        assert len(items) == 1
        assert items[0]["status"] == VideoStatus.DELETED.value
        assert not any(str(i.get("sk", "")).startswith("AUDIT#") for i in items)

    def test_failed_is_terminal_except_delete(self, videos) -> None:  # type: ignore[no-untyped-def]
        """FAILED allows no further transitions except deletion."""
        videos.create(video_id="fail", user_id="u1", filename="x.mp4")
        videos.update_status("fail", VideoStatus.PROCESSING)
        videos.update_status("fail", VideoStatus.FAILED)
        with pytest.raises(InvalidTransition):
            videos.update_status("fail", VideoStatus.PROCESSING)
        assert videos.soft_delete("fail").status is VideoStatus.DELETED


class TestEntityModel:
    """Serialization contract of the concrete entities."""

    def test_record_item_round_trip(self) -> None:
        """to_item/from_item preserve all typed fields."""
        record = VideoRecord(
            video_id="r1",
            user_id="u1",
            filename="x.mp4",
            duration=3.2,
            status=VideoStatus.PROCESSING,
            created_at="2026-01-01T00:00:00+00:00",
            updated_at="2026-01-01T00:00:00+00:00",
        )
        restored = VideoRecord.from_item(record.to_item())
        assert restored == record

    def test_no_audit_or_analytics_records_created(self, ddb_table, videos) -> None:  # type: ignore[no-untyped-def]
        """Lifecycle ops never leave ANALYTICS# or AUDIT# rows."""
        videos.create(video_id="clean", user_id="u1", filename="c.mp4")
        videos.update_status("clean", VideoStatus.PROCESSING)
        videos.update_status("clean", VideoStatus.PROCESSED)
        items = list(ddb_table.scan().get("Items", []))
        for item in items:
            assert not str(item.get("pk", "")).startswith("ANALYTICS#")
            assert not str(item.get("sk", "")).startswith("AUDIT#")
            assert not str(item.get("sk", "")).startswith("COUNTER#")

    def test_via_db_error_hierarchy(self) -> None:
        """All repository errors share the ViaDbError base."""
        for error_type in (InvalidTransition, VideoAlreadyExists, VideoNotFound):
            assert issubclass(error_type, ViaDbError)
