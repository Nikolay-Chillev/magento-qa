"""Page objects for the Luma storefront.

Locators prefer what a shopper perceives (roles, accessible names, labels) and
fall back to Magento's ``data-`` attributes; layout classes are the last resort.
"""

import re
from collections.abc import Callable
from decimal import Decimal

import allure
from playwright.sync_api import Locator, Page, expect

from magento_qa.models.address import Address
from magento_qa.models.customer import NewCustomer
from magento_qa.ui.components import Header, wait_for_luma


class StorePage:
    path = ""

    def __init__(self, page: Page) -> None:
        self.page = page
        self.header = Header(page)

    def open(self) -> "StorePage":
        with allure.step(f"Open /{self.path}"):
            self.page.goto(self.path)
            wait_for_luma(self.page)
        return self

    def message(self, text: str) -> Locator:
        """A success or error message shown at the top of the page."""
        return self.page.get_by_role("alert").filter(has_text=text)

    def search(self, text: str) -> "SearchResultsPage":
        with allure.step(f"Search for {text!r} from the header"):
            self.header.search_box.fill(text)
            self.header.search_box.press("Enter")
            self.page.wait_for_url("**/catalogsearch/result/**")
            wait_for_luma(self.page)
        return SearchResultsPage(self.page)


class HomePage(StorePage):
    path = ""

    def __init__(self, page: Page) -> None:
        super().__init__(page)
        self.product_links = page.locator(".product-items .product-item-link")

    def open(self) -> "HomePage":
        super().open()
        return self

    def open_product(self, name: str) -> "ProductPage":
        with allure.step(f"Open product {name!r} from the home page"):
            self.product_links.filter(has_text=name).first.click()
            product = ProductPage(self.page)
            wait_for_luma(self.page)
        return product


class ProductPage(StorePage):
    def __init__(self, page: Page, path: str = "") -> None:
        super().__init__(page)
        self.path = path
        self.title = page.get_by_role("heading", level=1)
        self.price = page.locator(".product-info-main [data-price-type='finalPrice'] .price")
        self.add_to_cart_button = page.get_by_role("button", name="Add to Cart")
        self.success_message = page.get_by_role("alert").filter(has_text="You added")

    def open(self) -> "ProductPage":
        super().open()
        return self

    def option(self, attribute_code: str, label: str) -> Locator:
        """A swatch, e.g. ``option("size", "XS")`` or ``option("color", "Blue")``."""
        return self.page.locator(f"[data-attribute-code='{attribute_code}']").get_by_role(
            "option", name=label, exact=True
        )

    def choose(self, **options: str) -> "ProductPage":
        """Pick swatches by attribute code, e.g. ``choose(size="XS", color="Blue")``."""
        for code, label in options.items():
            with allure.step(f"Choose {code} {label}"):
                swatch = self.option(code, label)
                swatch.click()
                expect(swatch).to_have_attribute("aria-checked", "true")
        return self

    def add_to_cart(self) -> "ProductPage":
        with allure.step("Add to cart"):
            self.add_to_cart_button.click()
            expect(self.success_message).to_be_visible()
        return self


