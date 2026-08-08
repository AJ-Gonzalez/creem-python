"""Async client behavior tests: parity with the sync client.

Auth, environment detection, error mapping, retries, and the async context
manager. All delays are short-circuited by patching ``asyncio.sleep``.
"""

from __future__ import annotations

from collections.abc import Coroutine
from typing import Any, Callable

import asyncio
import httpx
import pytest

from creem import (
    PROD_BASE_URL,
    TEST_BASE_URL,
    AsyncCreem,
    CreemAPIError,
    CreemAuthError,
    CreemConfigurationError,
    CreemNotFoundError,
    CreemRateLimitError,
    CreemServerError,
    CreemValidationError,
)

pytestmark = pytest.mark.anyio


def make_client(
    handler: Callable[[httpx.Request], httpx.Response]
    | Callable[[httpx.Request], Coroutine[None, None, httpx.Response]],
    api_key: str = "creem_test_key123",
    **kwargs: Any,
) -> AsyncCreem:
    transport = httpx.MockTransport(handler)
    http_client = httpx.AsyncClient(transport=transport)
    return AsyncCreem(api_key, http_client=http_client, **kwargs)


def sleep_capture(monkeypatch: pytest.MonkeyPatch) -> list[float]:
    """Replace asyncio.sleep with a recorder; returns the recorded delays."""
    sleeps: list[float] = []

    async def fake_sleep(seconds: float) -> None:
        sleeps.append(seconds)

    monkeypatch.setattr(asyncio, "sleep", fake_sleep)
    return sleeps


async def test_missing_api_key_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("CREEM_API_KEY", raising=False)
    with pytest.raises(CreemConfigurationError, match="API key"):
        AsyncCreem()


async def test_api_key_from_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CREEM_API_KEY", "creem_test_envkey")

    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["x-api-key"] == "creem_test_envkey"
        return httpx.Response(200, json={"ok": True})

    transport = httpx.MockTransport(handler)
    client = AsyncCreem(http_client=httpx.AsyncClient(transport=transport))
    assert await client.request("GET", "/v1/products") == {"ok": True}
    await client.aclose()


async def test_test_key_uses_test_base_url() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert str(request.url).startswith(TEST_BASE_URL)
        return httpx.Response(200, json={})

    client = make_client(handler)
    await client.request("GET", "/v1/products")
    await client.aclose()


async def test_live_key_uses_prod_base_url() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert str(request.url).startswith(PROD_BASE_URL)
        return httpx.Response(200, json={})

    client = make_client(handler, api_key="creem_live_key123")
    await client.request("GET", "/v1/products")
    await client.aclose()


async def test_request_sends_auth_header() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["x-api-key"] == "creem_test_key123"
        return httpx.Response(200, json={})

    client = make_client(handler)
    await client.request("GET", "/v1/products")
    await client.aclose()


async def test_json_body_is_sent() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert '"product_id":"prod_1"' in request.content.decode()
        return httpx.Response(200, json={})

    client = make_client(handler)
    await client.request("POST", "/v1/checkouts", json_body={"product_id": "prod_1"})
    await client.aclose()


async def test_validation_error_parses_envelope() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            400,
            json={
                "trace_id": "trace-abc",
                "status": 400,
                "error": "Bad Request",
                "message": ["The 'product_id' field is required."],
                "timestamp": 1706889600000,
            },
        )

    client = make_client(handler)
    with pytest.raises(CreemValidationError) as excinfo:
        await client.request("POST", "/v1/checkouts", json_body={})
    error = excinfo.value
    assert error.status == 400
    assert error.trace_id == "trace-abc"
    assert error.messages == ["The 'product_id' field is required."]
    await client.aclose()


async def test_auth_error_401() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"trace_id": "t", "status": 401})

    client = make_client(handler)
    with pytest.raises(CreemAuthError):
        await client.request("GET", "/v1/products")
    await client.aclose()


async def test_not_found_error() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, json={"message": ["Product not found"]})

    client = make_client(handler)
    with pytest.raises(CreemNotFoundError):
        await client.request("GET", "/v1/products/prod_missing")
    await client.aclose()


async def test_rate_limit_error() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, json={})

    client = make_client(handler)
    with pytest.raises(CreemRateLimitError):
        await client.request("GET", "/v1/products")
    await client.aclose()


async def test_server_error() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={})

    client = make_client(handler)
    with pytest.raises(CreemServerError):
        await client.request("GET", "/v1/products")
    await client.aclose()


async def test_non_json_error_body_falls_back_to_status() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, text="<html>boom</html>")

    client = make_client(handler)
    with pytest.raises(CreemAPIError) as excinfo:
        await client.request("GET", "/v1/products")
    assert excinfo.value.status == 503
    await client.aclose()


async def test_unknown_status_raises_generic_api_error() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(418, json={"error": "Teapot"})

    client = make_client(handler)
    with pytest.raises(CreemAPIError) as excinfo:
        await client.request("GET", "/v1/products")
    assert excinfo.value.status == 418
    await client.aclose()


