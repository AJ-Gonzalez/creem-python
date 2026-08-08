"""Affiliates: referral programs and commissions."""

from __future__ import annotations

from ..models import (
    Affiliate,
    AffiliateList,
    CommissionList,
    CommissionStatus,
)
from .base import APIResource, drop_none


class Affiliates(APIResource):
    """Affiliate endpoints."""

    def list(
        self,
        *,
        page_number: int | None = None,
        page_size: int | None = None,
    ) -> AffiliateList:
        """List affiliates with referral links, click/conversion counts, and
        lifetime commission. Invited-but-not-joined affiliates are excluded."""
        return self._client.request(
            "GET",
            "/v1/affiliates",
            params=drop_none({"page_number": page_number, "page_size": page_size}),
        )

    def get(self, affiliate_id: str) -> Affiliate:
        """Retrieve a single affiliate by ID."""
        return self._client.request("GET", f"/v1/affiliates/{affiliate_id}")

    def commissions(
        self,
        affiliate_id: str,
        *,
        status: CommissionStatus | None = None,
        page_number: int | None = None,
        page_size: int | None = None,
    ) -> CommissionList:
        """List an affiliate's commissions, optionally filtered by settlement
        status (pending, approved, paid)."""
        return self._client.request(
            "GET",
            f"/v1/affiliates/{affiliate_id}/commissions",
            params=drop_none(
                {"status": status, "page_number": page_number, "page_size": page_size}
            ),
        )
