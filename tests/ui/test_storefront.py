"""Storefront smoke tests: the pages every journey starts from work in a browser."""

import re
from collections.abc import Callable, Sequence

import allure
import pytest
from playwright.sync_api import Page, expect

from magento_qa.api.admin import AdminClient
from magento_qa.api.catalog import CatalogClient
from magento_qa.ui.cart_seed import SeedItem
from magento_qa.ui.pages import HomePage

pytestmark = [pytest.mark.ui, pytest.mark.smoke]

PRICE = re.compile(r"^€\d+\.\d{2}$")


@allure.feature("Storefront")
@allure.story("Browsing")
class TestStorefront:
    @allure.severity(allure.severity_level.BLOCKER)
    @allure.title("The home page shows featured products")
    def test_home_page_shows_products(self, page: Page) -> None:
        home = HomePage(page).open()

        expect(page).to_have_title("Home Page")
        expect(home.product_links.first).to_be_visible()

    @allure.severity(allure.severity_level.BLOCKER)
    @allure.title("A product opens from the home page with its name, price and Add to Cart")
    def test_product_opens_from_the_home_page(self, page: Page) -> None:
        home = HomePage(page).open()
        name = home.product_links.first.inner_text().strip()

        product = home.open_product(name)

        expect(product.title).to_have_text(name)
        expect(product.price).to_have_text(PRICE)
        expect(product.add_to_cart_button).to_be_enabled()

    @allure.severity(allure.severity_level.CRITICAL)
    @allure.title("A cart filled by the test shows in the mini-cart")
    def test_seeded_cart_shows_in_the_mini_cart(
        self,
        page: Page,
        seed: Callable[[Sequence[SeedItem]], None],
        catalog: CatalogClient,
        admin: AdminClient,
    ) -> None:
        bag = catalog.product("24-MB01")
        tee = catalog.product("WS12")
        blue_xs = admin.variant_options("WS12", {"Color": "Blue", "Size": "XS"})
        seed([SeedItem(bag.id, qty=2), SeedItem(tee.id, options=blue_xs)])

        home = HomePage(page).open()

        expect(home.header.cart_count).to_have_text("3")
        mini_cart = home.header.open_mini_cart()
        expect(mini_cart.product_names).to_contain_text([tee.name, bag.name], ignore_case=True)
