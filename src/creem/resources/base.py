"""Shared plumbing for API resource classes."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Mapping

if TYPE_CHECKING:
    from ..client import Creem


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


class APIResource:
    """Base class for resource groups; holds a reference to the client."""

    def __init__(self, client: Creem) -> None:
        self._client = client
