"""Async resource method tests: URL, method, body, and params wiring.

All requests are served by an async httpx.MockTransport; nothing hits the
network.
"""

from __future__ import annotations

import json
from collections.abc import Coroutine
from typing import Callable

import httpx
import pytest

from creem import AsyncCreem
from creem.models import CreditDebitParams

pytestmark = pytest.mark.anyio


def make_client(
    handler: Callable[[httpx.Request], httpx.Response]
    | Callable[[httpx.Request], Coroutine[None, None, httpx.Response]],
) -> AsyncCreem:
    transport = httpx.MockTransport(handler)
    return AsyncCreem("creem_test_key123", http_client=httpx.AsyncClient(transport=transport))


def capture() -> tuple[list[httpx.Request], AsyncCreem]:
    """Return a request recorder and an async client wired to it."""
    requests: list[httpx.Request] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json={})

    return requests, make_client(handler)


async def test_products_create_sends_body_and_idempotency_header() -> None:
    requests, client = capture()
    await client.products.create(
        {
            "name": "Pro",
            "description": "Pro plan",
            "price": 1999,
            "currency": "USD",
            "billing_type": "recurring",
        },
        billing_period="every-month",
        idempotency_key="idem-1",
    )
    request = requests[0]
    assert request.method == "POST"
    assert request.url.path == "/v1/products"
    assert request.headers["Idempotency-Key"] == "idem-1"
    body = json.loads(request.content)
    assert body["name"] == "Pro"
    assert body["billing_period"] == "every-month"
    await client.aclose()


async def test_kwargs_only_style_works_for_body_methods() -> None:
    requests, client = capture()
    await client.checkouts.create(product_id="prod_1", success_url="https://x.dev/s")
    await client.customers.create(email="kw@example.com", name="Kwargs User")
    await client.licenses.activate(key="ABC123-XYZ456-XYZ456-XYZ456", instance_name="laptop")
    await client.credits.credit("cca_1", amount="5", reference="ref", idempotency_key="idem")
    assert json.loads(requests[0].content) == {
        "product_id": "prod_1",
        "success_url": "https://x.dev/s",
    }
    assert json.loads(requests[1].content)["email"] == "kw@example.com"
    assert json.loads(requests[2].content)["instance_name"] == "laptop"
    assert json.loads(requests[3].content)["amount"] == "5"
    await client.aclose()


async def test_checkout_flow_returns_checkout_url() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "id": "ch_4l0N34kxo16AhRKUHFUuXr",
                "object": "checkout",
                "status": "pending",
                "checkout_url": "https://pay.creem.io/ch_4l0N34kxo16AhRKUHFUuXr",
            },
        )

    client = make_client(handler)
    checkout = await client.checkouts.create({"product_id": "prod_1"})
    assert checkout["checkout_url"].startswith("https://pay.creem.io/")
    await client.aclose()


async def test_customers_get_by_email_only() -> None:
    requests, client = capture()
    await client.customers.get(email="user@example.com")
    assert requests[0].url.path == "/v1/customers"
    assert requests[0].url.params["email"] == "user@example.com"
    assert "customer_id" not in requests[0].url.params
    await client.aclose()


async def test_subscription_cancel_scheduled_mode() -> None:
    requests, client = capture()
    await client.subscriptions.cancel("sub_1", {"mode": "scheduled"})
    request = requests[0]
    assert request.method == "POST"
    assert request.url.path == "/v1/subscriptions/sub_1/cancel"
    assert json.loads(request.content) == {"mode": "scheduled"}
    await client.aclose()


async def test_subscription_lifecycle_paths() -> None:
    requests, client = capture()
    await client.subscriptions.pause("sub_1")
    await client.subscriptions.resume("sub_1")
    await client.subscriptions.upgrade("sub_1", {"product_id": "prod_2"})
    paths = [r.url.path for r in requests]
    assert paths == [
        "/v1/subscriptions/sub_1/pause",
        "/v1/subscriptions/sub_1/resume",
        "/v1/subscriptions/sub_1/upgrade",
    ]
    await client.aclose()


