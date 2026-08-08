"""Customers and customer-scoped collections."""

from __future__ import annotations

from typing import Any

from ..models import (
    Customer,
    CustomerBillingLinks,
    CustomerBillingParams,
    CustomerCreateParams,
    CustomerList,
    CustomerUpdateParams,
    LicenseList,
    OrderList,
    SubscriptionList,
)
from .base import APIResource, drop_none, merge


class Customers(APIResource):
    """Customer endpoints."""

    def create(
        self,
        params: CustomerCreateParams,
        **kwargs: Any,
    ) -> Customer:
        """Create a new customer record for the store."""
        return self._client.request(
            "POST", "/v1/customers", json_body=merge(params, kwargs)
        )

    def get(self, *, customer_id: str | None = None, email: str | None = None) -> Customer:
        """Retrieve a customer by ID or email. Supply exactly one of the two."""
        return self._client.request(
            "GET",
            "/v1/customers",
            params=drop_none({"customer_id": customer_id, "email": email}),
        )

    def update(
        self,
        params: CustomerUpdateParams,
        **kwargs: Any,
    ) -> Customer:
        """Update a customer. ``customer_id`` is required."""
        return self._client.request(
            "PATCH", "/v1/customers", json_body=merge(params, kwargs)
        )

    def list(
        self,
        *,
        page_number: int | None = None,
        page_size: int | None = None,
    ) -> CustomerList:
        """List all customers with pagination."""
        return self._client.request(
            "GET",
            "/v1/customers/list",
            params=drop_none({"page_number": page_number, "page_size": page_size}),
        )

    def billing(
        self,
        params: CustomerBillingParams,
        **kwargs: Any,
    ) -> CustomerBillingLinks:
        """Generate a customer portal link for self-service billing
        (payment methods, invoices, subscriptions)."""
        return self._client.request(
            "POST", "/v1/customers/billing", json_body=merge(params, kwargs)
        )

    def orders(
        self,
        customer_id: str,
        *,
        page_number: int | None = None,
        page_size: int | None = None,
    ) -> OrderList:
        """List orders for a customer."""
        return self._client.request(
            "GET",
            f"/v1/customers/{customer_id}/orders",
            params=drop_none({"page_number": page_number, "page_size": page_size}),
        )

    def subscriptions(
        self,
        customer_id: str,
        *,
        page_number: int | None = None,
        page_size: int | None = None,
    ) -> SubscriptionList:
        """List subscriptions for a customer."""
        return self._client.request(
            "GET",
            f"/v1/customers/{customer_id}/subscriptions",
            params=drop_none({"page_number": page_number, "page_size": page_size}),
        )

    def licenses(
        self,
        customer_id: str,
        *,
        page_number: int | None = None,
        page_size: int | None = None,
    ) -> LicenseList:
        """List license keys for a customer."""
        return self._client.request(
            "GET",
            f"/v1/customers/{customer_id}/licenses",
            params=drop_none({"page_number": page_number, "page_size": page_size}),
        )
