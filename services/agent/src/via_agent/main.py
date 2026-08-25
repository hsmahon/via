"""FastAPI application factory for the Via agent service."""

from __future__ import annotations

from functools import lru_cache
from typing import Annotated, Any

from fastapi import Depends, FastAPI, Header, HTTPException
from via_harness import AgentRequest
from via_observability import RequestContextMiddleware, configure_logging

from via_agent.schemas import HealthResponse, InvokeRequest, InvokeResponse, TraceResponse
from via_agent.settings import Settings
from via_agent.wiring import ServiceContext, build_authorization_context, build_context

__all__ = ["create_app"]


@lru_cache(maxsize=1)
def _context() -> ServiceContext:
    """Build the process-wide wired context.

    Returns:
        :class:`ServiceContext` assembled from environment settings.
    """
    return build_context()


def get_context() -> ServiceContext:
    """FastAPI dependency returning the wired service context.

    Returns:
        The cached :class:`ServiceContext`.
    """
    return _context()


def create_app(settings: Settings | None = None) -> FastAPI:
    """Build the configured agent application.

    Args:
        settings: Optional settings override (tests).

    Returns:
        The assembled FastAPI app exposing the harness over HTTP.
    """
    resolved = settings or Settings()
    configure_logging(resolved.service_name, level=resolved.log_level)

    # Tests pass explicit settings and bypass the process-wide cache.
    context_holder = {"ctx": build_context(settings)} if settings is not None else {}

    app = FastAPI(
        title="Via Agent", version="0.1.0", description="Conversational video-understanding agent."
    )
    app.add_middleware(RequestContextMiddleware, service_name=resolved.service_name)

    def current_context() -> ServiceContext:
        """Resolve the active context (injected or process-wide).

        Returns:
            The active :class:`ServiceContext`.
        """
        return context_holder["ctx"] if context_holder else _context()

    @app.get("/health", response_model=HealthResponse)
    def health() -> HealthResponse:
        """Report liveness and version.

        Returns:
            Static healthy payload.
        """
        return HealthResponse(
            service=resolved.service_name, status="ok", version=resolved.agent_version
        )

    @app.post("/agent/invoke", response_model=None)
    def invoke(
        body: InvokeRequest,
        x_user_id: Annotated[str | None, Header()] = None,
        ctx: ServiceContext = Depends(current_context),
    ) -> Any:
        """Run one authorized agent interaction.

        Args:
            body: Invocation payload.
            x_user_id: Identity header (v0.1 auth; real identity layer later).
            ctx: Wired collaborators.

        Returns:
            ``InvokeResponse`` on success or a JSON error envelope mapped by
            error category.

        Raises:
            HTTPException: 400 invalid request, 403 authorization denials.
        """
        user_id = x_user_id or ctx.settings.default_user_id
        authz = build_authorization_context(ctx, user_id=user_id, video_id=body.video_id)
        request = AgentRequest(
            message=body.message,
            video_id=body.video_id,
            session_id=body.session_id,
            prompt_name=body.prompt_name,
        )
        result = ctx.runner.execute(request, authz)
        if result.completed:
            assert result.response is not None
            return InvokeResponse(
                run_id=result.run_id,
                trace_id=result.trace_id,
                session_id=result.session_id,
                answer=result.response.answer,
                citations=list(result.response.citations),
                steps=result.steps,
                usage=result.usage,
            )
        failure = result.failure
        category = failure.category.value if failure else "INTERNAL_ERROR"
        status_code = (
            403
            if category == "AUTHORIZATION_ERROR"
            else 502
            if category in ("MODEL_ERROR", "TOOL_ERROR", "INVALID_MODEL_RESPONSE")
            else 400
        )
        raise HTTPException(
            status_code=status_code,
            detail={
                "detail": failure.message if failure else "run failed",
                "category": category,
                "run_id": result.run_id,
            },
        )

    @app.get("/agent/runs/{run_id}/trace", response_model=TraceResponse)
    def trace(run_id: str, ctx: ServiceContext = Depends(current_context)) -> TraceResponse:
        """Expose recorded spans of one run (local tracer only).

        Args:
            run_id: Run identifier returned from an invocation.
            ctx: Wired collaborators.

        Returns:
            Span records for debugging and tests.
        """
        spans = ctx.tracer.query(run_id)
        return TraceResponse(
            run_id=run_id,
            spans=[
                {
                    "name": s.name,
                    "trace_id": s.trace_id,
                    "span_id": s.span_id,
                    "parent_span_id": s.parent_span_id,
                    "status": s.status,
                    "duration_ms": s.duration_ms,
                    "attributes": {k: str(v) for k, v in s.attributes.items()},
                }
                for s in spans
            ],
        )

    return app


app = create_app()
