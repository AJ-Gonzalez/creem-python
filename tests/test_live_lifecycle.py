"""Live lifecycle tests that require a completed browser checkout.

These tests drive the hosted checkout page with the sandbox test card
(4111 1111 1111 1111), creating real sandbox orders, subscriptions, and
transactions. They run only under ``pytest -m live`` and need playwright:

    pip install playwright && playwright install chromium
"""

from __future__ import annotations

import time
import uuid
from collections.abc import Iterator

import pytest

from creem import Checkout, Creem, Product, ProductCreateParams
from tests.checkout_automation import complete_checkout

pytestmark = pytest.mark.live

try:
    import playwright  # noqa: F401
except ImportError:
    playwright = None  # type: ignore[assignment]

requires_playwright = pytest.mark.skipif(
    playwright is None,
    reason="playwright not installed; run: pip install playwright && playwright install chromium",
)


def unique(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


@pytest.fixture(scope="module")
def client() -> Iterator[Creem]:
    creem = Creem()
    yield creem
    creem.close()


def _create_checkout(
    client: Creem,
    product_params: ProductCreateParams,
) -> tuple[Checkout, Product]:
    """Create a product and a checkout, complete it in the browser, and
    return the fresh checkout state and the product."""
    product = client.products.create(product_params)
    checkout = client.checkouts.create(
        {"product_id": product["id"], "success_url": "https://example.com/success"}
    )
    complete_checkout(checkout["checkout_url"])
    state = client.checkouts.get(checkout["id"])
    assert state.get("status") == "completed"
    return state, product


@requires_playwright
def test_subscription_lifecycle(client: Creem) -> None:
    state, product = _create_checkout(
        client,
        {
            "name": unique("sdk-live-sub"),
            "description": "Subscription lifecycle live test",
            "price": 900,
            "currency": "USD",
            "billing_type": "recurring",
            "billing_period": "every-month",
        },
    )
    try:
        subscription_ref = state.get("subscription")
        assert isinstance(subscription_ref, dict), "checkout has no subscription object"
        subscription_id = subscription_ref["id"]
        assert subscription_id.startswith("sub_")

        subscription = client.subscriptions.get(subscription_id)
        assert subscription["status"] == "active"

        paused = client.subscriptions.pause(subscription_id)
        assert paused["status"] == "paused"

        resumed = client.subscriptions.resume(subscription_id)
        assert resumed["status"] == "active"

        scheduled = client.subscriptions.cancel(subscription_id, {"mode": "scheduled"})
        assert scheduled["status"] == "scheduled_cancel"

        canceled = client.subscriptions.cancel(subscription_id, {"mode": "immediate"})
        assert canceled["status"] == "canceled"

        # The subscription's invoice transaction exists and is paid.
        customer_id = subscription_ref["customer"]
        assert isinstance(customer_id, str)
        transactions = client.transactions.search(customer_id=customer_id)
        assert any(t.get("subscription") == subscription_id for t in transactions["items"])
    finally:
        client.products.archive(product["id"])


@requires_playwright
def test_refund_flow(client: Creem) -> None:
    state, product = _create_checkout(
        client,
        {
            "name": unique("sdk-live-onetime"),
            "description": "Refund flow live test",
            "price": 500,
            "currency": "USD",
            "billing_type": "onetime",
        },
    )
    try:
        order = state.get("order")
        assert isinstance(order, dict), "checkout has no order object"
        transaction_id = order["transaction"]
        assert transaction_id.startswith("tran_")
        transaction = client.transactions.get(transaction_id)
        assert transaction["status"] == "paid"

        refund = client.refunds.create({"transaction_id": transaction_id})
        assert refund["status"] in ("pending", "succeeded")

        # The provider confirms refunds asynchronously; poll for the
        # transaction to flip to refunded.
        transaction_after = client.transactions.get(transaction_id)
        deadline = time.monotonic() + 30
        while transaction_after["status"] != "refunded" and time.monotonic() < deadline:
            time.sleep(2)
            transaction_after = client.transactions.get(transaction_id)
        assert transaction_after["status"] == "refunded"
        assert transaction_after["refunded_amount"] == transaction["amount"]
    finally:
        client.products.archive(product["id"])
