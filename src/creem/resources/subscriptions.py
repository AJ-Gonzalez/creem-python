"""Subscriptions: lifecycle management."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any, overload

from ..models import (
    Subscription,
    SubscriptionCancelParams,
    SubscriptionList,
    SubscriptionStatus,
    SubscriptionUpdateParams,
    SubscriptionUpgradeParams,
)
from .base import APIResource, drop_none, iter_pages, merge


class Subscriptions(APIResource):
    """Subscription endpoints."""

    def get(self, subscription_id: str) -> Subscription:
        """Retrieve a subscription by ID."""
        return self._client.request(
            "GET", "/v1/subscriptions", params={"subscription_id": subscription_id}
        )

    def search(
        self,
        *,
        page_number: int | None = None,
        page_size: int | None = None,
        status: SubscriptionStatus | None = None,
    ) -> SubscriptionList:
        """List subscriptions with pagination.

        ``status`` is accepted by the API's documented examples
        (e.g. ``?status=active``) though absent from the OpenAPI spec.
        """
        return self._client.request(
            "GET",
            "/v1/subscriptions/search",
            params=drop_none(
                {"page_number": page_number, "page_size": page_size, "status": status}
            ),
        )

    def update(
        self,
        subscription_id: str,
        params: SubscriptionUpdateParams | None = None,
        **kwargs: Any,
    ) -> Subscription:
        """Modify subscription items (units, seats, add-ons). Supports
        proration via ``update_behavior``."""
        return self._client.request(
            "POST", f"/v1/subscriptions/{subscription_id}", json_body=merge(params, kwargs)
        )

    def cancel(
        self,
        subscription_id: str,
        params: SubscriptionCancelParams | None = None,
        **kwargs: Any,
    ) -> Subscription:
        """Cancel a subscription immediately or at period end.

        Prefer ``{"mode": "scheduled"}`` so the customer keeps access until
        the billing period ends.
        """
        return self._client.request(
            "POST",
            f"/v1/subscriptions/{subscription_id}/cancel",
            json_body=merge(params, kwargs),
        )

    def pause(self, subscription_id: str) -> Subscription:
        """Temporarily pause a subscription; billing stops until resumed."""
        return self._client.request("POST", f"/v1/subscriptions/{subscription_id}/pause")

    def resume(self, subscription_id: str) -> Subscription:
        """Resume a paused (or scheduled-for-cancellation) subscription."""
        return self._client.request("POST", f"/v1/subscriptions/{subscription_id}/resume")

    @overload
    def upgrade(
        self, subscription_id: str, params: SubscriptionUpgradeParams, **kwargs: Any
    ) -> Subscription: ...

    @overload
    def upgrade(self, subscription_id: str, **kwargs: Any) -> Subscription: ...

    def upgrade(
        self,
        subscription_id: str,
        params: SubscriptionUpgradeParams | None = None,
        **kwargs: Any,
    ) -> Subscription:
        """Upgrade a subscription to a different product. Proration is
        handled automatically (see ``update_behavior``)."""
        return self._client.request(
            "POST",
            f"/v1/subscriptions/{subscription_id}/upgrade",
            json_body=merge(params, kwargs),
        )

    def iter_all(
        self,
        *,
        page_size: int = 100,
        status: SubscriptionStatus | None = None,
    ) -> Iterator[Subscription]:
        """Yield every subscription across all pages."""
        for page in iter_pages(self.search, page_size=page_size, filters={"status": status}):
            yield from page["items"]
