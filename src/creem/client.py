"""HTTP client for the Creem REST API.

The :class:`Creem` client authenticates every request with the ``x-api-key``
header and selects the API environment from the key prefix: keys starting
with ``creem_test_`` target the sandbox (https://test-api.creem.io),
everything else targets production (https://api.creem.io). Pass ``base_url``
explicitly to override the derived environment.

Retries: requests are retried automatically on rate limits (429), server
errors (5xx), and transport errors, with exponential backoff and jitter.
By default only idempotent-safe requests are retried — GET requests and
requests carrying an idempotency key (``Idempotency-Key`` header,
``request_id`` or ``idempotency_key`` in the body). Pass ``idempotent=True``
to ``request`` to retry other requests; pass ``max_retries=0`` to disable
retrying entirely.
"""

from __future__ import annotations

import os
import random
import time
from types import TracebackType
from typing import Any, Mapping, TypeVar, cast

import httpx

from .errors import (
    CreemAPIError,
    CreemAuthError,
    CreemConfigurationError,
    CreemNotFoundError,
    CreemRateLimitError,
    CreemServerError,
    CreemValidationError,
)

T = TypeVar("T")

PROD_BASE_URL = "https://api.creem.io"
TEST_BASE_URL = "https://test-api.creem.io"
TEST_KEY_PREFIX = "creem_test_"

# Statuses worth retrying: rate limit and transient server failures.
RETRYABLE_STATUSES = (429, 500, 502, 503, 504)
# Body keys that make a request safe to retry.
IDEMPOTENCY_BODY_KEYS = ("request_id", "idempotency_key")


class Creem:
    """Client for the Creem REST API.

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
        http_client: An existing ``httpx.Client`` to use (for tests and
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
        http_client: httpx.Client | None = None,
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
        self._http = http_client or httpx.Client(timeout=timeout)

        from .resources import (
            Affiliates,
            Checkouts,
            Credits,
            Customers,
            Discounts,
            Licenses,
            Moderation,
            Products,
            Refunds,
            Stats,
            Subscriptions,
            Transactions,
        )

        self.products = Products(self)
        self.checkouts = Checkouts(self)
        self.customers = Customers(self)
        self.subscriptions = Subscriptions(self)
        self.transactions = Transactions(self)
        self.discounts = Discounts(self)
        self.licenses = Licenses(self)
        self.credits = Credits(self)
        self.refunds = Refunds(self)
        self.affiliates = Affiliates(self)
        self.stats = Stats(self)
        self.moderation = Moderation(self)

    def request(
        self,
        method: str,
        path: str,
        *,
        params: Mapping[str, Any] | None = None,
        json_body: Mapping[str, Any] | None = None,
        headers: Mapping[str, str] | None = None,
        idempotent: bool | None = None,
    ) -> T:  # type: ignore[type-var]  # return type is inferred from the call site
        """Perform a raw API request and return the parsed JSON response.

        ``path`` is relative to the base URL, e.g. ``"/v1/checkouts"``.
        Raises the typed exceptions from :mod:`creem.errors` on non-2xx
        responses. Returns ``None`` for empty responses.

        ``idempotent`` forces retry eligibility when ``True`` or prevents
        retrying when ``False``; when omitted, a request is retried only if
        it is a GET or carries an idempotency key (see the module docs).
        """
        if idempotent is None:
            idempotent = self._is_idempotent_request(method, json_body, headers)
        request_headers = {"x-api-key": self.api_key, "Accept": "application/json"}
        if headers:
            request_headers.update(headers)
        url = f"{self.base_url}{path}"
        json_payload = dict(json_body) if json_body is not None else None

        attempt = 0
        while True:
            try:
                response = self._http.request(
                    method, url, params=params, json=json_payload, headers=request_headers
                )
            except httpx.RequestError:
                # Network failures may have reached the server; retry only
                # requests that are safe to repeat.
                if not idempotent or attempt >= self.max_retries:
                    raise
                time.sleep(self._retry_delay(attempt, None))
                attempt += 1
                continue
            if (
                response.status_code in RETRYABLE_STATUSES
                and idempotent
                and attempt < self.max_retries
            ):
                time.sleep(self._retry_delay(attempt, response))
                attempt += 1
                continue
            break

        if response.is_error:
            self._raise_for_error(response)
        if response.status_code == 204 or not response.content:
            return cast(T, None)
        return cast(T, response.json())

    @staticmethod
    def _is_idempotent_request(
        method: str,
        json_body: Mapping[str, Any] | None,
        headers: Mapping[str, str] | None,
    ) -> bool:
        if method.upper() == "GET":
            return True
        if headers and any(key.lower() == "idempotency-key" for key in headers):
            return True
        if json_body and any(key in json_body for key in IDEMPOTENCY_BODY_KEYS):
            return True
        return False

    def _retry_delay(self, attempt: int, response: httpx.Response | None) -> float:
        delay: float = self.backoff_base * (2**attempt)
        delay *= random.uniform(0.5, 1.0)
        if response is not None:
            retry_after = response.headers.get("Retry-After")
            if retry_after is not None:
                try:
                    retry_seconds: float | None = float(retry_after)
                except ValueError:
                    retry_seconds = None  # Retry-After may be an HTTP-date; use backoff
                if retry_seconds is not None:
                    delay = max(delay, retry_seconds)
        return delay

    def _raise_for_error(self, response: httpx.Response) -> None:
        payload: Any = None
        try:
            payload = response.json()
        except ValueError:
            payload = None
        status = response.status_code
        trace_id: str | None = None
        error: str | None = None
        messages: list[str] | None = None
        if isinstance(payload, dict):
            raw_messages = payload.get("message")
            if isinstance(raw_messages, str):
                messages = [raw_messages]
            elif isinstance(raw_messages, list):
                messages = [str(m) for m in raw_messages]
            trace_id = payload.get("trace_id") if isinstance(payload.get("trace_id"), str) else None
            error = payload.get("error") if isinstance(payload.get("error"), str) else None
            detail = ", ".join(messages) if messages else (error or f"HTTP {status}")
        else:
            detail = f"HTTP {status}"
        error_cls: type[CreemAPIError]
        if status == 400:
            error_cls = CreemValidationError
        elif status in (401, 403):
            error_cls = CreemAuthError
        elif status == 404:
            error_cls = CreemNotFoundError
        elif status == 429:
            error_cls = CreemRateLimitError
        elif status >= 500:
            error_cls = CreemServerError
        else:
            error_cls = CreemAPIError
        raise error_cls(status, detail, trace_id=trace_id, error=error, messages=messages) from None

    def close(self) -> None:
        """Close the underlying HTTP client."""
        self._http.close()

    def __enter__(self) -> Creem:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.close()
