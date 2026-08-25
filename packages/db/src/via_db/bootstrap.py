"""Console entry point creating the local table: ``python -m via_db.bootstrap``."""

from __future__ import annotations

import os

from via_db.client import get_dynamodb_resource
from via_db.tables import create_table


def main() -> None:
    """Create the Via table against the configured endpoint.

    Uses ``VIA_TABLE_NAME`` (default ``via``) and honors
    ``VIA_DYNAMODB_ENDPOINT_URL`` so the same command bootstraps DynamoDB
    Local in Docker Compose or a real AWS account.
    """
    table_name = os.environ.get("VIA_TABLE_NAME", "via")
    resource = get_dynamodb_resource()
    create_table(resource, table_name)
    print(f"table ready: {table_name}")


if __name__ == "__main__":
    main()
