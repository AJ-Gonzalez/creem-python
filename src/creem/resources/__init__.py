"""Resource groups exposed by the Creem and AsyncCreem clients."""

from __future__ import annotations

from .affiliates import Affiliates, AsyncAffiliates
from .base import APIResource, AsyncAPIResource
from .checkouts import AsyncCheckouts, Checkouts
from .credits import AsyncCredits, Credits
from .customers import AsyncCustomers, Customers
from .discounts import AsyncDiscounts, Discounts
from .licenses import AsyncLicenses, Licenses
from .moderation import AsyncModeration, Moderation
from .products import AsyncProducts, Products
from .refunds import AsyncRefunds, Refunds
from .stats import AsyncStats, Stats
from .subscriptions import AsyncSubscriptions, Subscriptions
from .transactions import AsyncTransactions, Transactions

__all__ = [
    "APIResource",
    "AsyncAPIResource",
    "Affiliates",
    "AsyncAffiliates",
    "Checkouts",
    "AsyncCheckouts",
    "Credits",
    "AsyncCredits",
    "Customers",
    "AsyncCustomers",
    "Discounts",
    "AsyncDiscounts",
    "Licenses",
    "AsyncLicenses",
    "Moderation",
    "AsyncModeration",
    "Products",
    "AsyncProducts",
    "Refunds",
    "AsyncRefunds",
    "Stats",
    "AsyncStats",
    "Subscriptions",
    "AsyncSubscriptions",
    "Transactions",
    "AsyncTransactions",
]