class CheckoutPage(StorePage):
    """Luma's one-page checkout: shipping step, then payment step."""

    path = "checkout/"

    def __init__(self, page: Page) -> None:
        super().__init__(page)
        self.shipping_step = page.locator("#checkout-step-shipping")
        self.shipping_form = page.locator("#co-shipping-form")
        self.email = page.get_by_role("textbox", name="Email Address")
        # A hidden text input shares the label; the select is the one shoppers use.
        self.region = self.shipping_form.get_by_role("combobox", name="State/Province")
        self.next_button = page.get_by_role("button", name="Next")
        self.payment_method = page.locator(".payment-method._active")
        self.grand_total = page.locator(".opc-block-summary .grand.totals .price")

    def open(self) -> "CheckoutPage":
        with allure.step("Open the checkout"):
            self.page.goto(self.path)
            expect(self.shipping_step).to_be_visible()
            wait_for_luma(self.page)
        return self

    def field(self, label: str) -> Locator:
        return self.shipping_form.get_by_label(label, exact=True)

    def fill_shipping_address(self, address: Address) -> "CheckoutPage":
        with allure.step(f"Fill the shipping address in {address.city}, {address.country_id}"):
            assert address.email, "A guest checkout needs an email address"
            self.email.fill(address.email)
            self.field("First Name").fill(address.firstname)
            self.field("Last Name").fill(address.lastname)
            self.field("Street Address: Line 1").fill(address.street[0])
            # The region list depends on the country, so the country comes first.
            self.field("Country").select_option(address.country_id)
            if address.region_id is not None:
                self.region.select_option(str(address.region_id))
            self.field("City").fill(address.city)
            self.field("Zip/Postal Code").fill(address.postcode)
            self.field("Phone Number").fill(address.telephone)
            wait_for_luma(self.page)
        return self

    def choose_shipping(self, method: str = "flatrate_flatrate") -> "CheckoutPage":
        with allure.step(f"Choose shipping {method}"):
            self.page.locator(f"#checkout-shipping-method-load input[value='{method}']").check()
        return self

    def continue_to_payment(self) -> "CheckoutPage":
        with allure.step("Continue to payment"):
            self.next_button.click()
            expect(self.payment_method).to_be_visible()
            wait_for_luma(self.page)
        return self

    def place_order(self) -> "SuccessPage":
        with allure.step("Place the order"):
            self.payment_method.get_by_role("button", name="Place Order").click()
            self.page.wait_for_url(f"**/{SuccessPage.path}")
        return SuccessPage(self.page)


class SuccessPage(StorePage):
    path = "checkout/onepage/success/"

    def __init__(self, page: Page) -> None:
        super().__init__(page)
        self.heading = page.get_by_role("heading", level=1)
        self.confirmation = page.locator(".checkout-success")

    @property
    def order_number(self) -> str:
        expect(self.confirmation).to_contain_text("Your order # is:")
        match = re.search(r"Your order # is: (\d+)", self.confirmation.inner_text())
        assert match, "No order number on the success page"
        return match.group(1)


def money(amount: Decimal) -> str:
    """Format an amount the way the store shows it, e.g. ``€4.90``."""
    return f"€{amount:.2f}"


class CartPage(StorePage):
    path = "checkout/cart/"

    def __init__(self, page: Page) -> None:
        super().__init__(page)
        self.totals = page.locator("#cart-totals")
        self.discount_row = self.totals.locator("tr").filter(has_text="Discount")
        self.order_total = self.totals.locator("tr.grand.totals")
        self._discount_block = page.locator("#block-discount")
        self._discount_title = page.locator("#block-discount-heading")
        self.coupon_field = page.get_by_label("Enter discount code")
        self.apply_button = page.get_by_role("button", name="Apply Discount")
        self.cancel_button = page.get_by_role("button", name="Cancel Coupon")

    def open(self) -> "CartPage":
        with allure.step("Open the cart"):
            self.page.goto(self.path)
            wait_for_luma(self.page)
            # The totals table is filled in by JavaScript after load.
            expect(self.order_total).to_be_visible()
        return self

    def _open_discount_form(self) -> None:
        # The section is collapsed by default; Luma marks it open only with a CSS class.
        if "active" not in (self._discount_block.get_attribute("class") or ""):
            self._discount_title.click()
        expect(self._discount_block).to_have_class(re.compile(r"\bactive\b"))

    def apply_coupon(self, code: str) -> "CartPage":
        with allure.step(f"Apply coupon {code}"):
            self._open_discount_form()
            self.coupon_field.fill(code)
            self.apply_button.click()
            self.page.wait_for_load_state()
            wait_for_luma(self.page)
            expect(self.order_total).to_be_visible()
        return self

    def cancel_coupon(self) -> "CartPage":
        with allure.step("Cancel the coupon"):
            self._open_discount_form()
            self.cancel_button.click()
            self.page.wait_for_load_state()
            wait_for_luma(self.page)
            expect(self.order_total).to_be_visible()
        return self


