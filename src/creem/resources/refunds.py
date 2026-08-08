"""Refunds: full refunds against transactions."""

from __future__ import annotations

from typing import Any

from ..models import RefundCreateParams, RefundResult
from .base import APIResource, merge


class Refunds(APIResource):
    """Refund endpoints."""

    def create(
        self,
        params: RefundCreateParams,
        **kwargs: Any,
    ) -> RefundResult:
        """Issue a full refund for a payment, identified by its transaction
        ID. The remaining refundable amount is resolved automatically.

        The refund status may be ``pending`` when the payment provider
        confirms asynchronously.
        """
        return self._client.request(
            "POST", "/v1/refunds", json_body=merge(params, kwargs)
        )
