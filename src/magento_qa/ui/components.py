"""Parts shared by every Luma page: header, mini-cart and loading indicators."""

from playwright.sync_api import Locator, Page, expect

# Luma shows these while it loads data with JavaScript.
LOADERS = ".loading-mask, #checkout-loader, [data-role='loader']"

# Luma's customer data (name in the header, mini-cart, messages) is refreshed by a
# script that watches form submissions. A form sent before the scripts have loaded
# leaves that data stale (finding #53), so tests act only once they are ready.
SCRIPTS_READY = """() => {
    if (!window.require || !window.jQuery
        || !require.defined('Magento_Customer/js/customer-data')) {
        return false;
    }
    const customerData = require('Magento_Customer/js/customer-data');
    return customerData.getInitCustomerData().state() === 'resolved' && jQuery.active === 0;
}"""


def wait_for_luma(page: Page) -> None:
    """Wait until Luma's scripts are ready and idle and no loading indicator is visible."""
    page.wait_for_function(SCRIPTS_READY)
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
