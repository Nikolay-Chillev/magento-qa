"""Fill a shopper's cart from the test, without clicking through the catalog.

Products are added with the storefront's own add-to-cart endpoint through the
browser context's request API, so the cart belongs to that browser's session and
no page has to load first. This must happen before the test opens its first page:

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
from playwright.sync_api import APIResponse, BrowserContext

from magento_qa.models.cart import VariantOption


@dataclass(frozen=True)
class SeedItem:
    product_id: int
    qty: int = 1
    options: Sequence[VariantOption] = field(default_factory=tuple)


class CartSeedError(AssertionError):
    pass


def seed_cart(context: BrowserContext, base_url: str, items: Sequence[SeedItem]) -> None:
    """Add ``items`` to the cart of the browser ``context`` before it opens any page."""
    form_key = secrets.token_hex(8)
    context.add_cookies([{"name": "form_key", "value": form_key, "url": base_url}])
    for item in items:
        with allure.step(f"Seed cart: product {item.product_id} x {item.qty}"):
            form: dict[str, str | float | bool] = {
                "product": str(item.product_id),
                "qty": str(item.qty),
                "form_key": form_key,
            }
            for option in item.options:
                form[f"super_attribute[{option.option_id}]"] = str(option.option_value)
            response = context.request.post(
                f"{base_url}checkout/cart/add", form=form, max_redirects=0
            )
            _keep_session(context, base_url, response)
            _raise_unless_added(context)
    # Any non-numeric value: Luma parses the cookie as JSON and ignores numbers.
    context.add_cookies([{"name": "section_data_clean", "value": "seeded", "url": base_url}])


def _keep_session(context: BrowserContext, base_url: str, response: APIResponse) -> None:
    """Store the session cookie of ``response`` so later requests and pages share it.

    Magento sets it for the domain "127.0.0.1". Firefox drops such a cookie when it
    comes from the request API, so the next request and the test's pages would start
    new, empty sessions; a host-only cookie with the same value works in every engine.
    """
    for header in response.headers_array:
        name, _, rest = header["value"].partition("=")
        if header["name"].lower() == "set-cookie" and name.strip() == "PHPSESSID":
            session_id = rest.split(";", 1)[0]
            context.add_cookies([{"name": "PHPSESSID", "value": session_id, "url": base_url}])


def _raise_unless_added(context: BrowserContext) -> None:
    """Magento reports the result in the ``mage-messages`` cookie; consume it."""
    cookies = {cookie["name"]: cookie for cookie in context.cookies()}
    messages = unquote(cookies.get("mage-messages", {}).get("value", ""))
    context.clear_cookies(name="mage-messages")
    if '"type":"success"' not in messages:
        raise CartSeedError(f"Product was not added to the cart: {messages or 'no message'}")
