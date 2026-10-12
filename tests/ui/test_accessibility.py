"""Accessibility of the key pages, scanned with axe-core (WCAG 2.1 A and AA).

Luma has known violations, so each page is compared with a baseline: the rule and
element pairs axe reports today, each explained by a finding. A new pair fails the
test, even for a known rule on another element; so does a pair that disappears, so
the baseline is only ever shortened on purpose.

Scanned in Chromium only: axe runs the same rules on the same page in every engine.
"""

import uuid
from collections.abc import Callable, Sequence

import allure
import pytest
from playwright.sync_api import Page, expect

from magento_qa.a11y import scan
from magento_qa.api.catalog import CatalogClient
from magento_qa.api.customers import CustomerClient
from magento_qa.data.factories import new_customer
from magento_qa.ui.cart_seed import SeedItem
from magento_qa.ui.pages import (
    CartPage,
    CheckoutPage,
    HomePage,
    LoginPage,
    ProductListPage,
    ProductPage,
    RegisterPage,
)

pytestmark = [pytest.mark.ui, pytest.mark.a11y, pytest.mark.only_browser("chromium")]

MENU_HIDDEN = 75  # main menu hidden from screen readers
ERROR_CONTRAST = 76  # error messages below 4.5:1
ARIA_STRUCTURE = 77  # product tabs, checkout steps, CAPTCHA field

# Rule and element pairs reported with axe-core 4.12.1 on Magento 2.4.9 with Luma,
# and the finding that explains each. Elements are axe's selectors.
MENU = ("aria-hidden-focus", r"#store\.menu")
KNOWN: dict[str, dict[tuple[str, str], int]] = {
    "home": {MENU: MENU_HIDDEN},
    "category": {MENU: MENU_HIDDEN},
    "product": {
        MENU: MENU_HIDDEN,
        ("aria-required-children", '.mage-tabs-disabled.items[role="tablist"]'): ARIA_STRUCTURE,
        ("nested-interactive", "#tab-label-description"): ARIA_STRUCTURE,
        ("nested-interactive", "#tab-label-additional"): ARIA_STRUCTURE,
        ("nested-interactive", "#tab-label-reviews"): ARIA_STRUCTURE,
    },
    "cart": {MENU: MENU_HIDDEN},
    "checkout": {("list", "#checkoutSteps"): ARIA_STRUCTURE},
    "sign-in": {MENU: MENU_HIDDEN},
    "sign-in after failed attempts": {
        MENU: MENU_HIDDEN,
        ("aria-roles", 'div[role="user_login"]'): ARIA_STRUCTURE,
        ("color-contrast", ".message-error > div"): ERROR_CONTRAST,
    },
    "registration": {MENU: MENU_HIDDEN},
}

JACKETS = "women/tops-women/jackets-women.html"
JACKET = "olivia-1-4-zip-light-jacket.html"
BAG_SKU = "24-MB01"

Seed = Callable[[Sequence[SeedItem]], None]


def assert_only_known_violations(page: Page, name: str) -> None:
    found = {
        (violation.rule, target): violation
        for violation in scan(page).values()
        for target in violation.targets
    }
    known = KNOWN[name]

    new = [
        f"{rule} at {target}: {violation.help}"
        for (rule, target), violation in found.items()
        if (rule, target) not in known
    ]
    gone = [
        f"{rule} at {target} (finding #{finding})"
        for (rule, target), finding in known.items()
        if (rule, target) not in found
    ]
    assert not new, f"New accessibility violations on the {name} page: {new}"
    assert not gone, f"No longer reported on the {name} page, remove from KNOWN: {gone}"


@allure.feature("Accessibility")
@allure.story("Key pages")
class TestKeyPages:
    @allure.title("Home page: no accessibility violations beyond the known ones")
    def test_home(self, page: Page) -> None:
        HomePage(page).open()
        assert_only_known_violations(page, "home")

    @allure.title("Category page: no accessibility violations beyond the known ones")
    def test_category(self, page: Page) -> None:
        ProductListPage(page, JACKETS).open()
        assert_only_known_violations(page, "category")

    @allure.title("Product page: no accessibility violations beyond the known ones")
    def test_product(self, page: Page) -> None:
        ProductPage(page, JACKET).open()
        assert_only_known_violations(page, "product")

    @allure.title("Cart: no accessibility violations beyond the known ones")
    def test_cart(self, page: Page, seed: Seed, catalog: CatalogClient) -> None:
        seed([SeedItem(catalog.product(BAG_SKU).id)])
        CartPage(page).open()
        assert_only_known_violations(page, "cart")

    @allure.title("Checkout: no accessibility violations beyond the known ones")
    def test_checkout(self, page: Page, seed: Seed, catalog: CatalogClient) -> None:
        seed([SeedItem(catalog.product(BAG_SKU).id)])
        CheckoutPage(page).open()
        assert_only_known_violations(page, "checkout")

    @allure.title("Sign-in page: no accessibility violations beyond the known ones")
    def test_sign_in(self, page: Page) -> None:
        LoginPage(page).open()
        assert_only_known_violations(page, "sign-in")

    @allure.title("Sign-in after failed attempts, with the error and the CAPTCHA shown")
    def test_sign_in_after_failed_attempts(self, page: Page, customers: CustomerClient) -> None:
        customer = new_customer()
        customers.register(customer)
        login = LoginPage(page).open()
        for _ in range(3):
            login.sign_in(customer.email, f"Wrong!{uuid.uuid4().hex[:8]}")
        expect(login.captcha).to_be_visible()
        expect(login.message("The account sign-in was incorrect")).to_be_visible()

        assert_only_known_violations(page, "sign-in after failed attempts")

    @allure.title("Registration page: no accessibility violations beyond the known ones")
    def test_registration(self, page: Page) -> None:
        RegisterPage(page).open()
        assert_only_known_violations(page, "registration")
