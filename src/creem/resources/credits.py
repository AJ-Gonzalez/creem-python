"""Customer credits: wallets, balances, and ledger entries.

Note: the customer-credits API is tagged experimental in the official spec
and may change.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

from ..models import (
    CreditDebitParams,
    CreditsAccount,
    CreditsAccountCreateParams,
    CreditsAccountList,
    CreditsBalance,
    CreditsEntry,
    CreditsEntryList,
    CreditsReverseParams,
    CreditsTransaction,
)
from .base import APIResource, drop_none, iter_cursor_pages, merge


class Credits(APIResource):
    """Customer credits account endpoints."""

    def create_account(
        self,
        params: CreditsAccountCreateParams,
        **kwargs: Any,
    ) -> CreditsAccount:
        """Create a credits account for a customer, optionally seeded with an
        initial balance."""
        return self._client.request(
            "POST", "/v1/customer-credits/accounts", json_body=merge(params, kwargs)
        )

    def list_accounts(
        self,
        *,
        limit: int | None = None,
        customer_id: str | None = None,
        starting_after: str | None = None,
        ending_before: str | None = None,
    ) -> CreditsAccountList:
        """List credits accounts with cursor pagination."""
        return self._client.request(
            "GET",
            "/v1/customer-credits/accounts",
            params=drop_none(
                {
                    "limit": limit,
                    "customer_id": customer_id,
                    "starting_after": starting_after,
                    "ending_before": ending_before,
                }
            ),
        )

    def get_account(self, account_id: str) -> CreditsAccount:
        """Retrieve a credits account by ID."""
        return self._client.request(
            "GET", f"/v1/customer-credits/accounts/{account_id}"
        )

    def balance(self, account_id: str, *, at: str | None = None) -> CreditsBalance:
        """Get the current balance. Pass ``at`` for a historical balance."""
        return self._client.request(
            "GET",
            f"/v1/customer-credits/accounts/{account_id}/balance",
            params=drop_none({"at": at}),
        )

    def credit(
        self,
        account_id: str,
        params: CreditDebitParams,
        **kwargs: Any,
    ) -> CreditsTransaction:
        """Add credits to an account."""
        return self._client.request(
            "POST",
            f"/v1/customer-credits/accounts/{account_id}/credit",
            json_body=merge(params, kwargs),
        )

    def debit(
        self,
        account_id: str,
        params: CreditDebitParams,
        **kwargs: Any,
    ) -> CreditsTransaction:
        """Deduct credits from an account."""
        return self._client.request(
            "POST",
            f"/v1/customer-credits/accounts/{account_id}/debit",
            json_body=merge(params, kwargs),
        )

    def reverse(
        self,
        account_id: str,
        params: CreditsReverseParams,
        **kwargs: Any,
    ) -> CreditsTransaction:
        """Reverse a previous credit or debit, preserving full history."""
        return self._client.request(
            "POST",
            f"/v1/customer-credits/accounts/{account_id}/reverse",
            json_body=merge(params, kwargs),
        )

    def entries(
        self,
        account_id: str,
        *,
        limit: int | None = None,
        starting_after: str | None = None,
        ending_before: str | None = None,
    ) -> CreditsEntryList:
        """List the credit/debit history of an account."""
        return self._client.request(
            "GET",
            f"/v1/customer-credits/accounts/{account_id}/entries",
            params=drop_none(
                {"limit": limit, "starting_after": starting_after, "ending_before": ending_before}
            ),
        )

    def close(self, account_id: str) -> CreditsAccount:
        """Permanently close an account. Cannot be undone."""
        return self._client.request(
            "POST", f"/v1/customer-credits/accounts/{account_id}/close"
        )

    def freeze(self, account_id: str) -> CreditsAccount:
        """Freeze an account to prevent new transactions."""
        return self._client.request(
            "POST", f"/v1/customer-credits/accounts/{account_id}/freeze"
        )

    def unfreeze(self, account_id: str) -> CreditsAccount:
        """Unfreeze a frozen account."""
        return self._client.request(
            "POST", f"/v1/customer-credits/accounts/{account_id}/unfreeze"
        )

    def iter_accounts(
        self,
        *,
        limit: int = 100,
        customer_id: str | None = None,
    ) -> Iterator[CreditsAccount]:
        """Yield every credits account across cursor pages."""
        for page in iter_cursor_pages(
            self.list_accounts, limit=limit, filters={"customer_id": customer_id}, id_key="id"
        ):
            yield from page["data"]

    def iter_entries(self, account_id: str, *, limit: int = 100) -> Iterator[CreditsEntry]:
        """Yield every credit/debit entry for an account across cursor pages."""
        for page in iter_cursor_pages(
            self.entries, limit=limit, filters={"account_id": account_id}, id_key="id"
        ):
            yield from page["data"]
