"""Browse the store: iterate every product and the latest transactions.

Shows the pagination iterators: pages are fetched lazily, one page at a
time, until the API reports the last one.

Run with the CREEM_API_KEY environment variable set to a test key.
"""

from __future__ import annotations

from itertools import islice

from creem import Creem


def main() -> None:
    creem = Creem()

    print("All products:")
    for product in creem.products.iter_all():
        print(f"  {product['name']} — {product['price']} {product['currency']}")

    print("Ten most recent transactions:")
    for transaction in islice(creem.transactions.iter_all(), 10):
        print(f"  {transaction['id']} — {transaction.get('amount')} {transaction.get('currency')}")


if __name__ == "__main__":
    main()
