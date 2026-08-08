"""Affiliates: referral programs and commissions."""

from __future__ import annotations

from collections.abc import Iterator

from ..models import (
    Affiliate,
    AffiliateList,
    Commission,
    CommissionList,
    CommissionStatus,
)
from .base import APIResource, drop_none, iter_pages


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

    def iter_all(self, *, page_size: int = 100) -> Iterator[Affiliate]:
        """Yield every affiliate across all pages."""
        for page in iter_pages(self.list, page_size=page_size, filters={}):
            yield from page["items"]

    def iter_commissions(
        self,
        affiliate_id: str,
        *,
        page_size: int = 100,
        status: CommissionStatus | None = None,
    ) -> Iterator[Commission]:
        """Yield every commission for an affiliate across all pages."""
        for page in iter_pages(
            self.commissions,
            page_size=page_size,
            filters={"affiliate_id": affiliate_id, "status": status},
        ):
            yield from page["items"]
