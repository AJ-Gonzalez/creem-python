"""Browser automation: complete a hosted Creem checkout with the test card.

Used by the live test suite to create real sandbox orders, which unlocks
subscription, refund, and license flows that need a completed payment.

Requires playwright::

    pip install playwright
    playwright install chromium

The flow mirrors the hosted checkout page:

1. Fill email and name
2. Select the billing country (a native select styled as a combobox)
3. Continue to payment -> address step (US requires the full address)
4. Fill address, select the state, continue
5. Fill the card fields: UNO hosts the card form in an iframe with inputs
   ``number``, ``expirationDate``, ``cvv``; the main page has
   ``cardHolderName``
6. Pay and wait for the success URL

Raises playwright TimeoutError when the page structure changes.
"""

from __future__ import annotations

from playwright.sync_api import Frame, Page, sync_playwright

TEST_CARD_NUMBER = "4111 1111 1111 1111"
TEST_CARD_EXPIRY = "12/30"
TEST_CARD_CVC = "123"


def _card_frame(page: Page) -> Frame:
    """Return the UNO card iframe frame."""
    return next(
        f for f in page.frames if f.locator("input[name='number']").count() > 0
    )


def complete_checkout(
    checkout_url: str,
    *,
    email: str = "checkout-bot@example.com",
    success_url_pattern: str = "**/success*",
) -> None:
    """Complete the checkout and wait for the success redirect."""
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            page = browser.new_page()
            page.goto(checkout_url, wait_until="domcontentloaded")

            page.fill("#email", email)
            page.fill("#name", "Checkout Bot")

            # The billing country is a native select styled as a combobox;
            # select_option works on it directly, even when visually hidden.
            page.select_option("select >> nth=0", "US")

            page.click("button:has-text('Continue to payment')")
            page.wait_for_selector("input[name='addressLine1']")

            page.fill("input[name='addressLine1']", "1 Main St")
            page.fill("input[name='city']", "Springfield")
            page.fill("input[name='postalCode']", "12345")
            page.select_option("select >> nth=1", index=1)

            page.click("button:has-text('Continue to payment')")
            page.wait_for_selector("button:has-text('Pay')")

            # Card fields: cardHolderName on the page, the rest in the UNO
            # card iframe.
            page.fill("input[name='cardHolderName']", "Checkout Bot")
            frame = _card_frame(page)
            frame.locator("input[name='number']").fill(TEST_CARD_NUMBER.replace(" ", ""))
            frame.locator("input[name='expirationDate']").fill(TEST_CARD_EXPIRY.replace("/", ""))
            frame.locator("input[name='cvv']").fill(TEST_CARD_CVC)

            page.click("button:has-text('Pay')")
            page.wait_for_url(success_url_pattern, timeout=30_000)
        finally:
            browser.close()
