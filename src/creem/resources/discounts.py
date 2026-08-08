"""Discounts: promotional codes."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any, Literal

from ..models import Discount, DiscountCreateParams, DiscountList, DiscountType
from .base import APIResource, drop_none, iter_pages, merge

DiscountSearchStatus = Literal["active", "deleted"]


class Discounts(APIResource):
    """Discount code endpoints."""

    def create(
        self,
        params: DiscountCreateParams,
        **kwargs: Any,
    ) -> Discount:
        """Create a promotional discount code. Percentage or fixed amount,
        with optional expiration and redemption limits."""
        return self._client.request(
            "POST", "/v1/discounts", json_body=merge(params, kwargs)
        )

    def get(
        self,
        *,
        discount_id: str | None = None,
        discount_code: str | None = None,
    ) -> Discount:
        """Retrieve a discount by ID or code. Supply exactly one of the two."""
        return self._client.request(
            "GET",
            "/v1/discounts",
            params=drop_none({"discount_id": discount_id, "discount_code": discount_code}),
        )

    def search(
        self,
        *,
        page_number: int | None = None,
        page_size: int | None = None,
        product_id: str | None = None,
        status: DiscountSearchStatus | None = None,
        type: DiscountType | None = None,
        created_after: str | None = None,
        created_before: str | None = None,
    ) -> DiscountList:
        """Search discounts with filters and pagination. Date filters use
        ISO-8601 timestamps."""
        return self._client.request(
            "GET",
            "/v1/discounts/search",
            params=drop_none(
                {
                    "page_number": page_number,
                    "page_size": page_size,
                    "product_id": product_id,
                    "status": status,
                    "type": type,
                    "created_after": created_after,
                    "created_before": created_before,
                }
            ),
        )

    def delete(self, discount_id: str) -> Discount:
        """Permanently delete a discount code; it can no longer be redeemed."""
        return self._client.request("DELETE", f"/v1/discounts/{discount_id}/delete")

    def iter_all(
        self,
        *,
        page_size: int = 100,
        product_id: str | None = None,
        status: DiscountSearchStatus | None = None,
        type: DiscountType | None = None,
        created_after: str | None = None,
        created_before: str | None = None,
    ) -> Iterator[Discount]:
        """Yield every discount across all pages."""
        for page in iter_pages(
            self.search,
            page_size=page_size,
            filters={
                "product_id": product_id,
                "status": status,
                "type": type,
                "created_after": created_after,
                "created_before": created_before,
            },
        ):
            yield from page["items"]
