"""Transactions: payments and invoices."""

from __future__ import annotations

from ..models import Transaction, TransactionList
from .base import APIResource, drop_none


class Transactions(APIResource):
    """Transaction endpoints."""

    def get(self, transaction_id: str) -> Transaction:
        """Retrieve a single transaction by ID."""
        return self._client.request(
            "GET", "/v1/transactions", params={"transaction_id": transaction_id}
        )

    def search(
        self,
        *,
        customer_id: str | None = None,
        order_id: str | None = None,
        product_id: str | None = None,
        page_number: int | None = None,
        page_size: int | None = None,
    ) -> TransactionList:
        """Search transactions (newest first), optionally filtered by
        customer, order, or product."""
        return self._client.request(
            "GET",
            "/v1/transactions/search",
            params=drop_none(
                {
                    "customer_id": customer_id,
                    "order_id": order_id,
                    "product_id": product_id,
                    "page_number": page_number,
                    "page_size": page_size,
                }
            ),
        )
