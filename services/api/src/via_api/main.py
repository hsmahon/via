"""FastAPI application factory for the Via API service."""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from via_harness import HarnessError
from via_observability import RequestContextMiddleware, configure_logging

from via_api.routes import health_router, videos_router
from via_api.settings import Settings

__all__ = ["create_app"]

#: Maps harness error categories onto HTTP status codes.
_CATEGORY_STATUS = {
    "INVALID_REQUEST": 400,
    "AUTHORIZATION_ERROR": 403,
    "TOOL_ERROR": 502,
    "MODEL_ERROR": 502,
    "INVALID_MODEL_RESPONSE": 502,
    "TIMEOUT": 504,
    "INTERNAL_ERROR": 500,
}


def create_app(settings: Settings | None = None) -> FastAPI:
    """Build the configured FastAPI application.

    Args:
        settings: Optional settings override (tests); defaults to env.

    Returns:
        The assembled application with tracing middleware and routers.
    """
    resolved = settings or Settings()
    configure_logging(resolved.service_name, level=resolved.log_level)
    app = FastAPI(
        title="Via API",
        version="0.1.0",
        description="Upload videos and interact with the Via video-understanding agent.",
    )
    app.add_middleware(RequestContextMiddleware, service_name=resolved.service_name)

    @app.exception_handler(HarnessError)
    async def harness_error_handler(request: Request, exc: HarnessError) -> JSONResponse:
        """Convert harness errors into the standard HTTP error envelope.

        Args:
            request: Inbound request.
            exc: Raised harness error.

        Returns:
            JSON response keyed by error category.
        """
        _ = request
        code = _CATEGORY_STATUS.get(exc.category.value, 500)
        return JSONResponse(
            status_code=code,
            content={"detail": exc.message, "category": exc.category.value, "run_id": exc.run_id},
        )

    app.include_router(health_router)
    app.include_router(videos_router)
    return app


app = create_app()
