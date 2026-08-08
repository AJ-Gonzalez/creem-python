"""Live smoke tests against the real Creem sandbox (test-api.creem.io).

Run with ``pytest -m live``. Skipped by default; requires the test API key,
loaded from the gitignored ``.env`` file by conftest.py (or the
``CREEM_API_KEY`` environment variable). These tests create and clean up
their own resources in the sandbox.
"""

from __future__ import annotations

import os
import uuid
from collections.abc import Iterator

import pytest

from creem import Creem, CreemNotFoundError, CreemValidationError
from creem.models import CreditsAccountCreateParams, CreditDebitParams, ProductCreateParams

pytestmark = pytest.mark.live

API_KEY = os.environ.get("CREEM_API_KEY")
requires_key = pytest.mark.skipif(
    not API_KEY, reason="CREEM_API_KEY not set; add it to .env (gitignored)"
)


def unique(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


@pytest.fixture(scope="module")
def client() -> Iterator[Creem]:
    creem = Creem()
    yield creem
    creem.close()


@pytest.fixture
def product_params() -> ProductCreateParams:
    return {
        "name": unique("sdk-test-product"),
        "description": "Created by the creem SDK live test suite",
        "price": 1999,
        "currency": "USD",
        "billing_type": "onetime",
    }


@requires_key
def test_products_crud_roundtrip(client: Creem, product_params: ProductCreateParams) -> None:
    created = client.products.create(product_params)
    assert created["id"].startswith("prod_")
    assert created["price"] == 1999

    fetched = client.products.get(created["id"])
    assert fetched["id"] == created["id"]

    found = client.products.search()
    assert any(item["id"] == created["id"] for item in found["items"])

    archived = client.products.archive(created["id"])
    assert archived["status"] == "archived"


@requires_key
def test_checkout_flow(client: Creem, product_params: ProductCreateParams) -> None:
    product = client.products.create(product_params)
    try:
        checkout = client.checkouts.create(
            {
                "product_id": product["id"],
                "success_url": "https://example.com/success",
                "metadata": {"userId": "live-test-user"},
            }
        )
        assert checkout["id"].startswith("ch_")
        assert checkout["checkout_url"].startswith("https://")
        assert checkout["status"] == "pending"

        fetched = client.checkouts.get(checkout["id"])
        assert fetched["id"] == checkout["id"]
    finally:
        client.products.archive(product["id"])


@requires_key
def test_customer_roundtrip_and_billing_link(client: Creem) -> None:
    email = f"{unique('sdk-test')}@example.com"
    customer = client.customers.create({"email": email, "name": "SDK Test User"})
    assert customer["id"].startswith("cust_")

    by_email = client.customers.get(email=email)
    assert by_email["id"] == customer["id"]

    links = client.customers.billing({"customer_id": customer["id"]})
    assert links["customer_portal_link"].startswith("https://")


@requires_key
def test_discount_search_shape(client: Creem) -> None:
    # Discount creation is feature-gated on this sandbox store (403
    # "Bad Request"), so only the read path is exercised live.
    found = client.discounts.search(status="active")
    assert "items" in found
    assert "pagination" in found


@requires_key
def test_credits_roundtrip(client: Creem) -> None:
    customer = client.customers.create(
        {"email": f"{unique('sdk-credits')}@example.com", "name": "Credits Test"}
    )
    params: CreditsAccountCreateParams = {
        "customer_id": customer["id"],
        "name": unique("points"),
        "unit_label": "points",
        "initial_balance": "100",
    }
    account = client.credits.create_account(params)
    assert account["id"].startswith("cca_")

    balance = client.credits.balance(account["id"])
    assert int(balance["balance"]) == 100

    credit: CreditDebitParams = {
        "amount": "50",
        "reference": unique("ref"),
        "idempotency_key": unique("idem"),
    }
    transaction = client.credits.credit(account["id"], credit)
    assert transaction["id"]

    balance_after = client.credits.balance(account["id"])
    assert int(balance_after["balance"]) == 150

    entries = client.credits.entries(account["id"])
    assert len(entries["data"]) >= 1

    client.credits.close(account["id"])


@requires_key
def test_transactions_and_stats_shapes(client: Creem) -> None:
    transactions = client.transactions.search()
    assert "items" in transactions
    assert "pagination" in transactions

    stats = client.stats.summary(currency="USD")
    assert stats["totals"]["totalProducts"] >= 0


@requires_key
def test_iter_all_transactions_terminates(client: Creem) -> None:
    # Validates cursor-less page iteration against the real pagination shape
    # (total_pages must terminate the loop even with zero records).
    transactions = list(client.transactions.iter_all())
    assert all("id" in t for t in transactions)


@requires_key
def test_moderation_screen(client: Creem) -> None:
    result = client.moderation.screen({"prompt": "a cute robot painting flowers"})
    assert result["decision"] in ("allow", "deny", "flag")
    assert result["prompt"] == "a cute robot painting flowers"


@requires_key
def test_validation_error_has_trace_id(client: Creem) -> None:
    # A body with the wrong type for product_id triggers a 400 validation
    # error. (An unknown but well-formed id is a 404: the API looks the
    # product up and reports it missing.)
    with pytest.raises(CreemValidationError) as excinfo:
        client.request("POST", "/v1/checkouts", json_body={"product_id": 123})
    assert excinfo.value.status == 400
    assert excinfo.value.trace_id


@requires_key
def test_not_found_error(client: Creem) -> None:
    with pytest.raises(CreemNotFoundError) as excinfo:
        client.products.get("prod_does_not_exist_12345")
    assert excinfo.value.status == 404
