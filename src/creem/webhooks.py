"""Webhook verification, parsing, and dispatch for Creem events.

Creem delivers events as POST requests to your HTTPS endpoint. The signature
is in the ``creem-signature`` header: the hex HMAC-SHA256 of the **raw
request body**, keyed with your webhook secret (dashboard > Developers >
Webhook). Verify every request before processing — Creem does not provide
static source IPs, so the signature is the only authentication.

Typical FastAPI flow::

    from creem import WebhookHandler

    handler = WebhookHandler(secret="...")
    handler.on("subscription.paid", grant_access)
    handler.on("subscription.canceled", revoke_access)

    @app.post("/webhooks/creem")
    async def creem_webhook(request: Request) -> Response:
        raw = await request.body()
        handler.handle(raw, request.headers.get("creem-signature"))
        return Response(status_code=200)

``handle`` verifies the signature, parses the envelope, and dispatches to the
registered callbacks. If your callbacks are coroutine functions, use
``await handler.ahandle(...)`` instead. Both return the parsed
:class:`WebhookEvent` (also delivered to each callback) so you can chain
further processing.
"""

from __future__ import annotations

import hashlib
import hmac
import inspect
import json
from dataclasses import dataclass
from typing import Any, Callable, Iterable, Literal, Mapping

from .errors import CreemError

EventType = Literal[
    "checkout.completed",
    "subscription.active",
    "subscription.paid",
    "subscription.canceled",
    "subscription.scheduled_cancel",
    "subscription.past_due",
    "subscription.unpaid",
    "subscription.expired",
    "subscription.trialing",
    "subscription.paused",
    "subscription.update",
    "refund.created",
    "dispute.created",
]

_SIGNATURE_HEADER = "creem-signature"


class WebhookError(CreemError):
    """Base class for webhook processing failures."""


class WebhookSignatureError(WebhookError):
    """The request is missing a signature or the signature does not match."""


class WebhookPayloadError(WebhookError):
    """The event payload does not match the expected envelope shape."""


@dataclass(frozen=True)
class WebhookEvent:
    """A parsed webhook envelope.

    Attributes:
        id: The event identifier (``evt_...``).
        event_type: The event name, e.g. ``"subscription.paid"``. May be an
            event type newer than this SDK knows; compare as a string.
        created_at: Unix timestamp in milliseconds.
        object: The event payload — the entity TypedDict documented for the
            event (e.g. :class:`creem.models.Checkout` for
            ``checkout.completed``). Its concrete type depends on
            ``event_type``.
    """

    id: str
    event_type: str
    created_at: int
    object: Any


def verify_signature(raw_body: str | bytes, signature: str, secret: str) -> bool:
    """Return whether ``signature`` matches the HMAC-SHA256 of ``raw_body``.

    ``raw_body`` must be the body exactly as received — do not re-serialize
    parsed JSON. The comparison is constant-time.
    """
    if isinstance(raw_body, str):
        raw_body = raw_body.encode()
    expected = hmac.new(secret.encode(), raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


def parse_event(payload: Mapping[str, Any]) -> WebhookEvent:
    """Validate and parse a webhook envelope.

    Raises :class:`WebhookPayloadError` when the payload is malformed.
    """
    if not isinstance(payload, Mapping):
        raise WebhookPayloadError(
            f"Webhook payload must be a JSON object, got {type(payload).__name__}"
        )
    event_id = payload.get("id")
    event_type = payload.get("eventType")
    created_at = payload.get("created_at")
    event_object = payload.get("object")
    if not isinstance(event_id, str):
        raise WebhookPayloadError("Webhook payload is missing a string 'id' field")
    if not isinstance(event_type, str):
        raise WebhookPayloadError("Webhook payload is missing a string 'eventType' field")
    if not isinstance(created_at, int):
        raise WebhookPayloadError("Webhook payload is missing an integer 'created_at' field")
    if not isinstance(event_object, Mapping):
        raise WebhookPayloadError("Webhook payload is missing an object 'object' field")
    return WebhookEvent(
        id=event_id, event_type=event_type, created_at=created_at, object=dict(event_object)
    )


Callback = Callable[[WebhookEvent], Any]


class WebhookHandler:
    """Verify, parse, and dispatch Creem webhook events.

    Args:
        secret: The webhook secret from the dashboard (Developers > Webhook).
    """

    def __init__(self, secret: str) -> None:
        if not secret:
            raise WebhookError("WebhookHandler requires a non-empty secret")
        self._secret = secret
        self._handlers: dict[str, list[Callback]] = {}

    def on(self, event_type: str | Iterable[str], callback: Callback) -> None:
        """Register a callback for one or more event types.

        Unknown event types are accepted: Creem may add events faster than
        this SDK is updated.
        """
        types = [event_type] if isinstance(event_type, str) else list(event_type)
        for event in types:
            self._handlers.setdefault(event, []).append(callback)

    def handle(
        self,
        raw_body: str | bytes,
        signature: str | None = None,
        *,
        headers: Mapping[str, str] | None = None,
    ) -> WebhookEvent:
        """Verify, parse, and dispatch one webhook request.

        Pass the signature from the ``creem-signature`` header directly, or
        pass the request headers to look it up case-insensitively.

        Raises :class:`WebhookSignatureError` when the signature is missing
        or does not match, :class:`WebhookPayloadError` for malformed
        payloads, and :class:`WebhookError` when a registered callback is a
        coroutine function (use :meth:`ahandle` for those).
        """
        event = self._parse_verified(raw_body, signature, headers)
        for callback in self._handlers.get(event.event_type, []):
            if inspect.iscoroutinefunction(callback):
                raise WebhookError(
                    f"Callback for {event.event_type!r} is a coroutine function; "
                    "use await handler.ahandle(...) instead"
                )
            callback(event)
        return event

    async def ahandle(
        self,
        raw_body: str | bytes,
        signature: str | None = None,
        *,
        headers: Mapping[str, str] | None = None,
    ) -> WebhookEvent:
        """Async variant of :meth:`handle`: awaits coroutine callbacks and
        calls plain callbacks directly."""
        event = self._parse_verified(raw_body, signature, headers)
        for callback in self._handlers.get(event.event_type, []):
            result = callback(event)
            if inspect.isawaitable(result):
                await result
        return event

    def _parse_verified(
        self,
        raw_body: str | bytes,
        signature: str | None,
        headers: Mapping[str, str] | None,
    ) -> WebhookEvent:
        if signature is None:
            if headers is None:
                raise WebhookSignatureError(
                    "Missing webhook signature: pass the 'creem-signature' header value"
                )
            for key, value in headers.items():
                if key.lower() == _SIGNATURE_HEADER:
                    signature = value
                    break
        if signature is None:
            raise WebhookSignatureError("Missing 'creem-signature' header on the webhook request")
        if not verify_signature(raw_body, signature, self._secret):
            raise WebhookSignatureError(
                "Webhook signature verification failed: the request is not authentic"
            )
        if isinstance(raw_body, str):
            raw_body = raw_body.encode()
        try:
            payload = json.loads(raw_body)
        except ValueError as exc:
            raise WebhookPayloadError(f"Webhook body is not valid JSON: {exc}") from exc
        return parse_event(payload)