class RegisterPage(StorePage):
    path = "customer/account/create/"

    def __init__(self, page: Page) -> None:
        super().__init__(page)
        # The hidden sign-in pop-up has a "Password" field too, so fields are found in the form.
        self.form = page.locator("form.form-create-account")
        self.create_button = self.form.get_by_role("button", name="Create an Account")

    def open(self) -> "RegisterPage":
        super().open()
        return self

    def field(self, label: str) -> Locator:
        return self.form.get_by_label(label, exact=True)

    def fill(self, customer: NewCustomer) -> "RegisterPage":
        with allure.step(f"Fill the registration form for {customer.email}"):
            self.field("First Name").fill(customer.firstname)
            self.field("Last Name").fill(customer.lastname)
            self.field("Email").fill(customer.email)
            self.field("Password").fill(customer.password)
            self.field("Confirm Password").fill(customer.password)
        return self

    def register(self, customer: NewCustomer) -> "AccountPage":
        self.fill(customer)
        with allure.step("Create the account"):
            self.create_button.click()
            self.page.wait_for_url(f"**/{AccountPage.path}")
            wait_for_luma(self.page)
        return AccountPage(self.page)


class LoginPage(StorePage):
    path = "customer/account/login/"

    def __init__(self, page: Page) -> None:
        super().__init__(page)
        # The sign-in pop-up, added later by a script, reuses the same form id.
        self.form = page.locator(".login-container form.form-login")
        self.email = self.form.get_by_role("textbox", name="Email")
        # Magento 2.4.9's password label points to a missing id, so the field has no
        # label; its accessible name comes from the title attribute (fixed upstream).
        self.password = self.form.get_by_role("textbox", name="Password")
        self.sign_in_button = self.form.get_by_role("button", name="Sign In")
        # Shown after repeated wrong passwords. The pop-up's copy of the field has the
        # same id, so the label belongs to the pop-up and this field has no name.
        self.captcha = self.form.locator("input[name='captcha[user_login]']")
        self.captcha_image = self.form.get_by_role(
            "img", name="Please type the letters and numbers below"
        )

    def open(self) -> "LoginPage":
        super().open()
        return self

    def sign_in(self, email: str, password: str, *, captcha: str | None = None) -> None:
        with allure.step(f"Sign in as {email}"):
            self.email.fill(email)
            self.password.fill(password)
            if captcha is not None:
                self.captcha.fill(captcha)
            self.sign_in_button.click()
            self.page.wait_for_load_state()
            wait_for_luma(self.page)


class AccountPage(StorePage):
    """The customer's dashboard, "My Account"."""

    path = "customer/account/"

    def __init__(self, page: Page) -> None:
        super().__init__(page)
        self.heading = page.get_by_role("heading", level=1)
        self.contact_information = page.locator(".box-information .box-content")

    def open(self) -> "AccountPage":
        super().open()
        return self


class ResetPasswordPage(StorePage):
    """The "Set a New Password" page, opened from the link in the password reset email."""

    path = "customer/account/createPassword/"

    def __init__(self, page: Page) -> None:
        super().__init__(page)
        self.heading = page.get_by_role("heading", level=1)
        self.form = page.locator("form.password.reset")
        self.save_button = self.form.get_by_role("button", name="Set a New Password")

    def open_link(self, url: str) -> "ResetPasswordPage":
        with allure.step("Open the link from the reset email"):
            self.page.goto(url)
            wait_for_luma(self.page)
        return self

    def set_password(self, password: str) -> LoginPage:
        with allure.step("Set a new password"):
            self.form.get_by_label("New Password", exact=True).fill(password)
            self.form.get_by_label("Confirm New Password", exact=True).fill(password)
            self.save_button.click()
            self.page.wait_for_url(f"**/{LoginPage.path}")
            wait_for_luma(self.page)
        return LoginPage(self.page)


