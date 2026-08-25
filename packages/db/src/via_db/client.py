"""Client factories for DynamoDB Local and real AWS endpoints."""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover - typing only
    from mypy_boto3_dynamodb.service_resource import DynamoDBServiceResource, Table

__all__ = ["get_dynamodb_resource", "get_table"]


def get_dynamodb_resource(
    *,
    endpoint_url: str | None = None,
    region_name: str | None = None,
) -> DynamoDBServiceResource:
    """Create a DynamoDB resource honoring local-endpoint configuration.

    Args:
        endpoint_url: Override endpoint (e.g. DynamoDB Local); falls back to
            the ``VIA_DYNAMODB_ENDPOINT_URL`` environment variable.
        region_name: AWS region; falls back to ``VIA_AWS_REGION``/default.

    Returns:
        A configured boto3 DynamoDB resource.
    """
    import boto3

    return boto3.resource(
        "dynamodb",
        endpoint_url=endpoint_url or os.environ.get("VIA_DYNAMODB_ENDPOINT_URL") or None,
        region_name=region_name or os.environ.get("VIA_AWS_REGION") or "us-east-1",
    )


def get_table(table_name: str, **kwargs: str | None) -> Table:
    """Return a table handle from the default resource.

    Args:
        table_name: Table name (``VIA_TABLE_NAME`` by convention).
        **kwargs: Forwarded to :func:`get_dynamodb_resource`.

    Returns:
        The DynamoDB table resource handle.
    """
    return get_dynamodb_resource(**kwargs).Table(table_name)
