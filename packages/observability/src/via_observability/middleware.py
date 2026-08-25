"""Pure-ASGI request tracing middleware.

Assigns/propagates ``X-Request-ID``, measures latency and emits one
structured log line per request. Implemented against the raw ASGI interface
so it works identically in FastAPI services and plain Starlette apps.
"""

from __future__ import annotations

import logging
import time
import uuid
from collections.abc import Awaitable, Callable
from contextvars import ContextVar
from typing import Any

__all__ = ["RequestContextMiddleware", "current_request_id"]

current_request_id: ContextVar[str | None] = ContextVar("current_request_id", default=None)

_ASGIApp = Callable[
    [
        dict[str, Any],
        Callable[[], Awaitable[dict[str, Any]]],
        Callable[[dict[str, Any]], Awaitable[None]],
    ],
    Awaitable[None],
]


class RequestContextMiddleware:
    """ASGI middleware attaching request identity and timing to logs."""

    def __init__(self, app: _ASGIApp, *, service_name: str) -> None:
        """Initialize the middleware.

        Args:
            app: Next ASGI application.
            service_name: Service identifier stamped onto log lines.
        """
        self.app = app
        self.service_name = service_name

    async def __call__(
        self,
        scope: dict[str, Any],
        receive: Callable[[], Awaitable[dict[str, Any]]],
        send: Callable[[dict[str, Any]], Awaitable[None]],
    ) -> None:
        """Process one HTTP request with tracing context installed.

        Non-HTTP scopes (lifespan/websocket) pass through untouched. HTTP
        requests get a request id (inbound ``X-Request-ID`` or generated),
        a response header echo, and a completion log line with status and
        latency.

        Args:
            scope: ASGI connection scope.
            receive: ASGI receive callable.
            send: ASGI send callable.
        """
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        headers = {
            k.decode("latin-1").lower(): v.decode("latin-1") for k, v in scope.get("headers", [])
        }
        request_id = headers.get("x-request-id") or uuid.uuid4().hex
        token = current_request_id.set(request_id)
        started = time.perf_counter()
        method = scope.get("method", "")
        path = scope.get("path", "")
        status_holder = {"status": 500}

        async def send_wrapper(message: dict[str, Any]) -> None:
            """Inject the response header and capture the status code.

            Args:
                message: Outbound ASGI message.
            """
            if message["type"] == "http.response.start":
                status_holder["status"] = message["status"]
                raw_headers = list(message.setdefault("headers", []))
                raw_headers.append((b"x-request-id", request_id.encode("latin-1")))
                message["headers"] = raw_headers
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            elapsed_ms = round((time.perf_counter() - started) * 1000, 3)
            logging.getLogger("via.request").info(
                "%s %s -> %s",
                method,
                path,
                status_holder["status"],
                extra={
                    "context": {
                        "request_id": request_id,
                        "http": {
                            "method": method,
                            "path": path,
                            "status": status_holder["status"],
                            "duration_ms": elapsed_ms,
                        },
                    }
                },
            )
            current_request_id.reset(token)
