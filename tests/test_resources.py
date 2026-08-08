"""Resource method tests: URL, method, body, and params wiring.

All requests are served by an httpx.MockTransport; nothing hits the network.
"""

from creem import Creem
from creem.models import CreditDebitParams
import json
from typing import Any, Callable

import httpx
import pytest

from creem import Creem


def make_client(handler: Callable[[httpx.Request], httpx.Response]) -> Creem:
    transport = httpx.MockTransport(handler)
    return Creem("creem_test_key123", http_client=httpx.Client(transport=transport))


def capture() -> tuple[list[httpx.Request], Creem]:
    """Return a request recorder and a client wired to it."""
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json={})

    return requests, make_client(handler)


def test_products_create_sends_body_and_idempotency_header() -> None:
    requests, client = capture()
    client.products.create(
        {"name": "Pro", "description": "Pro plan", "price": 1999, "currency": "USD", "billing_type": "recurring"},
        billing_period="every-month",
        idempotency_key="idem-1",
    )
    request = requests[0]
    assert request.method == "POST"
    assert request.url.path == "/v1/products"
    assert request.headers["Idempotency-Key"] == "idem-1"
    body = json.loads(request.content)
    assert body["name"] == "Pro"
    assert body["price"] == 1999
    assert body["billing_period"] == "every-month"  # kwargs override/extend params
    client.close()


def test_products_get_and_archive_paths() -> None:
    requests, client = capture()
    client.products.get("prod_1")
    client.products.archive("prod_1")
    assert requests[0].method == "GET"
    assert requests[0].url.path == "/v1/products/prod_1"
    assert requests[1].method == "DELETE"
    assert requests[1].url.path == "/v1/products/prod_1"
    client.close()


def test_products_search_query_params_dropped_when_none() -> None:
    requests, client = capture()
    client.products.search()
    assert requests[0].url.query.decode() == ""
    client.products.search(page_number=2, page_size=50, status="active")
    assert requests[1].url.query.decode() == "page_number=2&page_size=50&status=active"
    client.close()


def test_checkouts_create_and_get() -> None:
    requests, client = capture()
    client.checkouts.create({"product_id": "prod_1", "success_url": "https://x.dev/s"})
    client.checkouts.get("ch_9")
    assert requests[0].method == "POST"
    assert requests[0].url.path == "/v1/checkouts"
    body = json.loads(requests[0].content)
    assert body["success_url"] == "https://x.dev/s"
    assert requests[1].url.path == "/v1/checkouts"
    assert requests[1].url.params["checkout_id"] == "ch_9"
    client.close()


def test_checkout_create_returns_checkout_url() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
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
    checkout = client.checkouts.create({"product_id": "prod_1"})
    assert checkout["checkout_url"].startswith("https://pay.creem.io/")
    client.close()


def test_customers_get_by_email_only() -> None:
    requests, client = capture()
    client.customers.get(email="user@example.com")
    assert requests[0].url.path == "/v1/customers"
    assert requests[0].url.params["email"] == "user@example.com"
    assert "customer_id" not in requests[0].url.params
    client.close()


def test_customers_update_requires_customer_id_in_body() -> None:
    requests, client = capture()
    client.customers.update({"customer_id": "cust_1", "name": "New Name"})
    assert requests[0].method == "PATCH"
    assert json.loads(requests[0].content)["customer_id"] == "cust_1"
    client.close()


def test_subscription_cancel_scheduled_mode() -> None:
    requests, client = capture()
    client.subscriptions.cancel("sub_1", {"mode": "scheduled"})
    request = requests[0]
    assert request.method == "POST"
    assert request.url.path == "/v1/subscriptions/sub_1/cancel"
    assert json.loads(request.content) == {"mode": "scheduled"}
    client.close()


def test_subscription_lifecycle_paths() -> None:
    requests, client = capture()
    client.subscriptions.pause("sub_1")
    client.subscriptions.resume("sub_1")
    client.subscriptions.upgrade("sub_1", {"product_id": "prod_2"})
    paths = [r.url.path for r in requests]
    assert paths == [
        "/v1/subscriptions/sub_1/pause",
        "/v1/subscriptions/sub_1/resume",
        "/v1/subscriptions/sub_1/upgrade",
    ]
    client.close()


def test_transactions_search_filters() -> None:
    requests, client = capture()
    client.transactions.search(customer_id="cust_1", product_id="prod_2")
    query = requests[0].url.params
    assert query["customer_id"] == "cust_1"
    assert query["product_id"] == "prod_2"
    assert "order_id" not in query
    client.close()


def test_stats_summary_maps_snake_case_to_camel_case() -> None:
    requests, client = capture()
    client.stats.summary(
        currency="USD",
        start_date=1740614400000,
        end_date=1772150400000,
        interval="month",
    )
    query = requests[0].url.params
    assert query["currency"] == "USD"
    assert query["startDate"] == "1740614400000"
    assert query["endDate"] == "1772150400000"
    assert query["interval"] == "month"
    client.close()


def test_credits_credit_debit_paths_and_body() -> None:
    requests, client = capture()
    payload: CreditDebitParams = {"amount": "100", "reference": "signup_bonus", "idempotency_key": "idem_1"}
    client.credits.credit("cca_1", payload)
    client.credits.debit("cca_1", payload)
    client.credits.reverse("cca_1", {"transaction_id": "tran_9"})
    assert requests[0].url.path == "/v1/customer-credits/accounts/cca_1/credit"
    assert requests[1].url.path == "/v1/customer-credits/accounts/cca_1/debit"
    assert requests[2].url.path == "/v1/customer-credits/accounts/cca_1/reverse"
    assert json.loads(requests[2].content) == {"transaction_id": "tran_9"}
    client.close()


