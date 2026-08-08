"""Stats: store metrics and revenue time series."""

from __future__ import annotations

from typing import Literal

from ..models import ProductCurrency, StatsSummary
from .base import APIResource, AsyncAPIResource, drop_none

StatsInterval = Literal["day", "week", "month"]


class Stats(APIResource):
    """Store metrics endpoints."""

    def summary(
        self,
        *,
        currency: ProductCurrency,
        start_date: int | None = None,
        end_date: int | None = None,
        interval: StatsInterval | None = None,
    ) -> StatsSummary:
        """Retrieve aggregated store metrics (counts, revenue, MRR).

        Dates are Unix timestamps in milliseconds. When ``interval`` is
        provided, the response includes a ``periods`` time series; monetary
        amounts are in cents.
        """
        return self._client.request(
            "GET",
            "/v1/stats/summary",
            params=drop_none(
                {
                    "currency": currency,
                    "startDate": start_date,
                    "endDate": end_date,
                    "interval": interval,
                }
            ),
        )


class AsyncStats(AsyncAPIResource):
    """Async store metrics endpoints."""

    async def summary(
        self,
        *,
        currency: ProductCurrency,
        start_date: int | None = None,
        end_date: int | None = None,
        interval: StatsInterval | None = None,
    ) -> StatsSummary:
        """Retrieve aggregated store metrics (counts, revenue, MRR).

        Dates are Unix timestamps in milliseconds. When ``interval`` is
        provided, the response includes a ``periods`` time series; monetary
        amounts are in cents.
        """
        return await self._client.request(
            "GET",
            "/v1/stats/summary",
            params=drop_none(
                {
                    "currency": currency,
                    "startDate": start_date,
                    "endDate": end_date,
                    "interval": interval,
                }
            ),
        )
