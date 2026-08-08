"""Moderation: prompt screening for AI products."""

from __future__ import annotations

from typing import Any

from ..models import ModerationResult, ModerationScreenParams
from .base import APIResource, merge


class Moderation(APIResource):
    """Moderation endpoints.

    Experimental: this endpoint may change.
    """

    def screen(
        self,
        params: ModerationScreenParams,
        **kwargs: Any,
    ) -> ModerationResult:
        """Evaluate a text prompt against content policies before
        generation. The ``decision`` is ``allow``, ``deny``, or ``flag``."""
        return self._client.request(
            "POST", "/v1/moderation/prompt", json_body=merge(params, kwargs)
        )
