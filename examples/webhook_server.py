"""Receive Creem webhooks in FastAPI, with signature verification.

Run with the CREEM_WEBHOOK_SECRET environment variable:

    CREEM_WEBHOOK_SECRET=... uvicorn examples.webhook_server:app

Register the public URL (e.g. via ngrok) in the dashboard under
Developers > Webhook, then complete a test checkout to see the events.
"""

from __future__ import annotations

import os
from functools import lru_cache

from fastapi import FastAPI, Request, Response

from creem import WebhookHandler, WebhookEvent

app = FastAPI()


@lru_cache
def get_handler() -> WebhookHandler:
    secret = os.environ.get("CREEM_WEBHOOK_SECRET", "")
    if not secret:
        raise RuntimeError("Set the CREEM_WEBHOOK_SECRET environment variable")
    handler = WebhookHandler(secret)

    def grant_access(event: WebhookEvent) -> None:
        user_id = event.object.get("metadata", {}).get("userId")
        print(f"Grant access to user {user_id} for {event.event_type}")

    def revoke_access(event: WebhookEvent) -> None:
        customer = event.object.get("customer", {})
        print(f"Revoke access for {customer.get('email')} ({event.event_type})")

    handler.on(["checkout.completed", "subscription.paid"], grant_access)
    handler.on(["subscription.canceled", "subscription.expired"], revoke_access)
    return handler


@app.post("/webhooks/creem")
async def creem_webhook(request: Request) -> Response:
    raw_body = await request.body()
    get_handler().handle(raw_body, headers=request.headers)
    return Response(status_code=200)
