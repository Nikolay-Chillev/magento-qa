"""Page objects for the Luma storefront.

Locators prefer what a shopper perceives (roles, accessible names, labels) and
fall back to Magento's ``data-`` attributes; layout classes are the last resort.
"""

import allure
from playwright.sync_api import Locator, Page, expect

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
