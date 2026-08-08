"""Async HTTP client for the Creem REST API.

:class:`AsyncCreem` mirrors the sync :class:`creem.client.Creem` for async
backends (FastAPI, Starlette, async workers). Same authentication, same
environment detection, same retry semantics, same errors — everything is
``await``-ed.

Quickstart::

    from creem import AsyncCreem

    async with AsyncCreem() as creem:
        checkout = await creem.checkouts.create(
            {"product_id": "prod_abc123", "success_url": "https://yoursite.com/success"}
        )
        print(checkout["checkout_url"])

The pure request logic is shared with the sync client (see
:mod:`creem.client`); only the transport and the retry sleep differ.
"""

from __future__ import annotations

import asyncio
import os
from types import TracebackType
from typing import Any, Mapping, TypeVar, cast

import httpx

from .client import (
    PROD_BASE_URL,
    RETRYABLE_STATUSES,
    TEST_BASE_URL,
    TEST_KEY_PREFIX,
    is_idempotent_request,
    raise_for_error,
    retry_delay,
)
from .errors import CreemConfigurationError

T = TypeVar("T")


class AsyncCreem:
    """Async client for the Creem REST API.

    Args:
        api_key: The secret API key from the Creem dashboard. Defaults to
            the ``CREEM_API_KEY`` environment variable.
        base_url: Override the environment derived from the key prefix.
        timeout: Request timeout in seconds.
        max_retries: How many times to retry a retryable request (0 disables
            retrying). Retries happen only for idempotent-safe requests
            unless ``idempotent=True`` is passed to :meth:`request`.
        backoff_base: Base delay in seconds before the first retry; doubles
            per attempt, with jitter, and never below a ``Retry-After``
            header on 429 responses.
        http_client: An existing ``httpx.AsyncClient`` to use (for tests and
            connection pooling customization).
    """

    def __init__(
        self,
        api_key: str | None = None,
        *,
        base_url: str | None = None,
        timeout: float = 30.0,
        max_retries: int = 3,
        backoff_base: float = 0.5,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        api_key_value = api_key or os.environ.get("CREEM_API_KEY")
        if not api_key_value:
            raise CreemConfigurationError(
                "No API key provided: pass api_key=... or set the CREEM_API_KEY "
                "environment variable."
            )
        self.api_key: str = api_key_value
        if base_url is None:
            base_url = (
                TEST_BASE_URL if self.api_key.startswith(TEST_KEY_PREFIX) else PROD_BASE_URL
            )
        self.base_url = base_url.rstrip("/")
        self.max_retries = max_retries
        self.backoff_base = backoff_base
        self._http = http_client or httpx.AsyncClient(timeout=timeout)

        from .resources import (
            AsyncAffiliates,
            AsyncCheckouts,
            AsyncCredits,
            AsyncCustomers,
            AsyncDiscounts,
            AsyncLicenses,
            AsyncModeration,
            AsyncProducts,
            AsyncRefunds,
            AsyncStats,
            AsyncSubscriptions,
            AsyncTransactions,
        )

        self.products = AsyncProducts(self)
        self.checkouts = AsyncCheckouts(self)
        self.customers = AsyncCustomers(self)
        self.subscriptions = AsyncSubscriptions(self)
        self.transactions = AsyncTransactions(self)
        self.discounts = AsyncDiscounts(self)
        self.licenses = AsyncLicenses(self)
        self.credits = AsyncCredits(self)
        self.refunds = AsyncRefunds(self)
        self.affiliates = AsyncAffiliates(self)
        self.stats = AsyncStats(self)
        self.moderation = AsyncModeration(self)

    async def request(
        self,
        method: str,
        path: str,
        *,
        params: Mapping[str, Any] | None = None,
        json_body: Mapping[str, Any] | None = None,
        headers: Mapping[str, str] | None = None,
        idempotent: bool | None = None,
    ) -> T:
        """Perform a raw API request and return the parsed JSON response.

        ``path`` is relative to the base URL, e.g. ``"/v1/checkouts"``.
        Raises the typed exceptions from :mod:`creem.errors` on non-2xx
        responses. Returns ``None`` for empty responses.

        ``idempotent`` forces retry eligibility when ``True`` or prevents
        retrying when ``False``; when omitted, a request is retried only if
        it is a GET or carries an idempotency key (see the sync client's
        module docs).
        """
        if idempotent is None:
            idempotent = is_idempotent_request(method, json_body, headers)
        request_headers = {"x-api-key": self.api_key, "Accept": "application/json"}
        if headers:
            request_headers.update(headers)
        url = f"{self.base_url}{path}"
        json_payload = dict(json_body) if json_body is not None else None

        attempt = 0
        while True:
            try:
                response = await self._http.request(
                    method, url, params=params, json=json_payload, headers=request_headers
                )
            except httpx.RequestError:
                # Network failures may have reached the server; retry only
                # requests that are safe to repeat.
                if not idempotent or attempt >= self.max_retries:
                    raise
                await asyncio.sleep(retry_delay(self.backoff_base, attempt, None))
                attempt += 1
                continue
            if (
                response.status_code in RETRYABLE_STATUSES
                and idempotent
                and attempt < self.max_retries
            ):
                await asyncio.sleep(retry_delay(self.backoff_base, attempt, response))
                attempt += 1
                continue
            break

        if response.is_error:
            raise_for_error(response)
        if response.status_code == 204 or not response.content:
            return cast(T, None)
        return cast(T, response.json())

    async def aclose(self) -> None:
        """Close the underlying HTTP client."""
        await self._http.aclose()

    async def __aenter__(self) -> AsyncCreem:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        await self.aclose()
