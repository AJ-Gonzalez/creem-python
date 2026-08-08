# Creem SDK Guide for Agents

This guide explains the creem Python SDK to an AI agent that must use it, extend it, or help a human integrate it. Read `API_REFERENCE.md` for the complete API contract; this document explains the SDK's design and the conventions that the reference does not repeat.

## What the SDK Is

`creem` is a typed wrapper around the Creem REST API (https://api.creem.io/v1). One client object exposes twelve resource groups. Every endpoint has a typed method. Every response is a TypedDict with full field hints. Every error is a typed exception carrying the API's `trace_id`.

## File Map

| Path | Purpose |
|---|---|
| `src/creem/client.py` | The `Creem` client: auth, environment detection, retries, error mapping |
| `src/creem/resources/` | One module per resource (products, checkouts, customers, subscriptions, transactions, discounts, licenses, credits, refunds, affiliates, stats, moderation) |
| `src/creem/models.py` | Generated TypedDicts for every request and response shape. Do not edit by hand; regenerate with `python scripts/generate_models.py` |
| `src/creem/errors.py` | Exception hierarchy |
| `src/creem/webhooks.py` | Webhook verification, parsing, dispatch |
| `scripts/generate_models.py` | Regenerates `models.py` from the official OpenAPI spec |
| `examples/` | Runnable example scripts |
| `API_REFERENCE.md` | Every endpoint, schema, webhook event, error |

## Core Concepts

### Client

```python
from creem import Creem

creem = Creem()  # reads CREEM_API_KEY from the environment
```

The environment is derived from the key prefix: `creem_test_` targets `https://test-api.creem.io`, anything else targets production. Pass `base_url` to override. Pass `max_retries=0` to disable retrying; pass `timeout` to change the request timeout.

### Resources

`creem.products`, `creem.checkouts`, `creem.customers`, `creem.subscriptions`, `creem.transactions`, `creem.discounts`, `creem.licenses`, `creem.credits`, `creem.refunds`, `creem.affiliates`, `creem.stats`, `creem.moderation`. That is all 49 endpoints.

### Request Payloads

Methods that send a body take a params TypedDict first, plus `**kwargs` overrides:

```python
creem.checkouts.create({"product_id": "prod_1", "success_url": "https://x.dev/s"})
creem.checkouts.create({"product_id": "prod_1"}, success_url="https://x.dev/s")
```

Keyword arguments win over params entries. Required fields are marked `Required[...]` in the TypedDict; mypy enforces them.

### Response Models

Responses are TypedDicts with `total=False`: every field is optional, because real payloads vary (webhook samples prove it). Access fields with `.get()` when they may be absent, or subscript when the API contract guarantees them (e.g. `checkout["checkout_url"]` on a create response).

### Errors

| Exception | Status | Meaning |
|---|---|---|
| `CreemValidationError` | 400 | Invalid parameters |
| `CreemAuthError` | 401/403 | Missing or invalid API key |
| `CreemNotFoundError` | 404 | Resource does not exist |
| `CreemRateLimitError` | 429 | Rate limit exceeded |
| `CreemServerError` | 5xx | API failed |
| `CreemAPIError` | any | Base for the above; carries `status`, `trace_id`, `error`, `messages` |

Include `trace_id` in support requests.

### Retries

Retries are automatic: 429, 5xx, and network errors, up to 3 times, exponential backoff with jitter, honoring `Retry-After`. Only idempotent-safe requests are retried by default: GET requests, and requests carrying `request_id`, `idempotency_key`, or an `Idempotency-Key` header. Pass `idempotent=True` to `request()` to force retrying.

### Pagination

Two API styles exist; the SDK hides both. `iter_*` methods yield every item across pages:

```python
for txn in creem.transactions.iter_all(customer_id="cust_1"):
    ...
```

`products.iter_all`, `transactions.iter_all`, `subscriptions.iter_all`, `discounts.iter_all`, `customers.iter_all/iter_orders/iter_subscriptions/iter_licenses`, `affiliates.iter_all/iter_commissions`, `licenses.iter_instances`, `credits.iter_accounts/iter_entries`. Default page size is 100; iteration is lazy.

## Integration Flows

### Checkout

1. Create a checkout: `creem.checkouts.create({"product_id": ..., "success_url": ...})`
2. Redirect the customer to `checkout["checkout_url"]`
3. Grant access on `checkout.completed` (one-time) or `subscription.paid` (recurring) webhooks
4. Pass `metadata` (e.g. `{"userId": ...}`) to map payments to internal users; it flows through to webhooks

### Subscriptions

Cancel at period end, not immediately: `creem.subscriptions.cancel("sub_1", {"mode": "scheduled"})`. Pause, resume, update items, and upgrade products are separate methods. The statuses: `active`, `trialing`, `paused`, `past_due`, `expired`, `canceled`, `scheduled_cancel`, `unpaid`.

### Webhooks

```python
from creem import WebhookHandler

handler = WebhookHandler(secret="...")
handler.on("subscription.paid", grant_access)
handler.on(["subscription.canceled", "subscription.expired"], revoke_access)

# sync endpoint: handler.handle(raw_body, signature_or_headers)
# async endpoint: await handler.ahandle(raw_body, headers=request.headers)
```

The signature is HMAC-SHA256 of the raw body; verification is constant-time and happens before any callback. There are no static source IPs — the signature is the only authentication. Webhook retries: 30s, 1m, 5m, 1h.

### Licenses

Keys are `XXXXXX-XXXXXX-XXXXXX-XXXXXX` strings. `activate` with `instance_name`, `validate` with `key` + `instance_id` (grant access only when `status == "active"`), `deactivate` to free a slot.

### Customer Credits

Experimental API. `create_account` (optionally with `initial_balance`), `credit`, `debit`, `reverse`, `balance`, `entries`. Amounts are strings (bigint safety). `credit`/`debit` require an `idempotency_key`.

## Conventions and Gotchas

- All monetary amounts are integer **cents**. Supported currencies: `USD`, `EUR`.
- Test cards: `4111 1111 1111 1111` succeeds; `4507 9900 0000 0028` declines.
- Idempotency has three mechanisms: `Idempotency-Key` header (products create), `idempotency_key` in the body (credits), `request_id` in the body (checkouts). Use one whenever a retry could double-charge.
- `stats.summary` uses camelCase query params (`startDate`, `endDate`) exposed as `start_date`, `end_date` in the SDK.
- An unknown but well-formed `product_id` in a checkout returns **404** (the API looks the product up), not 400. Wrong types return 400.
- Discount **creation** may be feature-gated on a store: the API returns 403 with error category "Bad Request" and no message. Search and reads work.
- The customer-credits and moderation APIs are tagged experimental in the official spec and may change.
- `subscriptions.search` accepts a `status` filter used by the API's documentation, though the OpenAPI spec omits it.
- The SDK is sync-only for REST. Async webhook callbacks use `ahandle`.

## Development

```bash
pip install -e ".[dev]"
pytest            # mock suite (no network)
pytest -m live    # live suite against test-api.creem.io; needs the
                  # gitignored .env file with CREEM_API_KEY
mypy              # strict type check
flake8 src tests scripts examples
pylint src tests scripts examples
python scripts/generate_models.py  # regenerate models.py from the spec
```

Live tests create and clean up their own resources in the sandbox. Some endpoints cannot be live-tested without a completed payment (subscription lifecycle, refunds, licenses); they are mock-tested only.

CI runs the live suite on every push to `main` (and on tags) when the
`CREEM_API_KEY` repository secret is set — the same test key from the
gitignored `.env` file, stored as a GitHub secret.

## Rules for Agents Editing This SDK

- Read `AGENTS.md` first; its guidelines apply (type hints mandatory, read before edit, STE-flat docs).
- Do not edit `src/creem/models.py` by hand. Change `scripts/generate_models.py` and regenerate, then verify with `mypy` and the test suite.
- New endpoints appear in the spec before the SDK: regenerate models, then add the resource method.
- Keep the README quickstart warm but the reference docs STE-flat.
