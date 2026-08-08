"""Resource groups exposed by the Creem client."""

from __future__ import annotations

from .affiliates import Affiliates
from .base import APIResource
from .checkouts import Checkouts
from .credits import Credits
from .customers import Customers
from .discounts import Discounts
from .licenses import Licenses
from .moderation import Moderation
from .products import Products
from .refunds import Refunds
from .stats import Stats
from .subscriptions import Subscriptions
from .transactions import Transactions

__all__ = [
    "APIResource",
    "Affiliates",
    "Checkouts",
    "Credits",
    "Customers",
    "Discounts",
    "Licenses",
    "Moderation",
    "Products",
    "Refunds",
    "Stats",
    "Subscriptions",
    "Transactions",
]
