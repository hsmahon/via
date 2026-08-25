"""Analytics counters (monotonic, scope-scoped)."""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

from via_db.keys import analytics_pk, counter_sk

if TYPE_CHECKING:  # pragma: no cover - typing only
    from mypy_boto3_dynamodb.service_resource import Table

__all__ = ["AnalyticsRepository"]


class AnalyticsRepository:
    """Atomic counter increments for lightweight analytics."""

    def __init__(self, table: Table) -> None:
        """Initialize the repository.

        Args:
            table: DynamoDB table handle.
        """
        self._table = table

    def increment(self, *, scope: str = "GLOBAL", counter: str, amount: int = 1) -> None:
        """Atomically add to a counter.

        Args:
            scope: Scope identifier (``GLOBAL`` or ``USER#<id>``).
            counter: Counter name such as ``videos_uploaded``.
            amount: Positive delta to apply.
        """
        self._table.update_item(
            Key={"pk": analytics_pk(scope), "sk": counter_sk(counter)},
            UpdateExpression="ADD #c :amount",
            ExpressionAttributeNames={"#c": "count"},
            ExpressionAttributeValues={":amount": amount},
        )

    def get(self, *, scope: str = "GLOBAL", counter: str) -> int:
        """Read a counter's current value.

        Args:
            scope: Scope identifier.
            counter: Counter name.

        Returns:
            Current value; ``0`` when never incremented.
        """
        response = self._table.get_item(Key={"pk": analytics_pk(scope), "sk": counter_sk(counter)})
        item = response.get("Item") or {}
        raw = item.get("count", 0)
        return int(raw) if isinstance(raw, (int, float, str, Decimal)) else 0
