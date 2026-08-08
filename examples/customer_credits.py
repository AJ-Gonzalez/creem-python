"""Customer credits wallet: create an account, credit, check the balance.

Run with the CREEM_API_KEY environment variable set to a test key.
"""

from __future__ import annotations

from creem import Creem


def main() -> None:
    creem = Creem()

    customer = creem.customers.create(
        {"email": "wallet@example.com", "name": "Wallet Example"}
    )

    account = creem.credits.create_account(
        {
            "customer_id": customer["id"],
            "name": "points",
            "unit_label": "points",
            "initial_balance": "100",
        }
    )
    print(f"Created account {account['id']}")

    transaction = creem.credits.credit(
        account["id"],
        {
            "amount": "50",
            "reference": "signup-bonus",
            "idempotency_key": "signup-bonus-2026-08-07",
        },
    )
    print(f"Credited 50 points (transaction {transaction['id']})")

    balance = creem.credits.balance(account["id"])
    print(f"Balance: {balance['balance']} points")


if __name__ == "__main__":
    main()
