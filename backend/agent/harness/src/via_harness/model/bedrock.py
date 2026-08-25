"""Amazon Bedrock implementation of the :class:`ModelClient` port.

Uses the Bedrock ``converse`` / ``converse_stream`` APIs so the same client
serves text models and video-understanding models. The first production
target is **TwelveLabs Pegasus** served through Amazon Bedrock.

The module imports boto3 lazily: the base harness package has no hard AWS
dependency (install with ``via-harness[bedrock]``). Bedrock-specific types
never escape this module - callers see only :class:`ModelResponse`.
"""

from __future__ import annotations

import json
import time
from collections.abc import Iterator
from typing import TYPE_CHECKING, Any

from via_harness.errors import ErrorCategory, HarnessError
from via_harness.model.base import RetryPolicy
from via_harness.model.types import (
    ModelRequest,
    ModelResponse,
    ModelRole,
    StopReason,
    TokenUsage,
    ToolCallRequest,
)

if TYPE_CHECKING:  # pragma: no cover - boto3 is an optional dependency
    from mypy_boto3_bedrock_runtime import BedrockRuntimeClient

__all__ = ["DEFAULT_PEGASUS_MODEL_ID", "BedrockConverseClient"]

#: TwelveLabs Pegasus 1.2 on Bedrock (us-east-1 inference profile id).
#: Verify the exact id for your region/account before production use.
DEFAULT_PEGASUS_MODEL_ID = "us.twelvelabs.pegasus-1-2"

_STOP_REASON_MAP = {
    "end_turn": StopReason.END_TURN,
    "tool_use": StopReason.TOOL_USE,
    "max_tokens": StopReason.MAX_TOKENS,
}


