"""Examples compile and import cleanly."""

from __future__ import annotations

from pathlib import Path


EXAMPLES_DIR = Path(__file__).resolve().parent.parent / "examples"


def test_all_examples_compile() -> None:
    for path in sorted(EXAMPLES_DIR.glob("*.py")):
        compile(path.read_text(encoding="utf-8"), str(path), "exec")


def test_checkout_flow_imports() -> None:
    import examples.checkout_flow  # noqa: F401

    assert callable(examples.checkout_flow.main)


def test_subscription_management_imports() -> None:
    import examples.subscription_management

    assert callable(examples.subscription_management.main)


def test_customer_credits_imports() -> None:
    import examples.customer_credits

    assert callable(examples.customer_credits.main)


def test_browse_and_paginate_imports() -> None:
    import examples.browse_and_paginate

    assert callable(examples.browse_and_paginate.main)


def test_webhook_server_imports() -> None:
    import examples.webhook_server

    assert callable(examples.webhook_server.creem_webhook)
