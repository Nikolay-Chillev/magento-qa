"""Page objects for the Luma storefront.

Locators prefer what a shopper perceives (roles, accessible names, labels) and
fall back to Magento's ``data-`` attributes; layout classes are the last resort.
"""

import re

import allure
from playwright.sync_api import Locator, Page, expect

from magento_qa.models.address import Address
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
            "option", name=label
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
        self.message = page.locator(".checkout-success")

    @property
    def order_number(self) -> str:
        expect(self.message).to_contain_text("Your order # is:")
        match = re.search(r"Your order # is: (\d+)", self.message.inner_text())
        assert match, "No order number on the success page"
        return match.group(1)
