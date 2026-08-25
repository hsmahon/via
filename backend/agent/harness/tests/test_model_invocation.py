"""Model invocation tests (required area 5)."""

from __future__ import annotations

import json
from typing import Any

import pytest
from via_harness import (
    HarnessError,
    ModelMessage,
    ModelRequest,
    ModelRole,
    StopReason,
    ToolCallRequest,
)
from via_harness.model.bedrock import BedrockConverseClient
from via_harness.model.local import LocalModelClient
from via_harness.model.types import ModelToolSpec


def _request(**overrides: Any) -> ModelRequest:
    """Build a minimal model request.

    Args:
        overrides: Field overrides applied to the defaults.

    Returns:
        A single-user-message request.
    """
    fields: dict[str, Any] = {
        "messages": [ModelMessage(role=ModelRole.USER, content="what is in this video?")]
    }
    fields.update(overrides)
    return ModelRequest(**fields)


class TestLocalModelClient:
    """Deterministic behavior of the local client."""

    def test_scripted_responses_return_in_order(self) -> None:
        """Scripted responses pop FIFO regardless of request contents."""
        first = _scripted_response("one")
        second = _scripted_response("two")
        client = LocalModelClient([first, second])
        assert client.invoke(_request()).text == "one"
        assert client.invoke(_request()).text == "two"

    def test_heuristic_calls_first_tool_then_finalizes(self) -> None:
        """Without scripts: tool call first round, final JSON second."""
        spec = ModelToolSpec(
            name="get_video_metadata",
            description="d",
            parameters_json_schema={"type": "object", "properties": {}},
        )
        client = LocalModelClient()
        round1 = client.invoke(_request(tools=[spec]))
        assert round1.stop_reason is StopReason.TOOL_USE
        assert round1.tool_calls[0].name == "get_video_metadata"

        follow_up = _request(
            tools=[spec],
            messages=[
                ModelMessage(role=ModelRole.USER, content="q"),
                ModelMessage(
                    role=ModelRole.TOOL,
                    tool_call_id="x",
                    content=json.dumps(
                        {
                            "type": "tool_result",
                            "payload": {
                                "video": {"filename": "a.mp4", "video_id": "v1", "duration": 12.5}
                            },
                        }
                    ),
                ),
            ],
        )
        round2 = client.invoke(follow_up)
        assert round2.stop_reason is StopReason.END_TURN
        body = json.loads(round2.text or "{}")
        assert body["type"] == "final"
        assert body["answer"]
        assert body["citations"][0]["video_id"] == "v1"

    def test_injected_failure_raises_after_scripts(self) -> None:
        """The injected error surfaces once the script queue empties."""
        failure = HarnessError(
            __import__("via_harness").ErrorCategory.MODEL_ERROR, "provider down", retryable=True
        )
        client = LocalModelClient(fail_after_scripts=failure)
        with pytest.raises(HarnessError) as err:
            client.invoke(_request())
        assert err.value.retryable is True


class _StubBedrock:
    """Minimal stand-in for the boto3 bedrock-runtime client."""

    def __init__(self, payload: dict[str, Any]) -> None:
        """Initialize with the canned response.

        Args:
            payload: Dictionary returned by ``converse``.
        """
        self._payload = payload

    def converse(self, **kwargs: Any) -> dict[str, Any]:
        """Return the canned payload.

        Args:
            kwargs: Request parameters (captured for assertions).

        Returns:
            The configured response dictionary.
        """
        self.last_params = kwargs  # type: ignore[attr-defined]
        return self._payload


class TestBedrockConverseClient:
    """Mapping between harness requests and the Bedrock Converse API."""

    def test_builds_tool_config_and_parses_text_response(self) -> None:
        """Tools map to toolConfig; text/usage normalize into the response."""
        stub = _StubBedrock(
            {
                "output": {"message": {"content": [{"text": "hello"}]}},
                "stopReason": "end_turn",
                "usage": {"inputTokens": 11, "outputTokens": 7},
            }
        )
        client = BedrockConverseClient(stub, model_id="test-model")  # type: ignore[arg-type]
        spec = ModelToolSpec(name="t1", description="d", parameters_json_schema={"type": "object"})
        response = client.invoke(_request(tools=[spec], system="be brief"))
        assert response.text == "hello"
        assert response.usage is not None and response.usage.input_tokens == 11
        params = stub.last_params
        assert params["modelId"] == "test-model"
        assert params["toolConfig"]["tools"][0]["toolSpec"]["name"] == "t1"
        assert params["system"][0]["text"] == "be brief"

    def test_parses_tool_use_blocks(self) -> None:
        """Tool-use blocks normalize into typed tool-call requests."""
        stub = _StubBedrock(
            {
                "output": {
                    "message": {
                        "content": [
                            {
                                "toolUse": {
                                    "toolUseId": "id-1",
                                    "name": "echo",
                                    "input": {"text": "hey"},
                                }
                            }
                        ]
                    }
                },
                "stopReason": "tool_use",
                "usage": {},
            }
        )
        client = BedrockConverseClient(stub)  # type: ignore[arg-type]
        response = client.invoke(_request())
        assert response.stop_reason is StopReason.TOOL_USE
        assert response.tool_calls == [
            ToolCallRequest(call_id="id-1", name="echo", arguments={"text": "hey"})
        ]


def _scripted_response(text: str):  # type: ignore[no-untyped-def]
    """Build a scripted END_TURN response.

    Args:
        text: Text to embed.

    Returns:
        ModelResponse carrying the text.
    """
    from via_harness import ModelResponse

    return ModelResponse(text=text, stop_reason=StopReason.END_TURN)
