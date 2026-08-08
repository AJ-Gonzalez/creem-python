"""Licenses: activation, validation, and instance management."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any, overload

from ..models import (
    License,
    LicenseActivateParams,
    LicenseDeactivateParams,
    LicenseInstance,
    LicenseInstanceList,
    LicenseValidateParams,
)
from .base import APIResource, drop_none, iter_pages, merge


class Licenses(APIResource):
    """License key endpoints.

    License keys are ``XXXXXX-XXXXXX-XXXXXX-XXXXXX`` strings handed to the
    customer at purchase; instances are per-device activations.
    """

    @overload
    def activate(self, params: LicenseActivateParams, **kwargs: Any) -> License: ...

    @overload
    def activate(self, **kwargs: Any) -> License: ...

    def activate(
        self,
        params: LicenseActivateParams | None = None,
        **kwargs: Any,
    ) -> License:
        """Register a new device instance against a license key."""
        return self._client.request(
            "POST", "/v1/licenses/activate", json_body=merge(params, kwargs)
        )

    @overload
    def validate(self, params: LicenseValidateParams, **kwargs: Any) -> License: ...

    @overload
    def validate(self, **kwargs: Any) -> License: ...

    def validate(
        self,
        params: LicenseValidateParams | None = None,
        **kwargs: Any,
    ) -> License:
        """Verify a license key for a specific instance. Grant access only
        when the returned ``status`` is ``"active"``."""
        return self._client.request(
            "POST", "/v1/licenses/validate", json_body=merge(params, kwargs)
        )

    @overload
    def deactivate(self, params: LicenseDeactivateParams, **kwargs: Any) -> License: ...

    @overload
    def deactivate(self, **kwargs: Any) -> License: ...

    def deactivate(
        self,
        params: LicenseDeactivateParams | None = None,
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

    def iter_instances(self, license_id: str, *, page_size: int = 100) -> Iterator[LicenseInstance]:
        """Yield every activation (instance) of a license key."""
        for page in iter_pages(
            self.instances, page_size=page_size, filters={"license_id": license_id}
        ):
            yield from page["items"]
