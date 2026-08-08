"""Licenses: activation, validation, and instance management."""

from __future__ import annotations

from typing import Any

from ..models import (
    License,
    LicenseActivateParams,
    LicenseDeactivateParams,
    LicenseInstanceList,
    LicenseValidateParams,
)
from .base import APIResource, drop_none, merge


class Licenses(APIResource):
    """License key endpoints.

    License keys are ``XXXXXX-XXXXXX-XXXXXX-XXXXXX`` strings handed to the
    customer at purchase; instances are per-device activations.
    """

    def activate(
        self,
        params: LicenseActivateParams,
        **kwargs: Any,
    ) -> License:
        """Register a new device instance against a license key."""
        return self._client.request(
            "POST", "/v1/licenses/activate", json_body=merge(params, kwargs)
        )

    def validate(
        self,
        params: LicenseValidateParams,
        **kwargs: Any,
    ) -> License:
        """Verify a license key for a specific instance. Grant access only
        when the returned ``status`` is ``"active"``."""
        return self._client.request(
            "POST", "/v1/licenses/validate", json_body=merge(params, kwargs)
        )

    def deactivate(
        self,
        params: LicenseDeactivateParams,
        **kwargs: Any,
    ) -> License:
        """Remove a device activation, freeing up an activation slot."""
        return self._client.request(
            "POST", "/v1/licenses/deactivate", json_body=merge(params, kwargs)
        )

    def instances(
        self,
        license_id: str,
        *,
        page_number: int | None = None,
        page_size: int | None = None,
    ) -> LicenseInstanceList:
        """List the activations (instances) of a license key."""
        return self._client.request(
            "GET",
            f"/v1/licenses/{license_id}/instances",
            params=drop_none({"page_number": page_number, "page_size": page_size}),
        )