class ProductListPage(StorePage):
    """A list of products with Luma's toolbar and filters: a category or search results."""

    def __init__(self, page: Page, path: str | None = None) -> None:
        super().__init__(page)
        if path is not None:
            self.path = path
        self.heading = page.get_by_role("heading", level=1)
        self.products = page.locator(".products.list .product-item")
        self.product_names = self.products.locator(".product-item-link")
        self.prices = self.products.locator("[data-price-type='finalPrice'] .price")
        self.amount = page.locator(".toolbar-amount").first
        self.active_filters = page.locator(".filter-current .item")
        self._filters = page.locator("#narrow-by-list")
        # On a phone the filters hide behind a "Shop By" toggle.
        self._shop_by = page.get_by_role("tab", name="Shop By")

    def open(self) -> "ProductListPage":
        super().open()
        return self

    def filter_by(self, name: str, option: str) -> "ProductListPage":
        """Apply a filter, e.g. ``filter_by("Size", "M")`` or ``filter_by("Price", "€50.00")``."""
        with allure.step(f"Filter by {name}: {option}"):
            if (
                self._shop_by.is_visible()
                and self._shop_by.get_attribute("aria-expanded") != "true"
            ):
                self._shop_by.click()
            # A title's accessible name ends with an icon glyph from Luma's font, so the
            # title is matched by its text instead.
            title_text = re.compile(rf"^\s*{re.escape(name)}\s*$", re.IGNORECASE)
            section = self._filters.locator(".filter-options-item").filter(
                has=self.page.get_by_role("tab").filter(has_text=title_text)
            )
            title = section.get_by_role("tab")
            if title.get_attribute("aria-expanded") != "true":
                title.click()
            swatch = section.locator(f"[data-option-label='{option}']")
            # Swatches (size, colour) are pictures inside the links; other filters are text links.
            target = (
                swatch if swatch.count() else section.get_by_role("link").filter(has_text=option)
            )
            self._reload_by(target.click)
        return self

    def clear_filters(self) -> "ProductListPage":
        with allure.step("Clear all filters"):
            self._reload_by(self.page.get_by_role("link", name="Clear All").click)
        return self

    def sort_by(self, option: str, *, descending: bool = False) -> "ProductListPage":
        """Sort by a "Sort By" option, e.g. ``sort_by("Price", descending=True)``."""
        with allure.step(f"Sort by {option}{' descending' if descending else ''}"):
            sorter = self.page.get_by_label("Sort By").first
            self._reload_by(lambda: sorter.select_option(label=option))
            if descending:
                self._reload_by(
                    self.page.get_by_role("link", name="Set Descending Direction").first.click
                )
        return self

    def _reload_by(self, action: Callable[[], object]) -> None:
        """Run an action that reloads the list with new parameters, and wait for the new page.

        Luma changes the address from a script, so the old page stays loaded for a moment;
        waiting only for the load state could act on the old list.
        """
        before = self.page.url
        action()
        self.page.wait_for_url(lambda url: url != before)
        wait_for_luma(self.page)

    def product(self, name: str) -> Locator:
        return self.products.filter(has=self.page.get_by_role("link", name=name, exact=True))

    def offered_options(self, product: Locator) -> list[str]:
        """The sizes and colours a listed product offers, from its swatches."""
        return [
            label
            for label in product.locator("[data-option-label]").evaluate_all(
                "swatches => swatches.map(s => s.getAttribute('data-option-label'))"
            )
            if label
        ]

    def open_product(self, name: str) -> ProductPage:
        with allure.step(f"Open product {name!r}"):
            self.product_names.filter(has_text=name).first.click()
            wait_for_luma(self.page)
        return ProductPage(self.page)


class SearchResultsPage(ProductListPage):
    path = "catalogsearch/result/"
