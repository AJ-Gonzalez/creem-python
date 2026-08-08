"""Async pagination iterator tests: page-number and cursor styles."""

from __future__ import annotations

from typing import Any

import httpx
import pytest

from creem import AsyncCreem

pytestmark = pytest.mark.anyio


def make_paginated_client(
    pages: list[list[dict[str, Any]]],
    *,
    total_pages: int | None = None,
) -> tuple[list[httpx.Request], AsyncCreem]:
    """Serve page-number-paginated responses and record the requests."""
    requests: list[httpx.Request] = []
    resolved_total = total_pages if total_pages is not None else len(pages)

    async def handler(request: httpx.Request) -> httpx.Response:
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
    return requests, AsyncCreem(
        "creem_test_key", http_client=httpx.AsyncClient(transport=transport)
    )


def make_cursor_client(
    pages: list[tuple[bool, list[dict[str, Any]]]],
) -> tuple[list[httpx.Request], AsyncCreem]:
    """Serve cursor-paginated responses: (has_more, items) per page."""
    requests: list[httpx.Request] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        has_more, items = pages[len(requests) - 1]
        return httpx.Response(200, json={"object": "list", "data": items, "has_more": has_more})

    transport = httpx.MockTransport(handler)
    return requests, AsyncCreem(
        "creem_test_key", http_client=httpx.AsyncClient(transport=transport)
    )


async def test_iter_all_fetches_every_page() -> None:
    pages = [
        [{"id": f"tran_{i}"} for i in range(1, 3)],
        [{"id": f"tran_{i}"} for i in range(3, 5)],
        [{"id": f"tran_{i}"} for i in range(5, 7)],
    ]
    requests, client = make_paginated_client(pages)
    transactions = [t async for t in client.transactions.iter_all()]
    assert [t["id"] for t in transactions] == [f"tran_{i}" for i in range(1, 7)]
    assert [r.url.params["page_number"] for r in requests] == ["1", "2", "3"]
    assert all(r.url.params["page_size"] == "100" for r in requests)
    await client.aclose()


async def test_iter_all_stops_after_total_pages() -> None:
    pages = [[{"id": "tran_1"}], [{"id": "tran_2"}], [{"id": "tran_3"}]]
    requests, client = make_paginated_client(pages)
    collected = [t async for t in client.transactions.iter_all()]
    assert len(collected) == 3
    assert len(requests) == 3
    await client.aclose()


async def test_iter_all_empty_result_makes_one_request() -> None:
    requests, client = make_paginated_client([], total_pages=0)
    collected = [t async for t in client.transactions.iter_all()]
    assert not collected
    assert len(requests) == 1
    await client.aclose()


async def test_iter_all_forwards_filters() -> None:
    pages = [[{"id": "tran_1"}]]
    requests, client = make_paginated_client(pages)
    collected = [
        t
        async for t in client.transactions.iter_all(customer_id="cust_1", product_id="prod_2")
    ]
    assert collected[0]["id"] == "tran_1"
    assert requests[0].url.params["customer_id"] == "cust_1"
    assert requests[0].url.params["product_id"] == "prod_2"
    await client.aclose()


async def test_iter_all_early_exit_is_lazy() -> None:
    pages = [[{"id": f"tran_{i}"} for i in range(1, 4)] for _ in range(10)]
    requests, client = make_paginated_client(pages)
    first_two: list[Any] = []
    async for transaction in client.transactions.iter_all():
        first_two.append(transaction)
        if len(first_two) >= 2:
            break
    assert [t["id"] for t in first_two] == ["tran_1", "tran_2"]
    assert len(requests) == 1
    await client.aclose()


async def test_iter_commissions_forwards_status() -> None:
    pages = [[{"id": "comm_1"}]]
    requests, client = make_paginated_client(pages)
    collected = [c async for c in client.affiliates.iter_commissions("aff_1", status="paid")]
    assert collected[0]["id"] == "comm_1"
    assert requests[0].url.path == "/v1/affiliates/aff_1/commissions"
    assert requests[0].url.params["status"] == "paid"
    await client.aclose()


async def test_iter_instances_path() -> None:
    pages = [[{"id": "inst_1"}]]
    requests, client = make_paginated_client(pages)
    collected = [i async for i in client.licenses.iter_instances("lic_7")]
    assert collected[0]["id"] == "inst_1"
    assert requests[0].url.path == "/v1/licenses/lic_7/instances"
    await client.aclose()


async def test_iter_accounts_advances_cursor() -> None:
    requests, client = make_cursor_client(
        [
            (True, [{"id": "cca_1"}, {"id": "cca_2"}]),
            (True, [{"id": "cca_3"}]),
            (False, []),
        ]
    )
    accounts = [a async for a in client.credits.iter_accounts()]
    assert [a["id"] for a in accounts] == ["cca_1", "cca_2", "cca_3"]
    assert "starting_after" not in requests[0].url.params
    assert requests[1].url.params["starting_after"] == "cca_2"
    assert requests[2].url.params["starting_after"] == "cca_3"
    assert all(r.url.params["limit"] == "100" for r in requests)
    await client.aclose()


async def test_iter_accounts_stops_when_has_more_false() -> None:
    requests, client = make_cursor_client([(True, [{"id": "cca_1"}]), (False, [])])
    accounts = [a async for a in client.credits.iter_accounts()]
    assert [a["id"] for a in accounts] == ["cca_1"]
    assert len(requests) == 2
    await client.aclose()


async def test_iter_entries_cursor() -> None:
    requests, client = make_cursor_client([(False, [{"id": "entry_1"}])])
    entries = [e async for e in client.credits.iter_entries("cca_5")]
    assert entries[0]["id"] == "entry_1"
    assert requests[0].url.path == "/v1/customer-credits/accounts/cca_5/entries"
    await client.aclose()


async def test_iter_all_products_with_status_filter() -> None:
    pages = [[{"id": "prod_1"}]]
    requests, client = make_paginated_client(pages)
    collected = [p async for p in client.products.iter_all(status="active")]
    assert collected[0]["id"] == "prod_1"
    assert requests[0].url.params["status"] == "active"
    await client.aclose()
