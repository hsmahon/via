"""Shared fixtures for tools tests."""

from __future__ import annotations

import pytest
from via_harness import AuthorizationContext, Permission


@pytest.fixture()
def authz() -> AuthorizationContext:
    """Provide a fully-permitted authorization context.

    Returns:
        Context granting all harness permissions on video-1.
    """
    return AuthorizationContext(
        user_id="user-1",
        video_id="video-1",
        permissions=frozenset(
            {Permission.VIDEO_READ, Permission.TRANSCRIPT_READ, Permission.VIDEO_ANALYZE}
        ),
    )
