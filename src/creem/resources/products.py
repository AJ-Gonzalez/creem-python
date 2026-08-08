"""Products: one-time and subscription catalog items."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

from ..models import Product, ProductCreateParams, ProductList, ProductStatus, ProductUpdateParams
from .base import APIResource, drop_none, iter_pages, merge


class Products(APIResource):
    """Product endpoints."""

    def create(
        self,
        params: ProductCreateParams,
        *,
        idempotency_key: str | None = None,
        **kwargs: Any,
    ) -> Product:
        """Create a product for one-time payments or subscriptions.

        Prices are in cents; use 0 for free products. Pass ``idempotency_key``
        to retry safely.
        """
        headers = {"Idempotency-Key": idempotency_key} if idempotency_key else None
        return self._client.request(
            "POST", "/v1/products", json_body=merge(params, kwargs), headers=headers
        )

    def get(self, product_id: str) -> Product:
        """Retrieve a product by ID."""
        return self._client.request("GET", f"/v1/products/{product_id}")

    def search(
        self,
        *,
        page_number: int | None = None,
        page_size: int | None = None,
        status: ProductStatus | None = None,
    ) -> ProductList:
        """Search products with pagination."""
        return self._client.request(
            "GET",
            "/v1/products/search",
            params=drop_none(
                {"page_number": page_number, "page_size": page_size, "status": status}
            ),
        )

    def update(
        self,
        product_id: str,
        params: ProductUpdateParams | None = None,
        **kwargs: Any,
    ) -> Product:
        """Update a product. Only supplied fields change; a price change
        mints a new default price."""
        return self._client.request(
            "PATCH", f"/v1/products/{product_id}", json_body=merge(params, kwargs)
        )

    def archive(self, product_id: str) -> Product:
        """Archive a product (soft-delete). It can no longer be purchased but
        is retained for historical orders and subscriptions."""
        return self._client.request("DELETE", f"/v1/products/{product_id}")

    def iter_all(
        self,
        *,
        page_size: int = 100,
        status: ProductStatus | None = None,
    ) -> Iterator[Product]:
        """Yield every product across all pages."""
        for page in iter_pages(self.search, page_size=page_size, filters={"status": status}):
            yield from page["items"]
