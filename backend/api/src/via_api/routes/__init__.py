"""API route modules."""

from via_api.routes.health import router as health_router
from via_api.routes.videos import router as videos_router

__all__ = ["health_router", "videos_router"]
