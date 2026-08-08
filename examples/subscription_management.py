"""Manage subscriptions: search, cancel at period end, pause, resume.

Run with the CREEM_API_KEY environment variable set to a test key.
"""

from __future__ import annotations

from creem import Creem
from creem.models import Subscription


def describe(subscription: Subscription) -> str:
    return f"{subscription['id']} ({subscription.get('status')})"


def main() -> None:
    creem = Creem()

    print("Active subscriptions:")
    for subscription in creem.subscriptions.iter_all(status="active"):
        print(f"  {describe(subscription)}")

    subscription_id = input("Subscription ID to manage: ").strip()
    if not subscription_id:
        return

    # Prefer scheduled cancellation: the customer keeps access until the
    # billing period ends.
    creem.subscriptions.cancel(subscription_id, mode="scheduled")
    print(f"Scheduled cancellation for {subscription_id}")

    creem.subscriptions.pause(subscription_id)
    print(f"Paused {subscription_id}")

    creem.subscriptions.resume(subscription_id)
    print(f"Resumed {subscription_id}")


if __name__ == "__main__":
    main()