def test_credits_balance_and_entries_cursor_params() -> None:
    requests, client = capture()
    client.credits.balance("cca_1", at="2026-01-01T00:00:00Z")
    client.credits.entries("cca_1", limit=25, starting_after="entry_5")
    assert requests[0].url.params["at"] == "2026-01-01T00:00:00Z"
    assert requests[1].url.params["limit"] == "25"
    assert requests[1].url.params["starting_after"] == "entry_5"
    client.close()


def test_licenses_activate_validate_deactivate() -> None:
    requests, client = capture()
    key = "ABC123-XYZ456-XYZ456-XYZ456"
    client.licenses.activate({"key": key, "instance_name": "macbook-pro"})
    client.licenses.validate({"key": key, "instance_id": "inst_1"})
    client.licenses.deactivate({"key": key, "instance_id": "inst_1"})
    assert requests[0].url.path == "/v1/licenses/activate"
    assert json.loads(requests[1].content)["instance_id"] == "inst_1"
    assert requests[2].url.path == "/v1/licenses/deactivate"
    client.close()


def test_discounts_get_by_code_and_delete() -> None:
    requests, client = capture()
    client.discounts.get(discount_code="LAUNCH20")
    client.discounts.delete("disc_1")
    assert requests[0].url.params["discount_code"] == "LAUNCH20"
    assert requests[1].url.path == "/v1/discounts/disc_1/delete"
    client.close()


def test_refunds_create() -> None:
    requests, client = capture()
    client.refunds.create({"transaction_id": "tran_1"})
    assert requests[0].method == "POST"
    assert requests[0].url.path == "/v1/refunds"
    assert json.loads(requests[0].content) == {"transaction_id": "tran_1"}
    client.close()


def test_affiliates_commissions_status_filter() -> None:
    requests, client = capture()
    client.affiliates.commissions("aff_1", status="paid")
    assert requests[0].url.path == "/v1/affiliates/aff_1/commissions"
    assert requests[0].url.params["status"] == "paid"
    client.close()


def test_moderation_screen() -> None:
    requests, client = capture()
    client.moderation.screen({"prompt": "a cute robot"})
    assert requests[0].url.path == "/v1/moderation/prompt"
    assert json.loads(requests[0].content)["prompt"] == "a cute robot"
    client.close()


def test_error_propagates_through_resource_methods() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, json={"message": ["Product not found"]})

    client = make_client(handler)
    with pytest.raises(Exception) as excinfo:
        client.products.get("prod_missing")
    assert excinfo.value.status == 404  # type: ignore[attr-defined]
    client.close()


def test_products_update_path() -> None:
    requests, client = capture()
    client.products.update("prod_1", {"name": "Renamed"})
    assert requests[0].method == "PATCH"
    assert requests[0].url.path == "/v1/products/prod_1"
    assert json.loads(requests[0].content)["name"] == "Renamed"
    client.close()


def test_transactions_get_param() -> None:
    requests, client = capture()
    client.transactions.get("tran_9")
    assert requests[0].url.path == "/v1/transactions"
    assert requests[0].url.params["transaction_id"] == "tran_9"
    client.close()


def test_subscriptions_get_and_update() -> None:
    requests, client = capture()
    client.subscriptions.get("sub_1")
    assert requests[0].url.params["subscription_id"] == "sub_1"

    client.subscriptions.update("sub_1", {"items": [{"id": "sitem_1", "units": 3}]})
    assert requests[1].url.path == "/v1/subscriptions/sub_1"
    assert json.loads(requests[1].content)["items"][0]["units"] == 3
    client.close()


def test_discounts_create_body() -> None:
    requests, client = capture()
    client.discounts.create(
        {"name": "Sale", "type": "percentage", "percentage": 15, "duration": "once", "applies_to_products": []}
    )
    assert requests[0].url.path == "/v1/discounts"
    assert json.loads(requests[0].content)["percentage"] == 15
    client.close()


def test_customers_list_and_billing() -> None:
    requests, client = capture()
    client.customers.list(page_number=2, page_size=25)
    assert requests[0].url.path == "/v1/customers/list"
    assert requests[0].url.params["page_number"] == "2"
    assert requests[0].url.params["page_size"] == "25"

    client.customers.billing({"customer_id": "cust_1"})
    assert requests[1].url.path == "/v1/customers/billing"
    assert json.loads(requests[1].content)["customer_id"] == "cust_1"
    client.close()


def test_affiliates_get() -> None:
    requests, client = capture()
    client.affiliates.get("aff_1")
    assert requests[0].url.path == "/v1/affiliates/aff_1"
    client.close()


def test_credits_account_lifecycle_paths() -> None:
    requests, client = capture()
    client.credits.create_account({"customer_id": "cust_1", "name": "points", "unit_label": "points"})
    client.credits.get_account("cca_1")
    client.credits.freeze("cca_1")
    client.credits.unfreeze("cca_1")
    client.credits.close("cca_1")
    paths = [r.url.path for r in requests]
    assert paths == [
        "/v1/customer-credits/accounts",
        "/v1/customer-credits/accounts/cca_1",
        "/v1/customer-credits/accounts/cca_1/freeze",
        "/v1/customer-credits/accounts/cca_1/unfreeze",
        "/v1/customer-credits/accounts/cca_1/close",
    ]
    assert json.loads(requests[0].content)["customer_id"] == "cust_1"
    client.close()
