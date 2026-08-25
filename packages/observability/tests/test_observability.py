"""Tests for logging configuration and request tracing middleware."""

from __future__ import annotations

import json
import logging

import pytest
from via_observability.logging import JsonFormatter, configure_logging
from via_observability.middleware import RequestContextMiddleware, current_request_id


class TestJsonLogging:
    """Structured formatter behavior."""

    def test_formats_record_with_context(self) -> None:
        """Extra ``context`` payloads are embedded into the JSON line."""
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname=__file__,
            lineno=1,
            msg="hello %s",
            args=("world",),
            exc_info=None,
        )
        record.context = {"service": "via-test", "request_id": "abc"}  # type: ignore[attr-defined]
        payload = json.loads(JsonFormatter().format(record))
        assert payload["message"] == "hello world"
        assert payload["service"] == "via-test"
        assert payload["level"] == "INFO"


class TestRequestContextMiddleware:
    """ASGI tracing middleware."""

    @staticmethod
    def _app(scope, receive, send) -> None:  # type: ignore[no-untyped-def]
        """Minimal inner app echoing the captured request id.

        Args:
            scope: ASGI scope.
            receive: Ignored.
            send: Response sender.
        """

        async def respond() -> None:
            """Send a 200 response."""
            await send({"type": "http.response.start", "status": 200, "headers": []})
            await send({"type": "http.response.body", "body": current_request_id.get().encode()})  # type: ignore[union-attr]

        _ = scope, receive
        return respond()

    async def _call(
        self, app, headers: list[tuple[bytes, bytes]]
    ) -> tuple[int, list[tuple[bytes, bytes]], bytes]:  # type: ignore[no-untyped-def]
        """Drive the middleware stack with a canned request.

        Args:
            app: Middleware-wrapped app.
            headers: Request headers.

        Returns:
            Tuple of (status, response headers, body).
        """
        scope = {"type": "http", "method": "GET", "path": "/", "headers": headers}
        messages: list[dict] = []

        async def receive() -> dict:
            """Return a no-op receive event.

            Returns:
                http.request message.
            """
            return {"type": "http.request"}

        async def send(message: dict) -> None:
            """Collect outbound messages.

            Args:
                message: Outbound ASGI message.
            """
            messages.append(message)

        await app(scope, receive, send)
        start = next(m for m in messages if m["type"] == "http.response.start")
        body = b"".join(m.get("body", b"") for m in messages if m["type"] == "http.response.body")
        return start["status"], list(start["headers"]), body

    @pytest.mark.asyncio
    async def test_generates_and_echoes_request_id(self) -> None:
        """Missing inbound ids are generated; responses echo them."""
        app = RequestContextMiddleware(self._app, service_name="via-test")
        status, headers, body = await self._call(app, [])
        assert status == 200
        echoed = dict(headers)[b"x-request-id"]
        assert echoed == body

    @pytest.mark.asyncio
    async def test_propagates_inbound_request_id(self) -> None:
        """Inbound X-Request-ID is preserved end-to-end."""
        app = RequestContextMiddleware(self._app, service_name="via-test")
        _, headers, body = await self._call(app, [(b"x-request-id", b"inbound-123")])
        assert dict(headers)[b"x-request-id"] == b"inbound-123"
        assert body == b"inbound-123"

    @pytest.mark.asyncio
    async def test_non_http_scope_passes_through(self) -> None:
        """Lifespan scopes bypass request handling entirely."""
        seen: list[dict] = []

        async def lifespan_app(scope, receive, send) -> None:  # type: ignore[no-untyped-def]
            """Record the scope and finish.

            Args:
                scope: ASGI scope.
                receive: Ignored.
                send: Ignored.
            """
            _ = receive, send
            seen.append(scope)

        app = RequestContextMiddleware(lifespan_app, service_name="via-test")
        await app({"type": "lifespan"}, None, None)
        assert seen == [{"type": "lifespan"}]


def test_configure_logging_is_idempotent() -> None:
    """Repeated configuration keeps exactly one root handler."""
    configure_logging("via-a")
    configure_logging("via-b")
    root = logging.getLogger()
    assert len(root.handlers) == 1
