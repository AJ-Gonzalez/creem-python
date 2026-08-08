"""Client behavior tests: auth, environment detection, error mapping."""

from __future__ import annotations

from typing import Any

import httpx
import pytest

from creem import (
    PROD_BASE_URL,
    TEST_BASE_URL,
    Creem,
    CreemAPIError,
    CreemAuthError,
    CreemConfigurationError,
    CreemNotFoundError,
    CreemRateLimitError,
    CreemServerError,
    CreemValidationError,
)


def make_client(handler: Any, api_key: str = "creem_test_key123", **kwargs: Any) -> Creem:
    transport = httpx.MockTransport(handler)
    http_client = httpx.Client(transport=transport)
    return Creem(api_key, http_client=http_client, **kwargs)


def test_missing_api_key_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("CREEM_API_KEY", raising=False)
    with pytest.raises(CreemConfigurationError, match="API key"):
        Creem()


def test_api_key_from_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CREEM_API_KEY", "creem_test_envkey")

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["x-api-key"] == "creem_test_envkey"
        return httpx.Response(200, json={"ok": True})

    transport = httpx.MockTransport(handler)
    client = Creem(http_client=httpx.Client(transport=transport))
    assert client.request("GET", "/v1/products") == {"ok": True}
    client.close()


def test_test_key_uses_test_base_url() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert str(request.url).startswith(TEST_BASE_URL)
        return httpx.Response(200, json={})

    client = make_client(handler)
    client.request("GET", "/v1/products")
    client.close()


def test_live_key_uses_prod_base_url() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert str(request.url).startswith(PROD_BASE_URL)
        return httpx.Response(200, json={})

    client = make_client(handler, api_key="creem_live_key123")
    client.request("GET", "/v1/products")
    client.close()


def test_explicit_base_url_overrides_key_prefix() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert str(request.url).startswith("https://custom.example.com")
        return httpx.Response(200, json={})

    client = make_client(handler, base_url="https://custom.example.com")
    client.request("GET", "/v1/products")
    client.close()


def test_request_sends_auth_and_accept_headers() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["x-api-key"] == "creem_test_key123"
        assert request.headers["accept"] == "application/json"
        return httpx.Response(200, json={})

    client = make_client(handler)
    client.request("GET", "/v1/products")
    client.close()


def test_json_body_and_params_are_sent() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert request.url.path == "/v1/checkouts"
        assert request.headers["content-type"].startswith("application/json")
        body = httpx.Request.read(request).decode()
        assert '"product_id":"prod_1"' in body
        return httpx.Response(200, json={"id": "ch_1"})

    client = make_client(handler)
    client.request("POST", "/v1/checkouts", json_body={"product_id": "prod_1"})
    client.close()


def test_validation_error_parses_envelope() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
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
        client.request("POST", "/v1/checkouts", json_body={})
    error = excinfo.value
    assert error.status == 400
    assert error.trace_id == "trace-abc"
    assert error.error == "Bad Request"
    assert error.messages == ["The 'product_id' field is required."]
    assert "product_id" in str(error)
    client.close()


def test_auth_error_401_and_403() -> None:
    for status in (401, 403):
        def handler(request: httpx.Request, status: int = status) -> httpx.Response:
            return httpx.Response(
                status, json={"trace_id": "t", "status": status, "error": "Forbidden"}
            )
        client = make_client(handler)
        with pytest.raises(CreemAuthError) as excinfo:
            client.request("GET", "/v1/products")
        assert excinfo.value.status == status
        client.close()


def test_not_found_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, json={"message": ["Product not found"]})

    client = make_client(handler)
    with pytest.raises(CreemNotFoundError):
        client.request("GET", "/v1/products/prod_missing")
    client.close()


def test_rate_limit_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, json={})

    client = make_client(handler)
    with pytest.raises(CreemRateLimitError):
        client.request("GET", "/v1/products")
    client.close()


def test_server_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={})

    client = make_client(handler)
    with pytest.raises(CreemServerError):
        client.request("GET", "/v1/products")
    client.close()


def test_non_json_error_body_falls_back_to_status() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, text="<html>boom</html>")

    client = make_client(handler)
    with pytest.raises(CreemAPIError) as excinfo:
        client.request("GET", "/v1/products")
    assert excinfo.value.status == 503
    assert excinfo.value.messages == []
    client.close()


def test_string_message_is_normalized_to_list() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(400, json={"message": "single string error"})

    client = make_client(handler)
    with pytest.raises(CreemValidationError) as excinfo:
        client.request("GET", "/v1/products")
    assert excinfo.value.messages == ["single string error"]
    client.close()


def test_empty_response_returns_none() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(204)

    client = make_client(handler)
    assert client.request("POST", "/v1/customers", json_body={}) is None
    client.close()


def test_context_manager_closes_client() -> None:
    closed = False

    class TrackingClient(httpx.Client):
        """httpx client that records close() calls."""

        def close(self) -> None:
            nonlocal closed
            closed = True
            super().close()

    transport = httpx.MockTransport(lambda request: httpx.Response(200, json={}))
    with Creem("creem_test_key", http_client=TrackingClient(transport=transport)):
        pass
    assert closed


def test_unknown_status_raises_generic_api_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(418, json={"error": "Teapot"})

    client = make_client(handler)
    with pytest.raises(CreemAPIError) as excinfo:
        client.request("GET", "/v1/products")
    assert excinfo.value.status == 418
    assert not isinstance(excinfo.value, CreemValidationError)
    client.close()