class BedrockConverseClient:
    """Bedrock Runtime client implementing the harness model port."""

    def __init__(
        self,
        client: BedrockRuntimeClient,
        *,
        model_id: str = DEFAULT_PEGASUS_MODEL_ID,
        retry_policy: RetryPolicy | None = None,
    ) -> None:
        """Initialize the client.

        Args:
            client: A configured ``boto3`` ``bedrock-runtime`` client.
            model_id: Bedrock model or inference-profile id. Pegasus by default.
            retry_policy: Retry behavior for transient provider errors.
        """
        self._client = client
        self._model_id = model_id
        self._retry = (retry_policy or RetryPolicy()).validated()

    @classmethod
    def from_region(
        cls,
        region: str,
        *,
        model_id: str = DEFAULT_PEGASUS_MODEL_ID,
        retry_policy: RetryPolicy | None = None,
    ) -> BedrockConverseClient:
        """Create a client using ambient AWS credentials.

        Args:
            region: AWS region for the Bedrock runtime endpoint.
            model_id: Bedrock model or inference-profile id.
            retry_policy: Retry configuration.

        Returns:
            A ready-to-use client.

        Raises:
            HarnessError: If boto3 is unavailable (missing ``bedrock`` extra).
        """
        try:
            import boto3
        except ModuleNotFoundError as exc:  # pragma: no cover - environment guard
            raise HarnessError(
                ErrorCategory.INTERNAL_ERROR,
                "boto3 is required for the Bedrock model client; install via-harness[bedrock]",
                cause=exc,
            ) from exc
        return cls(
            boto3.client("bedrock-runtime", region_name=region),
            model_id=model_id,
            retry_policy=retry_policy,
        )

    # ------------------------------------------------------------------
    # ModelClient protocol
    # ------------------------------------------------------------------

    def invoke(
        self, request: ModelRequest, *, timeout_seconds: float | None = None
    ) -> ModelResponse:
        """Invoke the model through the Bedrock Converse API.

        Args:
            request: Normalized conversation request.
            timeout_seconds: Unused today (boto3 owns socket timeouts);
                accepted for protocol compatibility and future enforcement.

        Returns:
            Normalized response including token usage and cost estimate.

        Raises:
            HarnessError: ``TIMEOUT`` after retries exhausted for transient
                failures, otherwise ``MODEL_ERROR`` with the provider reason.
        """
        params = self._build_params(request)
        attempts = max(1, self._retry.max_attempts)
        last_error: HarnessError | None = None
        for attempt in range(attempts):
            if attempt:
                time.sleep(
                    self._retry.initial_backoff_seconds * (self._retry.multiplier ** (attempt - 1))
                )
            try:
                raw = self._client.converse(**params)
                return self._parse_response(raw)
            except Exception as exc:
                last_error = self._normalize(exc)
                if not last_error.retryable:
                    raise last_error from exc
        assert last_error is not None
        raise last_error

    def stream(
        self, request: ModelRequest, *, timeout_seconds: float | None = None
    ) -> Iterator[str]:
        """Stream text chunks via the Bedrock Converse Stream API.

        Tool-use streaming is not supported in v0.1: a streamed invocation is
        only valid when no tools are requested by the caller.

        Args:
            request: Normalized conversation request without tool round-trips.
            timeout_seconds: Unused; see :meth:`invoke`.

        Yields:
            Incremental text chunks as delivered by Bedrock.
        """
        params = self._build_params(request)
        params.pop("toolConfig", None)
        try:
            output = self._client.converse_stream(**params)
            for event in output.get("stream", []):
                chunk = event.get("contentBlockDelta", {}).get("delta", {}).get("text")
                if chunk:
                    yield chunk
        except Exception as exc:
            raise self._normalize(exc) from exc

    # ------------------------------------------------------------------
    # Mapping helpers (Bedrock shapes stay inside this class)
    # ------------------------------------------------------------------

    def _build_params(self, request: ModelRequest) -> dict[str, Any]:
        """Translate a harness request into Converse API parameters.

        Args:
            request: Normalized conversation request.

        Returns:
            Keyword arguments ready for ``converse`` / ``converse_stream``.
        """
        messages: list[dict[str, Any]] = []
        for message in request.messages:
            role = "user" if message.role in (ModelRole.USER, ModelRole.TOOL) else "assistant"
            content: dict[str, Any] = {"text": message.content}
            if message.role is ModelRole.TOOL:
                content = {
                    "toolResult": {
                        "toolUseId": message.tool_call_id or "",
                        "content": [{"json": json.loads(message.content or "{}")}],
                    }
                }
            if messages and messages[-1]["role"] == role:
                messages[-1]["content"].append(content)
            else:
                messages.append({"role": role, "content": [content]})

        params: dict[str, Any] = {
            "modelId": self._model_id,
            "messages": messages,
            "inferenceConfig": {"maxTokens": request.max_tokens},
        }
        if request.system:
            params["system"] = [{"text": request.system}]
        if request.temperature is not None:
            params["inferenceConfig"]["temperature"] = request.temperature
        if request.tools:
            params["toolConfig"] = {
                "tools": [
                    {
                        "toolSpec": {
                            "name": t.name,
                            "description": t.description,
                            "inputSchema": {"json": t.parameters_json_schema},
                        }
                    }
                    for t in request.tools
                ]
            }
        return params

    def _parse_response(self, raw: Any) -> ModelResponse:
        """Normalize a Converse response into the harness shape.

        Args:
            raw: Raw Bedrock response dictionary.

        Returns:
            Normalized :class:`ModelResponse`.
        """
        message = raw.get("output", {}).get("message", {})
        text_parts: list[str] = []
        tool_calls: list[ToolCallRequest] = []
        for block in message.get("content", []):
            if "text" in block:
                text_parts.append(block["text"])
            elif "toolUse" in block:
                use = block["toolUse"]
                tool_calls.append(
                    ToolCallRequest(
                        call_id=use["toolUseId"], name=use["name"], arguments=use.get("input") or {}
                    )
                )

        usage_raw = raw.get("usage", {})
        usage = (
            TokenUsage(
                input_tokens=usage_raw.get("inputTokens"),
                output_tokens=usage_raw.get("outputTokens"),
            )
            if usage_raw
            else None
        )
        stop = _STOP_REASON_MAP.get(str(raw.get("stopReason", "")).lower(), StopReason.ERROR)
        text = "".join(text_parts) or None
        if tool_calls and not text:
            # Normalize native tool-use into the harness wire contract so the
            # runner parses one uniform protocol regardless of provider.
            call = tool_calls[0]
            text = json.dumps(
                {"type": "tool_request", "tool": call.name, "arguments": call.arguments}
            )
        return ModelResponse(
            text=text,
            tool_calls=tool_calls,
            stop_reason=stop,
            usage=usage,
            model_id=self._model_id,
        )

    def _normalize(self, exc: BaseException) -> HarnessError:
        """Map a provider exception to the harness error taxonomy.

        Args:
            exc: Exception raised by boto3/botocore.

        Returns:
            ``HarnessError`` marked retryable for throttling/transient codes.
        """
        name = type(exc).__name__.lower()
        transient = any(
            token in name for token in ("throttl", "serviceunavailable", "toomanyrequests")
        )
        return HarnessError(
            ErrorCategory.MODEL_ERROR,
            f"Bedrock invocation failed: {exc}",
            details={"model_id": self._model_id},
            retryable=transient,
            cause=exc,
        )
