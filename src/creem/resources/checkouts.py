"""Checkouts: hosted payment sessions."""

from __future__ import annotations

from typing import Any

from ..models import Checkout, CheckoutCreateParams
from .base import APIResource, merge


class Checkouts(APIResource):
    """Checkout session endpoints."""

    def create(
        self,
        params: CheckoutCreateParams,
        **kwargs: Any,
    ) -> Checkout:
        """Create a checkout session.

        Redirect the customer to the ``checkout_url`` in the response. Pass
        ``metadata`` (e.g. ``{"userId": ...}``) to map the payment back to
        your internal user in webhooks.
        """
        return self._client.request(
            "POST", "/v1/checkouts", json_body=merge(params, kwargs)
        )

    def get(self, checkout_id: str) -> Checkout:
        """Retrieve a checkout session by ID (e.g. to poll ``status``)."""
        return self._client.request(
            "GET", "/v1/checkouts", params={"checkout_id": checkout_id}
        )
