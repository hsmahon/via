"""Event receiver and state machine for video processing.

Exports :func:`create_app` from :mod:`via_worker_video_processing.main` as the
public worker entry point. Used by the FastAPI worker service and tests to
bootstrap the EventBridge boundary.
"""

from via_worker_video_processing.main import create_app

__all__ = ["create_app"]
