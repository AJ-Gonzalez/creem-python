# Unofficial Creem.io Python SDK

A comfy python wrapper around the Creem REST API. 

Will hopefully be official at some point. 

Supports both sync and async flows. 

**Status: alpha.** 

Expect mostly minor changes before 1.0. 

The author is dogfooding it with at least one real product.

Shoutout to [Creem](https://creem.io) for being cool, hope they see this. 

***If the community at large needs python 3.8 support it will be added, otherwise it's 3.11 or above.***

## Installing

Requires Python 3.11+.

```bash
pip install creem
```

For development, install from the repo with test tooling:

```bash
pip install -e ".[dev]"
```

## Quickstart

Grab your API key from the [dashboard](https://creem.io/dashboard/developers), then:

```python
from creem import Creem

creem = Creem()  # reads CREEM_API_KEY from the environment
```

Test keys (`creem_test_...`) automatically target the sandbox at `test-api.creem.io` — no config needed. Live keys (`creem_...`) hit production. Async backends use `AsyncCreem` — same API, everything awaited (`await creem.checkouts.create(...)`).

**Sell something.** Create a checkout session and send your customer to the hosted payment page:

```python
checkout = creem.checkouts.create({
    "product_id": "prod_abc123",
    "success_url": "https://yourapp.com/success",
    "metadata": {"userId": "user_123"},  # flows through to webhooks
})

print(checkout["checkout_url"])  # redirect the customer here
```

**Know when it's paid.** Handle the `checkout.completed` (one-time) and `subscription.paid` (recurring) webhooks to grant access — the payloads carry your `metadata` back. Signatures are verified for you:

```python
from creem import WebhookHandler

handler = WebhookHandler(secret="your webhook secret")
handler.on("subscription.paid", grant_access)
handler.on("subscription.canceled", revoke_access)

# FastAPI: handler.handle(await request.body(), request.headers.get("creem-signature"))
# Async callbacks: await handler.ahandle(...)
```

**Keep customers happy.** Cancel at period end, not instantly:

```python
creem.subscriptions.cancel("sub_abc123", {"mode": "scheduled"})
```

Every response is a typed dict with full field hints (models import from the top level: `from creem import Checkout, Subscription, ...`). When the API complains, you get a `CreemAPIError` carrying the `trace_id` — include it when contacting support.

Retries are automatic: rate limits (429), server errors, and network failures are retried up to 3 times with exponential backoff and jitter — when it's safe to do so (GETs and requests carrying `request_id`, `idempotency_key`, or an `Idempotency-Key` header). Pass `max_retries=0` to `Creem(...)` to disable.

## Examples

Runnable scripts live in [`examples/`](examples/) — set `CREEM_API_KEY` (test keys target the sandbox) and run them directly:

| Example | What it shows |
|---|---|
| `checkout_flow.py` | Create a product, create a checkout, print the payment URL |
| `subscription_management.py` | Search, scheduled cancel, pause, resume |
| `webhook_server.py` | FastAPI endpoint with signature verification and grant/revoke dispatch |
| `customer_credits.py` | Wallet: create account, credit, balance |
| `browse_and_paginate.py` | Pagination iterators over products and transactions |
| `async_checkout_flow.py` | The same flow with `AsyncCreem` — for async backends |

```bash
CREEM_API_KEY=creem_test_... python examples/checkout_flow.py
```

## API Reference

See the full reference in [API_REFERENCE](API_REFERENCE.md)

## Documentation for Agents

AI agents integrating or extending this SDK should read [docs/for-agents.md](docs/for-agents.md) — it covers the mental model, conventions, integration flows, and gotchas. For the complete API contract, see [API_REFERENCE.md](API_REFERENCE.md). Release history: [CHANGELOG.md](CHANGELOG.md).


## Contributing

Please raise any issues you have. Feature requests are welcome as well. 
PR's welcome. 
