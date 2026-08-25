"""Shared fixtures: a real table shape in moto-backed DynamoDB."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest


@pytest.fixture()
def ddb_table() -> Iterator[Any]:
    """Provide the Via table inside a moto-mocked DynamoDB.

    Yields:
        A boto3 Table handle with the production key/GSI layout.
    """
    from moto import mock_aws
    from via_db.client import get_dynamodb_resource
    from via_db.tables import create_table

    with mock_aws():
        resource = get_dynamodb_resource(region_name="us-east-1")
        create_table(resource, "via-test")
        yield resource.Table("via-test")


@pytest.fixture()
def videos(ddb_table: Any) -> Any:
    """Provide a video repository over the mocked table.

    Args:
        ddb_table: Mocked DynamoDB table.

    Returns:
        :class:`VideoRepository` instance.
    """
    from via_db.videos import VideoRepository

    return VideoRepository(ddb_table)
