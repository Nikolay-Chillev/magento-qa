"""Fill a shopper's cart from the test, without clicking through the catalog.

Products are added with the storefront's own add-to-cart endpoint, called from
the page itself, so the cart belongs to that browser's session and every engine
stores the session cookie its own way. (Requests from Playwright's API context
share cookies with the page too, but Firefox then drops the session cookie for an
IP-address host.) This must happen before the test opens its first store page:

* the form key normally comes from a cookie that Luma's JavaScript creates; the
  test sets its own, which Magento accepts the same way;
* Luma caches cart data in localStorage and only reloads it when the
  ``section_data_clean`` cookie is set, which the helper does at the end.
"""

import secrets
from collections.abc import Sequence
from dataclasses import dataclass, field
from urllib.parse import unquote

import allure
from playwright.sync_api import BrowserContext, Page

from magento_qa.models.cart import VariantOption


@dataclass(frozen=True)
class SeedItem:
    product_id: int
    qty: int = 1
    options: Sequence[VariantOption] = field(default_factory=tuple)


class CartSeedError(AssertionError):
    pass


# Posts a form from the page; the redirect Magento answers with is not followed.
POST_FORM = """async ({url, form}) => {
    await fetch(url, {method: "POST", body: new URLSearchParams(form), redirect: "manual"});
}"""


def seed_cart(page: Page, base_url: str, items: Sequence[SeedItem]) -> None:
    """Add ``items`` to the cart of ``page``'s browser before the test opens a store page."""
    context = page.context
    # A plain-text page of the store, so the requests below come from its origin.
    page.goto(f"{base_url}robots.txt")
    form_key = secrets.token_hex(8)
    context.add_cookies([{"name": "form_key", "value": form_key, "url": base_url}])
    for item in items:
        with allure.step(f"Seed cart: product {item.product_id} x {item.qty}"):
            form = {"product": str(item.product_id), "qty": str(item.qty), "form_key": form_key}
            for option in item.options:
                form[f"super_attribute[{option.option_id}]"] = str(option.option_value)
            page.evaluate(POST_FORM, {"url": f"{base_url}checkout/cart/add", "form": form})
            _raise_unless_added(context)
    # Any non-numeric value: Luma parses the cookie as JSON and ignores numbers.
    context.add_cookies([{"name": "section_data_clean", "value": "seeded", "url": base_url}])


def _raise_unless_added(context: BrowserContext) -> None:
    """Magento reports the result in the ``mage-messages`` cookie; consume it."""
    cookies = {cookie["name"]: cookie for cookie in context.cookies()}
    messages = unquote(cookies.get("mage-messages", {}).get("value", ""))
    context.clear_cookies(name="mage-messages")
    if '"type":"success"' not in messages:
        raise CartSeedError(f"Product was not added to the cart: {messages or 'no message'}")