async def test_transactions_search_filters() -> None:
    requests, client = capture()
    await client.transactions.search(customer_id="cust_1", product_id="prod_2")
    query = requests[0].url.params
    assert query["customer_id"] == "cust_1"
    assert query["product_id"] == "prod_2"
    assert "order_id" not in query
    await client.aclose()


async def test_stats_summary_maps_snake_case_to_camel_case() -> None:
    requests, client = capture()
    await client.stats.summary(
        currency="USD",
        start_date=1740614400000,
        end_date=1772150400000,
        interval="month",
    )
    query = requests[0].url.params
    assert query["startDate"] == "1740614400000"
    assert query["interval"] == "month"
    await client.aclose()


async def test_credits_credit_debit_paths_and_body() -> None:
    requests, client = capture()
    payload: CreditDebitParams = {
        "amount": "100",
        "reference": "signup_bonus",
        "idempotency_key": "idem_1",
    }
    await client.credits.credit("cca_1", payload)
    await client.credits.debit("cca_1", payload)
    await client.credits.reverse("cca_1", {"transaction_id": "tran_9"})
    assert requests[0].url.path == "/v1/customer-credits/accounts/cca_1/credit"
    assert requests[1].url.path == "/v1/customer-credits/accounts/cca_1/debit"
    assert requests[2].url.path == "/v1/customer-credits/accounts/cca_1/reverse"
    assert json.loads(requests[2].content) == {"transaction_id": "tran_9"}
    await client.aclose()


async def test_credits_account_lifecycle_paths() -> None:
    requests, client = capture()
    await client.credits.create_account(
        {"customer_id": "cust_1", "name": "points", "unit_label": "points"}
    )
    await client.credits.get_account("cca_1")
    await client.credits.freeze("cca_1")
    await client.credits.unfreeze("cca_1")
    await client.credits.close("cca_1")
    paths = [r.url.path for r in requests]
    assert paths == [
        "/v1/customer-credits/accounts",
        "/v1/customer-credits/accounts/cca_1",
        "/v1/customer-credits/accounts/cca_1/freeze",
        "/v1/customer-credits/accounts/cca_1/unfreeze",
        "/v1/customer-credits/accounts/cca_1/close",
    ]
    await client.aclose()


async def test_licenses_validate_body() -> None:
    requests, client = capture()
    await client.licenses.validate({"key": "ABC123-XYZ456-XYZ456-XYZ456", "instance_id": "inst_1"})
    assert requests[0].url.path == "/v1/licenses/validate"
    assert json.loads(requests[0].content)["instance_id"] == "inst_1"
    await client.aclose()


async def test_discounts_get_by_code_and_delete() -> None:
    requests, client = capture()
    await client.discounts.get(discount_code="LAUNCH20")
    await client.discounts.delete("disc_1")
    assert requests[0].url.params["discount_code"] == "LAUNCH20"
    assert requests[1].url.path == "/v1/discounts/disc_1/delete"
    await client.aclose()


async def test_refunds_create() -> None:
    requests, client = capture()
    await client.refunds.create({"transaction_id": "tran_1"})
    assert requests[0].method == "POST"
    assert requests[0].url.path == "/v1/refunds"
    assert json.loads(requests[0].content) == {"transaction_id": "tran_1"}
    await client.aclose()


async def test_affiliates_commissions_status_filter() -> None:
    requests, client = capture()
    await client.affiliates.commissions("aff_1", status="paid")
    assert requests[0].url.path == "/v1/affiliates/aff_1/commissions"
    assert requests[0].url.params["status"] == "paid"
    await client.aclose()


async def test_moderation_screen() -> None:
    requests, client = capture()
    await client.moderation.screen({"prompt": "a cute robot"})
    assert requests[0].url.path == "/v1/moderation/prompt"
    assert json.loads(requests[0].content)["prompt"] == "a cute robot"
    await client.aclose()


async def test_error_propagates_through_resource_methods() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, json={"message": ["Product not found"]})

    client = make_client(handler)
    with pytest.raises(Exception) as excinfo:
        await client.products.get("prod_missing")
    assert excinfo.value.status == 404  # type: ignore[attr-defined]
    await client.aclose()
