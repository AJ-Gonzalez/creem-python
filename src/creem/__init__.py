"""Python SDK for the Creem.io REST API.

Quickstart::

    from creem import Creem

    creem = Creem()  # API key from the CREEM_API_KEY environment variable

    checkout = creem.checkouts.create(
        {"product_id": "prod_abc123", "success_url": "https://yoursite.com/success"}
    )
    # redirect the customer to checkout["checkout_url"]

The client auto-detects the sandbox environment from ``creem_test_`` key
prefixes; pass ``base_url`` to override. Response bodies are returned as
TypedDict models from :mod:`creem.models`; request payloads accept the
corresponding ``*Params`` TypedDict plus keyword overrides.
"""

from __future__ import annotations

from . import models
from .async_client import AsyncCreem
from .client import PROD_BASE_URL, TEST_BASE_URL, Creem
from .models import (
    Checkout,
    CheckoutCreateParams,
    CreditsAccount,
    CreditsBalance,
    Customer,
    CustomerCreateParams,
    Discount,
    License,
    Order,
    Product,
    ProductCreateParams,
    Refund,
    StatsSummary,
    Subscription,
    Transaction,
    WebhookSubscription,
)
from .errors import (
    CreemAPIError,
    CreemAuthError,
    CreemConfigurationError,
    CreemError,
    CreemNotFoundError,
    CreemRateLimitError,
    CreemServerError,
    CreemValidationError,
)
from .webhooks import (
    EventType,
    WebhookError,
    WebhookEvent,
    WebhookHandler,
    WebhookPayloadError,
    WebhookSignatureError,
    parse_event,
    verify_signature,
)

__version__ = "0.3.0"
__all__ = [
    "Checkout",
    "CheckoutCreateParams",
    "CreditsAccount",
    "CreditsBalance",
    "Customer",
    "CustomerCreateParams",
    "Discount",
    "License",
    "Order",
    "Product",
    "ProductCreateParams",
    "Refund",
    "StatsSummary",
    "Subscription",
    "SubscriptionCancelParams",
    "Transaction",
    "WebhookSubscription",
    "AsyncCreem",
    "Creem",
    "PROD_BASE_URL",
    "TEST_BASE_URL",
    "CreemError",
    "CreemConfigurationError",
    "CreemAPIError",
    "CreemValidationError",
    "CreemAuthError",
    "CreemNotFoundError",
    "CreemRateLimitError",
    "CreemServerError",
    "EventType",
    "WebhookError",
    "WebhookEvent",
    "WebhookHandler",
    "WebhookPayloadError",
    "WebhookSignatureError",
    "parse_event",
    "verify_signature",
    "models",
    "__version__",
]
