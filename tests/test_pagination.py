"""Pagination iterator tests: page-number and cursor styles."""

from __future__ import annotations

from typing import Any, Callable

import httpx
import pytest

from creem import Creem


def make_paginated_client(
    pages: list[list[dict[str, Any]]],
    *,
    total_pages: int | None = None,
) -> tuple[list[httpx.Request], Creem]:
    """Serve page-number-paginated responses and record the requests."""
    requests: list[httpx.Request] = []
    resolved_total = total_pages if total_pages is not None else len(pages)

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        page_number = int(request.url.params.get("page_number", "1"))
        items = pages[page_number - 1] if page_number <= len(pages) else []
        return httpx.Response(
            200,
            json={
                "items": items,
                "pagination": {
                    "total_records": sum(len(p) for p in pages),
                    "total_pages": resolved_total,
                    "current_page": page_number,
                    "next_page": page_number + 1 if page_number < resolved_total else None,
                    "prev_page": page_number - 1 if page_number > 1 else None,
                },
            },
        )

    transport = httpx.MockTransport(handler)
    return requests, Creem("creem_test_key", http_client=httpx.Client(transport=transport))


def make_cursor_client(
    pages: list[tuple[bool, list[dict[str, Any]]]],
) -> tuple[list[httpx.Request], Creem]:
    """Serve cursor-paginated responses: (has_more, items) per page."""
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        has_more, items = pages[len(requests) - 1]
        return httpx.Response(200, json={"object": "list", "data": items, "has_more": has_more})

    transport = httpx.MockTransport(handler)
    return requests, Creem("creem_test_key", http_client=httpx.Client(transport=transport))


def test_iter_all_fetches_every_page() -> None:
    pages = [[{"id": f"tran_{i}"} for i in range(1, 3)],
             [{"id": f"tran_{i}"} for i in range(3, 5)],
             [{"id": f"tran_{i}"} for i in range(5, 7)]]
    requests, client = make_paginated_client(pages)
    transactions = list(client.transactions.iter_all())
    assert [t["id"] for t in transactions] == [f"tran_{i}" for i in range(1, 7)]
    assert [r.url.params["page_number"] for r in requests] == ["1", "2", "3"]
    assert all(r.url.params["page_size"] == "100" for r in requests)
    client.close()


def test_iter_all_stops_after_total_pages() -> None:
    pages = [[{"id": "tran_1"}], [{"id": "tran_2"}], [{"id": "tran_3"}]]
    requests, client = make_paginated_client(pages)
    assert len(list(client.transactions.iter_all())) == 3
    assert len(requests) == 3  # no fourth request past total_pages
    client.close()


def test_iter_all_empty_result_makes_one_request() -> None:
    requests, client = make_paginated_client([], total_pages=0)
    assert list(client.transactions.iter_all()) == []
    assert len(requests) == 1
    client.close()


def test_iter_all_forwards_filters() -> None:
    pages = [[{"id": "tran_1"}]]
    requests, client = make_paginated_client(pages)
    list(client.transactions.iter_all(customer_id="cust_1", product_id="prod_2", page_size=50))
    assert requests[0].url.params["customer_id"] == "cust_1"
    assert requests[0].url.params["product_id"] == "prod_2"
    assert requests[0].url.params["page_size"] == "50"
    client.close()


def test_iter_all_products_with_status_filter() -> None:
    pages = [[{"id": "prod_1"}]]
    requests, client = make_paginated_client(pages)
    list(client.products.iter_all(status="active"))
    assert requests[0].url.params["status"] == "active"
    client.close()


def test_iter_subscriptions_and_discounts() -> None:
    pages = [[{"id": "sub_1"}]]
    requests, client = make_paginated_client(pages)
    list(client.subscriptions.iter_all(status="active"))
    assert requests[0].url.path == "/v1/subscriptions/search"
    assert requests[0].url.params["status"] == "active"

    requests2, client2 = make_paginated_client([[{"id": "disc_1"}]])
    list(client2.discounts.iter_all(type="percentage"))
    assert requests2[0].url.path == "/v1/discounts/search"
    assert requests2[0].url.params["type"] == "percentage"
    client.close()
    client2.close()


