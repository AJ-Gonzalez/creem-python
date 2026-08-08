"""Sell a product: create the product, create a checkout, print the payment URL.

Run with the CREEM_API_KEY environment variable set to a test key:

    CREEM_API_KEY=creem_test_... python examples/checkout_flow.py
"""

from __future__ import annotations

from creem import Creem


def main() -> None:
    creem = Creem()  # reads CREEM_API_KEY; test keys target the sandbox

    product = creem.products.create(
        {
            "name": "Pro Plan",
            "description": "Monthly subscription with all features",
            "price": 1999,  # cents: $19.99
            "currency": "USD",
            "billing_type": "recurring",
            "billing_period": "every-month",
        }
    )
    print(f"Created product {product['id']}")

    checkout = creem.checkouts.create(
        {
            "product_id": product["id"],
            "success_url": "https://yourapp.com/success",
            "metadata": {"plan": "pro"},
        }
    )
    print(f"Send the customer to: {checkout['checkout_url']}")


if __name__ == "__main__":
    main()
