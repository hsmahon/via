"""Agent service tests: harness wired over HTTP with moto-backed state."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient
from via_agent.main import create_app
from via_agent.settings import Settings


@pytest.fixture()
def client(monkeypatch: pytest.MonkeyPatch) -> Iterator[tuple[TestClient, dict[str, str]]]:
    """Provide an agent app backed by moto DynamoDB and local implementations.

    Seeds one owned video directly through the repository, mirroring what
    the API service would have produced.

    Args:
        monkeypatch: Environment patcher.

    Yields:
        Tuple of (client, seeded video payload).
    """
    import uuid

    from moto import mock_aws

    with mock_aws():
        from via_db.client import get_dynamodb_resource
        from via_db.tables import create_table
        from via_db.videos import VideoRepository

        table_name = "via-agent-test"
        create_table(get_dynamodb_resource(region_name="us-east-1"), table_name)
        repo = VideoRepository(get_dynamodb_resource(region_name="us-east-1").Table(table_name))
        video_id = uuid.uuid4().hex
        repo.create(video_id=video_id, user_id="user-1", filename="demo.mp4", duration=15.0)
        settings = Settings(table_name=table_name, model_backend="local", env="local")
        _ = monkeypatch  # settings passed explicitly; no env dependence
        client = TestClient(create_app(settings))
        yield client, {"video_id": video_id}


def test_health(client: tuple[TestClient, Any]) -> None:
    """GET /health reports ok."""
    c, _ = client
    assert c.get("/health").json()["status"] == "ok"


def test_invoke_answers_for_owned_video(client: tuple[TestClient, dict[str, str]]) -> None:
    """Full loop completes locally: prompt → metadata tool → final answer."""
    c, video = client
    response = c.post(
        "/agent/invoke",
        json={"message": "What is this video?", "video_id": video["video_id"]},
        headers={"X-User-Id": "user-1"},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["answer"]
    assert any(step["kind"] == "tool" for step in body["steps"])
    assert body["usage"]["input_tokens"]


def test_invoke_denies_non_owner(client: tuple[TestClient, dict[str, str]]) -> None:
    """Another user cannot invoke the agent on someone else's video."""
    c, video = client
    response = c.post(
        "/agent/invoke",
        json={"message": "hi", "video_id": video["video_id"]},
        headers={"X-User-Id": "intruder"},
    )
    assert response.status_code == 403
    assert response.json()["detail"]["category"] == "AUTHORIZATION_ERROR"


def test_trace_endpoint_returns_spans(client: tuple[TestClient, dict[str, str]]) -> None:
    """Recorded spans are retrievable for a completed run."""
    c, video = client
    run = c.post(
        "/agent/invoke",
        json={"message": "What is this video?", "video_id": video["video_id"]},
        headers={"X-User-Id": "user-1"},
    ).json()
    trace = c.get(f"/agent/runs/{run['run_id']}/trace").json()
    names = {s["name"] for s in trace["spans"]}
    assert {"agent.run", "prompt.resolve", "model.invoke"} <= names


def test_bedrock_backend_requires_model_id(monkeypatch: pytest.MonkeyPatch) -> None:
    """Selecting Bedrock without a Pegasus id fails fast at wiring time."""
    from via_agent.wiring import build_context
    from via_harness import ErrorCategory, HarnessError

    for key, value in (
        ("AWS_ACCESS_KEY_ID", "testing"),
        ("AWS_SECRET_ACCESS_KEY", "testing"),
        ("AWS_DEFAULT_REGION", "us-east-1"),
    ):
        monkeypatch.setenv(key, value)
    with pytest.raises(HarnessError) as err:
        build_context(Settings(model_backend="bedrock", pegasus_model_id=None))
    assert err.value.category is ErrorCategory.INTERNAL_ERROR