def test_customer_scoped_iterators_use_path_and_page() -> None:
    pages = [[{"id": "ord_1"}]]
    requests, client = make_paginated_client(pages)
    list(client.customers.iter_orders("cust_9"))
    assert requests[0].url.path == "/v1/customers/cust_9/orders"

    requests2, client2 = make_paginated_client([[{"id": "sub_1"}]])
    list(client2.customers.iter_subscriptions("cust_9"))
    assert requests2[0].url.path == "/v1/customers/cust_9/subscriptions"

    requests3, client3 = make_paginated_client([[{"id": "lic_1"}]])
    list(client3.customers.iter_licenses("cust_9"))
    assert requests3[0].url.path == "/v1/customers/cust_9/licenses"
    client.close()
    client2.close()
    client3.close()


def test_iter_commissions_forwards_status() -> None:
    pages = [[{"id": "comm_1"}]]
    requests, client = make_paginated_client(pages)
    list(client.affiliates.iter_commissions("aff_1", status="paid"))
    assert requests[0].url.path == "/v1/affiliates/aff_1/commissions"
    assert requests[0].url.params["status"] == "paid"
    client.close()


def test_iter_instances_path() -> None:
    pages = [[{"id": "inst_1"}]]
    requests, client = make_paginated_client(pages)
    list(client.licenses.iter_instances("lic_7"))
    assert requests[0].url.path == "/v1/licenses/lic_7/instances"
    client.close()


def test_iter_accounts_advances_cursor() -> None:
    requests, client = make_cursor_client(
        [(True, [{"id": "cca_1"}, {"id": "cca_2"}]),
         (True, [{"id": "cca_3"}]),
         (False, [])]
    )
    accounts = list(client.credits.iter_accounts())
    assert [a["id"] for a in accounts] == ["cca_1", "cca_2", "cca_3"]
    # first request: no cursor; second: after cca_2; third: after cca_3
    assert "starting_after" not in requests[0].url.params
    assert requests[1].url.params["starting_after"] == "cca_2"
    assert requests[2].url.params["starting_after"] == "cca_3"
    assert all(r.url.params["limit"] == "100" for r in requests)
    client.close()


def test_iter_accounts_stops_when_has_more_false() -> None:
    requests, client = make_cursor_client([(True, [{"id": "cca_1"}]), (False, [])])
    assert [a["id"] for a in client.credits.iter_accounts()] == ["cca_1"]
    assert len(requests) == 2
    client.close()


def test_iter_entries_cursor() -> None:
    requests, client = make_cursor_client([(False, [{"id": "entry_1"}])])
    entries = list(client.credits.iter_entries("cca_5"))
    assert entries[0]["id"] == "entry_1"
    assert requests[0].url.path == "/v1/customer-credits/accounts/cca_5/entries"
    client.close()


def test_iter_accounts_forwards_customer_filter() -> None:
    requests, client = make_cursor_client([(False, [])])
    list(client.credits.iter_accounts(customer_id="cust_2"))
    assert requests[0].url.params["customer_id"] == "cust_2"
    client.close()


def test_iter_all_early_exit_does_not_fetch_all_pages() -> None:
    pages = [[{"id": f"tran_{i}"} for i in range(1, 4)] for _ in range(10)]
    requests, client = make_paginated_client(pages)
    first_two = list(_first_n(client.transactions.iter_all(), 2))
    assert [t["id"] for t in first_two] == ["tran_1", "tran_2"]
    assert len(requests) == 1  # lazy: stops before fetching page 2
    client.close()


def _first_n(iterator: Any, n: int) -> list[Any]:
    result = []
    for item in iterator:
        result.append(item)
        if len(result) >= n:
            break
    return result


def test_customers_iter_all() -> None:
    pages = [[{"id": "cust_1"}], [{"id": "cust_2"}]]
    requests, client = make_paginated_client(pages)
    customers = list(client.customers.iter_all())
    assert [c["id"] for c in customers] == ["cust_1", "cust_2"]
    assert requests[0].url.path == "/v1/customers/list"
    client.close()


def test_affiliates_iter_all() -> None:
    pages = [[{"id": "aff_1"}]]
    requests, client = make_paginated_client(pages)
    list(client.affiliates.iter_all())
    assert requests[0].url.path == "/v1/affiliates"
    client.close()
