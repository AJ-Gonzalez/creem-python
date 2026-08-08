"""Webhook module tests: signature verification, parsing, and dispatch."""

from __future__ import annotations

import hashlib
import hmac
import json
from typing import Any

import pytest

from creem import (
    WebhookError,
    WebhookEvent,
    WebhookHandler,
    WebhookPayloadError,
    WebhookSignatureError,
    parse_event,
    verify_signature,
)

SECRET = "whsec_test_secret_123"
BODY = json.dumps(
    {
        "id": "evt_5WHHcZPv7VS0YUsberIuOz",
        "eventType": "subscription.paid",
        "created_at": 1728734325927,
        "object": {
            "id": "sub_6pC2lNB6joCRQIZ1aMrTpi",
            "object": "subscription",
            "status": "active",
        },
    }
).encode()


def sign(body: bytes, secret: str = SECRET) -> str:
    return hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


# --- verify_signature ------------------------------------------------------


def test_verify_signature_matches() -> None:
    assert verify_signature(BODY, sign(BODY), SECRET) is True


def test_verify_signature_rejects_wrong_secret() -> None:
    assert verify_signature(BODY, sign(BODY, "wrong-secret"), SECRET) is False


def test_verify_signature_rejects_tampered_body() -> None:
    tampered = BODY.replace(b'"status": "active"', b'"status": "canceled"')
    assert verify_signature(tampered, sign(BODY), SECRET) is False


def test_verify_signature_accepts_str_body() -> None:
    assert verify_signature(BODY.decode(), sign(BODY), SECRET) is True


# --- parse_event -----------------------------------------------------------


def test_parse_event_returns_envelope() -> None:
    event = parse_event(json.loads(BODY))
    assert event.id == "evt_5WHHcZPv7VS0YUsberIuOz"
    assert event.event_type == "subscription.paid"
    assert event.created_at == 1728734325927
    assert event.object["status"] == "active"


@pytest.mark.parametrize(
    "payload",
    [
        None,
        [],
        {},
        {"id": 1, "eventType": "x", "created_at": 1, "object": {}},
        {"id": "evt_1", "eventType": 2, "created_at": 1, "object": {}},
        {"id": "evt_1", "eventType": "x", "created_at": "now", "object": {}},
        {"id": "evt_1", "eventType": "x", "created_at": 1, "object": []},
    ],
)
def test_parse_event_rejects_malformed(payload: Any) -> None:
    with pytest.raises(WebhookPayloadError):
        parse_event(payload)


def test_parse_event_accepts_unknown_event_type() -> None:
    payload = {"id": "evt_1", "eventType": "future.event", "created_at": 1, "object": {}}
    event = parse_event(payload)
    assert event.event_type == "future.event"


# --- handler dispatch ------------------------------------------------------


def test_handle_dispatches_to_registered_callback() -> None:
    handler = WebhookHandler(SECRET)
    received: list[WebhookEvent] = []
    handler.on("subscription.paid", received.append)
    event = handler.handle(BODY, sign(BODY))
    assert received == [event]
    assert event.event_type == "subscription.paid"


def test_handle_skips_unregistered_events() -> None:
    handler = WebhookHandler(SECRET)
    called: list[str] = []
    handler.on("subscription.canceled", lambda event: called.append(event.event_type))
    handler.handle(BODY, sign(BODY))
    assert called == []


def test_on_accepts_list_of_event_types() -> None:
    handler = WebhookHandler(SECRET)
    called: list[str] = []
    handler.on(["subscription.paid", "subscription.active"], lambda event: called.append(event.event_type))
    handler.handle(BODY, sign(BODY))
    assert called == ["subscription.paid"]


def test_multiple_callbacks_for_one_event() -> None:
    handler = WebhookHandler(SECRET)
    order: list[str] = []
    handler.on("subscription.paid", lambda event: order.append("first"))
    handler.on("subscription.paid", lambda event: order.append("second"))
    handler.handle(BODY, sign(BODY))
    assert order == ["first", "second"]


def test_handle_rejects_bad_signature_before_dispatch() -> None:
    handler = WebhookHandler(SECRET)
    called: list[str] = []
    handler.on("subscription.paid", lambda event: called.append("called"))
    with pytest.raises(WebhookSignatureError):
        handler.handle(BODY, sign(BODY, "wrong"))
    assert called == []


def test_handle_requires_signature() -> None:
    handler = WebhookHandler(SECRET)
    with pytest.raises(WebhookSignatureError, match="Missing"):
        handler.handle(BODY)


def test_handle_reads_signature_from_headers_case_insensitively() -> None:
    handler = WebhookHandler(SECRET)
    received: list[WebhookEvent] = []
    handler.on("subscription.paid", received.append)
    handler.handle(BODY, headers={"Content-Type": "application/json", "Creem-Signature": sign(BODY)})
    assert len(received) == 1


def test_handle_rejects_malformed_json() -> None:
    handler = WebhookHandler(SECRET)
    body = b"{not json"
    with pytest.raises(WebhookPayloadError, match="JSON"):
        handler.handle(body, sign(body))


def test_handle_rejects_async_callback_with_clear_error() -> None:
    handler = WebhookHandler(SECRET)

    async def async_callback(event: WebhookEvent) -> None:
        pass

    handler.on("subscription.paid", async_callback)
    with pytest.raises(WebhookError, match="ahandle"):
        handler.handle(BODY, sign(BODY))


@pytest.mark.anyio
async def test_ahandle_awaits_coroutine_callbacks() -> None:
    handler = WebhookHandler(SECRET)
    order: list[str] = []

    async def async_callback(event: WebhookEvent) -> None:
        order.append("async")

    def sync_callback(event: WebhookEvent) -> None:
        order.append("sync")

    handler.on("subscription.paid", async_callback)
    handler.on("subscription.paid", sync_callback)
    await handler.ahandle(BODY, sign(BODY))
    assert order == ["async", "sync"]


@pytest.mark.anyio
async def test_ahandle_rejects_bad_signature() -> None:
    handler = WebhookHandler(SECRET)
    with pytest.raises(WebhookSignatureError):
        await handler.ahandle(BODY, sign(BODY, "wrong"))


def test_handler_requires_secret() -> None:
    with pytest.raises(WebhookError, match="secret"):
        WebhookHandler("")


# --- end-to-end: real signature over a realistic payload -------------------


def test_end_to_end_checkout_completed() -> None:
    payload = {
        "id": "evt_9fgh",
        "eventType": "checkout.completed",
        "created_at": 1728734325927,
        "object": {
            "id": "ch_4l0N34kxo16AhRKUHFUuXr",
            "object": "checkout",
            "status": "completed",
            "checkout_url": "https://pay.creem.io/ch_4l0N34kxo16AhRKUHFUuXr",
            "order": {"id": "ord_1", "status": "paid"},
            "metadata": {"userId": "user_123"},
        },
    }
    raw = json.dumps(payload).encode()
    handler = WebhookHandler(SECRET)
    granted: dict[str, Any] = {}

    def grant_access(event: WebhookEvent) -> None:
        granted["userId"] = event.object["metadata"]["userId"]
        granted["orderStatus"] = event.object["order"]["status"]

    handler.on("checkout.completed", grant_access)
    handler.handle(raw, sign(raw))
    assert granted == {"userId": "user_123", "orderStatus": "paid"}


def test_handle_headers_without_signature_raises() -> None:
    handler = WebhookHandler(SECRET)
    with pytest.raises(WebhookSignatureError, match="Missing"):
        handler.handle(BODY, headers={"Content-Type": "application/json"})
