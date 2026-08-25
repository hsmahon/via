"""Single DynamoDB table for v0.1: ``via-table`` with the user-videos GSI."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:  # pragma: no cover - typing only
    from mypy_boto3_dynamodb.service_resource import DynamoDBServiceResource

__all__ = ["TABLE_DEFINITION", "create_table"]


TABLE_DEFINITION: dict[str, Any] = {
    "TableName": "via",
    "KeySchema": [
        {"AttributeName": "pk", "KeyType": "HASH"},
        {"AttributeName": "sk", "KeyType": "RANGE"},
    ],
    "AttributeDefinitions": [
        {"AttributeName": "pk", "AttributeType": "S"},
        {"AttributeName": "sk", "AttributeType": "S"},
        {"AttributeName": "gsi1pk", "AttributeType": "S"},
        {"AttributeName": "gsi1sk", "AttributeType": "S"},
    ],
    "GlobalSecondaryIndexes": [
        {
            "IndexName": "gsi1",
            "KeySchema": [
                {"AttributeName": "gsi1pk", "KeyType": "HASH"},
                {"AttributeName": "gsi1sk", "KeyType": "RANGE"},
            ],
            "Projection": {"ProjectionType": "ALL"},
        }
    ],
    "BillingMode": "PAY_PER_REQUEST",
}


def create_table(resource: DynamoDBServiceResource, table_name: str) -> None:
    """Create the Via table if it does not already exist.

    Args:
        resource: DynamoDB resource (real AWS or DynamoDB Local).
        table_name: Name to create; overrides the default in the definition.
    """
    existing = [t.name for t in resource.tables.all()]
    if table_name in existing:
        return
    definition = {**TABLE_DEFINITION, "TableName": table_name}
    table = resource.create_table(**definition)
    table.wait_until_exists()
