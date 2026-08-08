"""Async checkout flow: create a product, create a checkout, print the URL.

The async counterpart of checkout_flow.py. Run with the CREEM_API_KEY
environment variable set to a test key:

    CREEM_API_KEY=creem_test_... python examples/async_checkout_flow.py
"""

from __future__ import annotations

import asyncio

from creem import AsyncCreem


async def main() -> None:
    async with AsyncCreem() as creem:  # reads CREEM_API_KEY; test keys target the sandbox
        product = await creem.products.create(
            {
                "name": "Pro Plan (async)",
                "description": "Monthly subscription with all features",
                "price": 1999,  # cents: $19.99
                "currency": "USD",
                "billing_type": "recurring",
                "billing_period": "every-month",
            }
        )
        print(f"Created product {product['id']}")

        checkout = await creem.checkouts.create(
            {
                "product_id": product["id"],
                "success_url": "https://yourapp.com/success",
                "metadata": {"plan": "pro"},
            }
        )
        print(f"Send the customer to: {checkout['checkout_url']}")


if __name__ == "__main__":
    asyncio.run(main())