async def test_empty_response_returns_none() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(204)

    client = make_client(handler)
    assert await client.request("POST", "/v1/customers", json_body={}) is None
    await client.aclose()


# --- retry behavior ---------------------------------------------------------


async def test_get_retries_5xx_then_succeeds(monkeypatch: pytest.MonkeyPatch) -> None:
    attempts = 0
    sleeps = sleep_capture(monkeypatch)

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            return httpx.Response(500, json={})
        return httpx.Response(200, json={"ok": True})

    client = make_client(handler)
    assert await client.request("GET", "/v1/products") == {"ok": True}
    assert attempts == 2
    assert len(sleeps) == 1
    assert 0.5 * 0.5 <= sleeps[0] <= 0.5
    await client.aclose()


async def test_get_retries_429_respecting_retry_after(monkeypatch: pytest.MonkeyPatch) -> None:
    attempts = 0
    sleeps = sleep_capture(monkeypatch)

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            return httpx.Response(429, headers={"Retry-After": "2.5"}, json={})
        return httpx.Response(200, json={})

    client = make_client(handler)
    await client.request("GET", "/v1/products")
    assert attempts == 2
    assert sleeps[0] >= 2.5
    await client.aclose()


async def test_retries_exhausted_raises_server_error(monkeypatch: pytest.MonkeyPatch) -> None:
    attempts = 0
    sleeps = sleep_capture(monkeypatch)

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        return httpx.Response(503, json={})

    client = make_client(handler, max_retries=2)
    with pytest.raises(CreemServerError):
        await client.request("GET", "/v1/products")
    assert attempts == 3
    assert len(sleeps) == 2
    assert sleeps[0] < sleeps[1]
    await client.aclose()


async def test_post_without_idempotency_is_not_retried(monkeypatch: pytest.MonkeyPatch) -> None:
    attempts = 0
    sleeps = sleep_capture(monkeypatch)

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        return httpx.Response(500, json={})

    client = make_client(handler)
    with pytest.raises(CreemServerError):
        await client.request("POST", "/v1/checkouts", json_body={"product_id": "prod_1"})
    assert attempts == 1
    assert not sleeps
    await client.aclose()


async def test_post_with_request_id_is_retried(monkeypatch: pytest.MonkeyPatch) -> None:
    attempts = 0
    sleeps = sleep_capture(monkeypatch)

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            return httpx.Response(500, json={})
        return httpx.Response(200, json={})

    client = make_client(handler)
    await client.request(
        "POST", "/v1/checkouts", json_body={"product_id": "p", "request_id": "req_1"}
    )
    assert attempts == 2
    assert len(sleeps) == 1
    await client.aclose()


async def test_idempotent_override_forces_retry(monkeypatch: pytest.MonkeyPatch) -> None:
    attempts = 0
    sleeps = sleep_capture(monkeypatch)

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            return httpx.Response(500, json={})
        return httpx.Response(200, json={})

    client = make_client(handler)
    await client.request("POST", "/v1/checkouts", json_body={"product_id": "p"}, idempotent=True)
    assert attempts == 2
    assert len(sleeps) == 1
    await client.aclose()


async def test_transport_error_is_retried_when_idempotent(monkeypatch: pytest.MonkeyPatch) -> None:
    attempts = 0
    sleeps = sleep_capture(monkeypatch)

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise httpx.ConnectError("connection refused", request=request)
        return httpx.Response(200, json={"ok": True})

    client = make_client(handler)
    assert await client.request("GET", "/v1/products") == {"ok": True}
    assert attempts == 2
    assert len(sleeps) == 1
    await client.aclose()


async def test_transport_error_not_retried_for_plain_post(monkeypatch: pytest.MonkeyPatch) -> None:
    attempts = 0
    sleeps = sleep_capture(monkeypatch)

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        raise httpx.ConnectError("connection refused", request=request)

    client = make_client(handler)
    with pytest.raises(httpx.ConnectError):
        await client.request("POST", "/v1/checkouts", json_body={"product_id": "p"})
    assert attempts == 1
    assert not sleeps
    await client.aclose()


async def test_max_retries_zero_disables_retrying(monkeypatch: pytest.MonkeyPatch) -> None:
    attempts = 0
    sleeps = sleep_capture(monkeypatch)

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        return httpx.Response(500, json={})

    client = make_client(handler, max_retries=0)
    with pytest.raises(CreemServerError):
        await client.request("GET", "/v1/products")
    assert attempts == 1
    assert not sleeps
    await client.aclose()


# --- context manager --------------------------------------------------------


async def test_async_context_manager_closes_client() -> None:
    closed = False

    class TrackingClient(httpx.AsyncClient):
        """AsyncClient that records aclose() calls."""

        async def aclose(self) -> None:
            nonlocal closed
            closed = True
            await super().aclose()

    transport = httpx.MockTransport(
        lambda request: httpx.Response(200, json={})
    )
    async with AsyncCreem(
        "creem_test_key", http_client=TrackingClient(transport=transport)
    ):
        pass
    assert closed
