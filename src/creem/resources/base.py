"""Shared plumbing for API resource classes."""

from __future__ import annotations

from collections.abc import AsyncIterator, Iterator
from typing import TYPE_CHECKING, Any, Callable, Mapping

if TYPE_CHECKING:
    from ..async_client import AsyncCreem
    from ..client import Creem


async def iter_pages_async(
    fetch: Callable[..., Any],
    *,
    page_size: int,
    filters: Mapping[str, Any],
) -> AsyncIterator[Any]:
    """Async variant of :func:`iter_pages`; ``fetch`` is awaited per page."""
    clean = {
        key: value
        for key, value in filters.items()
        if value is not None and key not in ("page_number", "page_size")
    }
    page_number = 1
    while True:
        page = await fetch(page_number=page_number, page_size=page_size, **clean)
        yield page
        pagination = page.get("pagination") or {}
        total_pages = pagination.get("total_pages")
        if total_pages is None or page_number >= total_pages:
            return
        page_number += 1


async def iter_cursor_pages_async(
    fetch: Callable[..., Any],
    *,
    limit: int,
    filters: Mapping[str, Any],
    id_key: str,
) -> AsyncIterator[Any]:
    """Async variant of :func:`iter_cursor_pages`; ``fetch`` is awaited per page."""
    clean = {
        key: value
        for key, value in filters.items()
        if value is not None and key not in ("limit", "starting_after", "ending_before")
    }
    starting_after: str | None = None
    while True:
        page = await fetch(limit=limit, starting_after=starting_after, **clean)
        yield page
        items = page.get("data") or []
        if not page.get("has_more") or not items:
            return
        starting_after = str(items[-1][id_key])


def merge(
    params: Mapping[str, Any] | None, overrides: Mapping[str, Any]
) -> dict[str, Any]:
    """Combine a typed params TypedDict with keyword overrides.

    Keyword arguments win over entries in ``params``.
    """
    body = dict(params) if params else {}
    body.update(overrides)
    return body


def drop_none(params: Mapping[str, Any] | None) -> dict[str, Any] | None:
    """Drop entries whose value is ``None`` (used for optional query params)."""
    if params is None:
        return None
    return {key: value for key, value in params.items() if value is not None}


def iter_pages(
    fetch: Callable[..., Any],
    *,
    page_size: int,
    filters: Mapping[str, Any],
) -> Iterator[Any]:
    """Yield pages from a page-number-paginated endpoint until the last page.

    ``fetch`` is the resource's single-page method (e.g. ``search``); its
    ``page_number`` and ``page_size`` parameters are set per page, and
    ``filters`` carries the remaining query filters.
    """
    clean = {
        key: value
        for key, value in filters.items()
        if value is not None and key not in ("page_number", "page_size")
    }
    page_number = 1
    while True:
        page = fetch(page_number=page_number, page_size=page_size, **clean)
        yield page
        pagination = page.get("pagination") or {}
        total_pages = pagination.get("total_pages")
        if total_pages is None or page_number >= total_pages:
            return
        page_number += 1


def iter_cursor_pages(
    fetch: Callable[..., Any],
    *,
    limit: int,
    filters: Mapping[str, Any],
    id_key: str,
) -> Iterator[Any]:
    """Yield pages from a cursor-paginated endpoint until ``has_more`` stops.

    ``starting_after`` advances to the last item's ``id_key`` value on each
    page — the API's documented cursor semantics.
    """
    clean = {
        key: value
        for key, value in filters.items()
        if value is not None and key not in ("limit", "starting_after", "ending_before")
    }
    starting_after: str | None = None
    while True:
        page = fetch(limit=limit, starting_after=starting_after, **clean)
        yield page
        items = page.get("data") or []
        if not page.get("has_more") or not items:
            return
        starting_after = str(items[-1][id_key])


class APIResource:
    """Base class for resource groups; holds a reference to the client."""

    def __init__(self, client: Creem) -> None:
        self._client = client


class AsyncAPIResource:
    """Base class for async resource groups; holds the async client."""

    def __init__(self, client: AsyncCreem) -> None:
        self._client = client
