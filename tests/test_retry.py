"""Retry/backoff behavior tests.

All delays are short-circuited by monkeypatching ``time.sleep``; nothing
waits for real backoff.
"""

from __future__ import annotations

from typing import Any, Callable

import httpx
import pytest

from creem import Creem, CreemServerError


def make_client(
    handler: Callable[[httpx.Request], httpx.Response],
    **kwargs: Any,
) -> Creem:
    transport = httpx.MockTransport(handler)
    return Creem("creem_test_key", http_client=httpx.Client(transport=transport), **kwargs)


def sleep_capture(monkeypatch: pytest.MonkeyPatch) -> list[float]:
    """Replace time.sleep with a recorder; returns the recorded delays."""
    sleeps: list[float] = []

    def fake_sleep(seconds: float) -> None:
        sleeps.append(seconds)

    monkeypatch.setattr("time.sleep", fake_sleep)
    return sleeps


def test_get_retries_5xx_then_succeeds(monkeypatch: pytest.MonkeyPatch) -> None:
    attempts = 0
    sleeps = sleep_capture(monkeypatch)

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            return httpx.Response(500, json={})
        return httpx.Response(200, json={"ok": True})

    client = make_client(handler)
    assert client.request("GET", "/v1/products") == {"ok": True}
    assert attempts == 2
    assert len(sleeps) == 1
    assert 0.5 * 0.5 <= sleeps[0] <= 0.5  # backoff_base * jitter range
    client.close()


def test_get_retries_429_respecting_retry_after(monkeypatch: pytest.MonkeyPatch) -> None:
    attempts = 0
    sleeps = sleep_capture(monkeypatch)

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            return httpx.Response(429, headers={"Retry-After": "2.5"}, json={})
        return httpx.Response(200, json={})

    client = make_client(handler)
    client.request("GET", "/v1/products")
    assert attempts == 2
    assert sleeps[0] >= 2.5  # never below Retry-After
    client.close()


def test_retries_exhausted_raises_server_error(monkeypatch: pytest.MonkeyPatch) -> None:
    attempts = 0
    sleeps = sleep_capture(monkeypatch)

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        return httpx.Response(503, json={})

    client = make_client(handler, max_retries=2)
    with pytest.raises(CreemServerError):
        client.request("GET", "/v1/products")
    assert attempts == 3  # initial + 2 retries
    assert len(sleeps) == 2
    assert sleeps[0] < sleeps[1]  # exponential growth
    client.close()


def test_4xx_is_never_retried(monkeypatch: pytest.MonkeyPatch) -> None:
    attempts = 0
    sleeps = sleep_capture(monkeypatch)

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        return httpx.Response(400, json={"message": ["nope"]})

    client = make_client(handler)
    with pytest.raises(Exception):
        client.request("GET", "/v1/products")
    assert attempts == 1
    assert sleeps == []
    client.close()


def test_post_without_idempotency_is_not_retried(monkeypatch: pytest.MonkeyPatch) -> None:
    attempts = 0
    sleeps = sleep_capture(monkeypatch)

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        return httpx.Response(500, json={})

    client = make_client(handler)
    with pytest.raises(CreemServerError):
        client.request("POST", "/v1/checkouts", json_body={"product_id": "prod_1"})
    assert attempts == 1
    assert sleeps == []
    client.close()


def test_post_with_idempotency_key_in_body_is_retried(monkeypatch: pytest.MonkeyPatch) -> None:
    attempts = 0
    sleeps = sleep_capture(monkeypatch)

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            return httpx.Response(500, json={})
        return httpx.Response(200, json={"id": "tran_1"})

    client = make_client(handler)
    result: Any = client.request(
        "POST",
        "/v1/customer-credits/accounts/cca_1/credit",
        json_body={"amount": "10", "reference": "r", "idempotency_key": "idem_1"},
    )
    assert result == {"id": "tran_1"}
    assert attempts == 2
    assert len(sleeps) == 1
    client.close()


def test_post_with_request_id_is_retried(monkeypatch: pytest.MonkeyPatch) -> None:
    attempts = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        return httpx.Response(500, json={}) if attempts == 1 else httpx.Response(200, json={})

    sleeps = sleep_capture(monkeypatch)
    client = make_client(handler)
    client.request("POST", "/v1/checkouts", json_body={"product_id": "p", "request_id": "req_1"})
    assert attempts == 2
    assert len(sleeps) == 1
    client.close()


def test_post_with_idempotency_header_is_retried(monkeypatch: pytest.MonkeyPatch) -> None:
    attempts = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        return httpx.Response(500, json={}) if attempts == 1 else httpx.Response(200, json={})

    sleeps = sleep_capture(monkeypatch)
    client = make_client(handler)
    client.request("POST", "/v1/products", json_body={}, headers={"Idempotency-Key": "k1"})
    assert attempts == 2
    assert len(sleeps) == 1
    client.close()


def test_idempotent_override_forces_retry(monkeypatch: pytest.MonkeyPatch) -> None:
    attempts = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        return httpx.Response(500, json={}) if attempts == 1 else httpx.Response(200, json={})

    sleeps = sleep_capture(monkeypatch)
    client = make_client(handler)
    client.request("POST", "/v1/checkouts", json_body={"product_id": "p"}, idempotent=True)
    assert attempts == 2
    assert len(sleeps) == 1
    client.close()


def test_transport_error_is_retried_when_idempotent(monkeypatch: pytest.MonkeyPatch) -> None:
    attempts = 0
    sleeps = sleep_capture(monkeypatch)

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise httpx.ConnectError("connection refused", request=request)
        return httpx.Response(200, json={"ok": True})

    client = make_client(handler)
    assert client.request("GET", "/v1/products") == {"ok": True}
    assert attempts == 2
    assert len(sleeps) == 1
    client.close()


def test_transport_error_not_retried_for_plain_post(monkeypatch: pytest.MonkeyPatch) -> None:
    attempts = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        raise httpx.ConnectError("connection refused", request=request)

    sleeps = sleep_capture(monkeypatch)
    client = make_client(handler)
    with pytest.raises(httpx.ConnectError):
        client.request("POST", "/v1/checkouts", json_body={"product_id": "p"})
    assert attempts == 1
    assert sleeps == []
    client.close()


def test_max_retries_zero_disables_retrying(monkeypatch: pytest.MonkeyPatch) -> None:
    attempts = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        return httpx.Response(500, json={})

    sleeps = sleep_capture(monkeypatch)
    client = make_client(handler, max_retries=0)
    with pytest.raises(CreemServerError):
        client.request("GET", "/v1/products")
    assert attempts == 1
    assert sleeps == []
    client.close()


def test_retry_sends_same_body_and_headers(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: list[httpx.Request] = []
    sleeps = sleep_capture(monkeypatch)

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        if len(captured) == 1:
            return httpx.Response(502, json={})
        return httpx.Response(200, json={})

    client = make_client(handler)
    client.request(
        "POST",
        "/v1/checkouts",
        json_body={"product_id": "p", "request_id": "req_1"},
        headers={"X-Custom": "v"},
    )
    assert len(captured) == 2
    assert captured[0].content == captured[1].content
    assert captured[0].headers["x-api-key"] == captured[1].headers["x-api-key"] == "creem_test_key"
    assert captured[0].headers["X-Custom"] == captured[1].headers["X-Custom"] == "v"
    assert len(sleeps) == 1
    client.close()
