"""Parts shared by every Luma page: header, mini-cart and loading indicators."""

from playwright.sync_api import Locator, Page, expect

# Luma shows these while it loads data with JavaScript.
LOADERS = ".loading-mask, #checkout-loader, [data-role='loader']"


def wait_for_luma(page: Page) -> None:
    """Wait until no Luma loading indicator is visible."""
    expect(page.locator(LOADERS).filter(visible=True)).to_have_count(0)


class MiniCart:
    def __init__(self, page: Page) -> None:
        self.page = page
        self.panel = page.locator("#minicart-content-wrapper")

    @property
    def product_names(self) -> Locator:
        return self.panel.locator(".product-item-name")


class Header:
    def __init__(self, page: Page) -> None:
        self.page = page
        self.search_box = page.get_by_role("combobox", name="Search")
        self.cart_count = page.locator(".minicart-wrapper .counter-number")
        self._cart_link = page.locator(".minicart-wrapper a.showcart")

    def open_mini_cart(self) -> MiniCart:
        self._cart_link.click()
        mini_cart = MiniCart(self.page)
        expect(mini_cart.panel).to_be_visible()
        return mini_cart
