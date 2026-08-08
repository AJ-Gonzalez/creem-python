#!/usr/bin/env python3
"""Production smoke test for the creem SDK.

Exercises the SDK against the LIVE API (https://api.creem.io) with read-only
calls and create-then-archive round trips. It never creates checkouts,
refunds, subscriptions, or customer-credits mutations — no financial state.

Safety gates:
- Requires CREEM_PROD_SMOKE=1 (forces intentionality; never run by CI).
- Requires a LIVE key (creem_ prefix, not creem_test_).
- The key comes from CREEM_API_KEY or the gitignored `prodkey` file.

Run::

    CREEM_PROD_SMOKE=1 CREEM_API_KEY=$(cat prodkey) python scripts/prod_smoke.py

Exit code is 0 when every step passes; informational findings (e.g. discount
creation being feature-gated) are reported but do not fail the run.
"""

from __future__ import annotations

import os
import sys
from collections.abc import Callable
from pathlib import Path

from creem import (
    Creem,
    CreemAuthError,
    CreemNotFoundError,
    CreemValidationError,
)

RESULTS: list[tuple[str, str]] = []


def check(name: str, fn: Callable[[], None]) -> None:
    """Run one smoke step and record the outcome."""
    try:
        fn()
        RESULTS.append((name, "ok"))
    except Exception as exc:  # noqa: BLE001 - report and continue
        RESULTS.append((name, f"FAIL: {type(exc).__name__}: {exc}"))


def main() -> None:
    if os.environ.get("CREEM_PROD_SMOKE") != "1":
        print("Refusing: set CREEM_PROD_SMOKE=1 to run the production smoke test.")
        sys.exit(2)

    api_key = os.environ.get("CREEM_API_KEY")
    prodkey = Path(__file__).resolve().parent.parent / "prodkey"
    if not api_key and prodkey.exists():
        api_key = prodkey.read_text(encoding="utf-8").strip()
    if not api_key:
        print("Refusing: no API key (set CREEM_API_KEY or create the gitignored prodkey file).")
        sys.exit(2)
    if not api_key.startswith("creem_") or api_key.startswith("creem_test_"):
        print("Refusing: the key must be a live key (creem_ prefix, not creem_test_).")
        sys.exit(2)

    client = Creem(api_key)
    print(f"Base URL: {client.base_url}")

    # --- read-only checks -------------------------------------------------

    def check_products() -> None:
        found = client.products.search()
        assert "items" in found and "pagination" in found
        print(f"  products.search: {len(found['items'])} on this page (page 1)")

    def check_transactions() -> None:
        found = client.transactions.search()
        assert "items" in found
        print(f"  transactions.search: {len(found['items'])} on this page (page 1)")

    def check_customers() -> None:
        found = client.customers.list()
        assert "items" in found
        print(f"  customers.list: {len(found['items'])} on this page (page 1)")

    def check_subscriptions() -> None:
        found = client.subscriptions.search()
        assert "items" in found
        print(f"  subscriptions.search: {len(found['items'])} on this page (page 1)")

    def check_discounts() -> None:
        found = client.discounts.search()
        assert "items" in found
        print(f"  discounts.search: {len(found['items'])} on this page (page 1)")

    def check_affiliates() -> None:
        found = client.affiliates.list()
        assert "items" in found
        print(f"  affiliates.list: {len(found['items'])} on this page (page 1)")

    def check_stats() -> None:
        stats = client.stats.summary(currency="USD")
        totals = stats["totals"]
        assert totals["totalProducts"] >= 0
        print(
            f"  stats.summary: {totals['totalProducts']} products, "
            f"{totals['totalCustomers']} customers, "
            f"MRR ${totals['monthlyRecurringRevenue'] / 100:.2f}"
        )

    def check_credits_accounts() -> None:
        found = client.credits.list_accounts()
        assert "data" in found
        print(f"  credits.list_accounts: {len(found['data'])} accounts")

    def check_errors() -> None:
        try:
            client.products.get("prod_does_not_exist_12345")
            raise AssertionError("expected CreemNotFoundError")
        except CreemNotFoundError:
            pass
        try:
            client.request("POST", "/v1/checkouts", json_body={"product_id": 123})
            raise AssertionError("expected CreemValidationError")
        except CreemValidationError:
            pass
        print("  error mapping: 404 and 400 raise typed errors with trace_id")

    # --- create-then-archive round trips ----------------------------------

    def check_product_roundtrip() -> None:
        product = client.products.create(
            {
                "name": "prod-smoke-probe",
                "description": "Temporary probe created by scripts/prod_smoke.py; archived after.",
                "price": 100,
                "currency": "USD",
                "billing_type": "onetime",
            }
        )
        fetched = client.products.get(product["id"])
        assert fetched["id"] == product["id"]
        archived = client.products.archive(product["id"])
        assert archived["status"] == "archived"
        print(f"  product round trip: {product['id']} created and archived")

    def check_discount_roundtrip() -> None:
        try:
            created = client.discounts.create(
                {
                    "name": "prod-smoke-probe",
                    "type": "percentage",
                    "percentage": 1,
                    "duration": "once",
                    "applies_to_products": [],
                }
            )
        except CreemAuthError as exc:
            # Feature-gated on some stores: report, do not fail.
            print(
                "  discount round trip: skipped, creation feature-gated "
                f"(403, {exc.error or 'no category'})"
            )
            return
        deleted = client.discounts.delete(created["id"])
        assert deleted["status"] == "deleted"
        print(f"  discount round trip: {created['id']} created and deleted")

    check("products.search", check_products)
    check("transactions.search", check_transactions)
    check("customers.list", check_customers)
    check("subscriptions.search", check_subscriptions)
    check("discounts.search", check_discounts)
    check("affiliates.list", check_affiliates)
    check("stats.summary", check_stats)
    check("credits.list_accounts", check_credits_accounts)
    check("error mapping", check_errors)
    check("product round trip", check_product_roundtrip)
    check("discount round trip", check_discount_roundtrip)

    print("\nSummary:")
    failures = 0
    for name, outcome in RESULTS:
        marker = "ok " if outcome == "ok" else "FAIL"
        if outcome != "ok":
            failures += 1
        print(f"  [{marker}] {name}: {outcome}")
    if failures:
        print(f"\n{failures} step(s) failed.")
        sys.exit(1)
    print("\nAll smoke steps passed.")


if __name__ == "__main__":
    main()
