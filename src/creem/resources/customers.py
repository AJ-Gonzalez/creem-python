"""Customers and customer-scoped collections."""

from __future__ import annotations

from collections.abc import AsyncIterator, Iterator
from typing import Any, overload

from ..models import (
    Customer,
    CustomerBillingLinks,
    CustomerBillingParams,
    CustomerCreateParams,
    CustomerList,
    CustomerUpdateParams,
    License,
    LicenseList,
    Order,
    OrderList,
    Subscription,
    SubscriptionList,
)
from .base import APIResource, AsyncAPIResource, drop_none, iter_pages, iter_pages_async, merge


class Customers(APIResource):
    """Customer endpoints."""

    @overload
    def create(self, params: CustomerCreateParams, **kwargs: Any) -> Customer: ...

    @overload
    def create(self, **kwargs: Any) -> Customer: ...

    def create(
        self,
        params: CustomerCreateParams | None = None,
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

    @overload
    def update(self, params: CustomerUpdateParams, **kwargs: Any) -> Customer: ...

    @overload
    def update(self, **kwargs: Any) -> Customer: ...

    def update(
        self,
        params: CustomerUpdateParams | None = None,
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

    @overload
    def billing(self, params: CustomerBillingParams, **kwargs: Any) -> CustomerBillingLinks: ...

    @overload
    def billing(self, **kwargs: Any) -> CustomerBillingLinks: ...

    def billing(
        self,
        params: CustomerBillingParams | None = None,
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

    def iter_all(self, *, page_size: int = 100) -> Iterator[Customer]:
        """Yield every customer across all pages."""
        for page in iter_pages(self.list, page_size=page_size, filters={}):
            yield from page["items"]

    def iter_orders(self, customer_id: str, *, page_size: int = 100) -> Iterator[Order]:
        """Yield every order for a customer across all pages."""
        for page in iter_pages(
            self.orders, page_size=page_size, filters={"customer_id": customer_id}
        ):
            yield from page["items"]

    def iter_subscriptions(
        self, customer_id: str, *, page_size: int = 100
    ) -> Iterator[Subscription]:
        """Yield every subscription for a customer across all pages."""
        for page in iter_pages(
            self.subscriptions, page_size=page_size, filters={"customer_id": customer_id}
        ):
            yield from page["items"]

    def iter_licenses(self, customer_id: str, *, page_size: int = 100) -> Iterator[License]:
        """Yield every license key for a customer across all pages."""
        for page in iter_pages(
            self.licenses, page_size=page_size, filters={"customer_id": customer_id}
        ):
            yield from page["items"]


class AsyncCustomers(AsyncAPIResource):
    """Async customer endpoints."""

    @overload
    async def create(self, params: CustomerCreateParams, **kwargs: Any) -> Customer: ...

    @overload
    async def create(self, **kwargs: Any) -> Customer: ...

    async def create(
        self,
        params: CustomerCreateParams | None = None,
        **kwargs: Any,
    ) -> Customer:
        """Create a new customer record for the store."""
        return await self._client.request(
            "POST", "/v1/customers", json_body=merge(params, kwargs)
        )

    async def get(
        self, *, customer_id: str | None = None, email: str | None = None
    ) -> Customer:
        """Retrieve a customer by ID or email. Supply exactly one of the two."""
        return await self._client.request(
            "GET",
            "/v1/customers",
            params=drop_none({"customer_id": customer_id, "email": email}),
        )

    @overload
    async def update(self, params: CustomerUpdateParams, **kwargs: Any) -> Customer: ...

    @overload
    async def update(self, **kwargs: Any) -> Customer: ...

    async def update(
        self,
        params: CustomerUpdateParams | None = None,
        **kwargs: Any,
    ) -> Customer:
        """Update a customer. ``customer_id`` is required."""
        return await self._client.request(
            "PATCH", "/v1/customers", json_body=merge(params, kwargs)
        )

    async def list(
        self,
        *,
        page_number: int | None = None,
        page_size: int | None = None,
    ) -> CustomerList:
        """List all customers with pagination."""
        return await self._client.request(
            "GET",
            "/v1/customers/list",
            params=drop_none({"page_number": page_number, "page_size": page_size}),
        )

    @overload
    async def billing(
        self, params: CustomerBillingParams, **kwargs: Any
    ) -> CustomerBillingLinks: ...

    @overload
    async def billing(self, **kwargs: Any) -> CustomerBillingLinks: ...

    async def billing(
        self,
        params: CustomerBillingParams | None = None,
        **kwargs: Any,
    ) -> CustomerBillingLinks:
        """Generate a customer portal link for self-service billing
        (payment methods, invoices, subscriptions)."""
        return await self._client.request(
            "POST", "/v1/customers/billing", json_body=merge(params, kwargs)
        )

    async def orders(
        self,
        customer_id: str,
        *,
        page_number: int | None = None,
        page_size: int | None = None,
    ) -> OrderList:
        """List orders for a customer."""
        return await self._client.request(
            "GET",
            f"/v1/customers/{customer_id}/orders",
            params=drop_none({"page_number": page_number, "page_size": page_size}),
        )

    async def subscriptions(
        self,
        customer_id: str,
        *,
        page_number: int | None = None,
        page_size: int | None = None,
    ) -> SubscriptionList:
        """List subscriptions for a customer."""
        return await self._client.request(
            "GET",
            f"/v1/customers/{customer_id}/subscriptions",
            params=drop_none({"page_number": page_number, "page_size": page_size}),
        )

    async def licenses(
        self,
        customer_id: str,
        *,
        page_number: int | None = None,
        page_size: int | None = None,
    ) -> LicenseList:
        """List license keys for a customer."""
        return await self._client.request(
            "GET",
            f"/v1/customers/{customer_id}/licenses",
            params=drop_none({"page_number": page_number, "page_size": page_size}),
        )

    async def iter_all(self, *, page_size: int = 100) -> AsyncIterator[Customer]:
        """Yield every customer across all pages."""
        async for page in iter_pages_async(self.list, page_size=page_size, filters={}):
            for item in page["items"]:
                yield item

    async def iter_orders(
        self, customer_id: str, *, page_size: int = 100
    ) -> AsyncIterator[Order]:
        """Yield every order for a customer across all pages."""
        async for page in iter_pages_async(
            self.orders, page_size=page_size, filters={"customer_id": customer_id}
        ):
            for item in page["items"]:
                yield item

    async def iter_subscriptions(
        self, customer_id: str, *, page_size: int = 100
    ) -> AsyncIterator[Subscription]:
        """Yield every subscription for a customer across all pages."""
        async for page in iter_pages_async(
            self.subscriptions, page_size=page_size, filters={"customer_id": customer_id}
        ):
            for item in page["items"]:
                yield item

    async def iter_licenses(
        self, customer_id: str, *, page_size: int = 100
    ) -> AsyncIterator[License]:
        """Yield every license key for a customer across all pages."""
        async for page in iter_pages_async(
            self.licenses, page_size=page_size, filters={"customer_id": customer_id}
        ):
            for item in page["items"]:
                yield item
