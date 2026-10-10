"""Finding a product in the browser: search, category filters and sorting, the product
page and the mini-cart, on a desktop and on a phone-sized screen.

The tests only read the Luma sample data; the one that adds to the cart uses this
test's own guest session.
"""

import re
from decimal import Decimal

import allure
import pytest
from playwright.sync_api import Page, expect

from magento_qa.ui.pages import HomePage, ProductListPage

pytestmark = pytest.mark.ui

JACKETS = "women/tops-women/jackets-women.html"
JACKET = "Olivia 1/4 Zip Light Jacket"  # offered in M and Black
PHONE = {"viewport": {"width": 390, "height": 844}, "has_touch": True}


def prices(listing: ProductListPage) -> list[Decimal]:
    return [Decimal(text.lstrip("€").replace(",", "")) for text in listing.prices.all_inner_texts()]


def item_count(listing: ProductListPage) -> int:
    """The total from the toolbar: "12 Items" or "Items 1-12 of 14"."""
    numbers = re.findall(r"\d+", listing.amount.inner_text())
    return int(numbers[-1])


@allure.feature("Storefront")
@allure.story("Catalog")
class TestSearch:
    @allure.severity(allure.severity_level.CRITICAL)
    @allure.title("A search from the header lists matching products")
    def test_search_from_the_header(self, page: Page) -> None:
        results = HomePage(page).open().search("bag")

        expect(results.heading).to_have_text("Search results for: 'bag'")
        expect(page).to_have_url(re.compile(r"[?&]q=bag\b"))
        expect(results.product_names.filter(has_text="Joust Duffle Bag")).to_have_count(1)
        assert item_count(results) == results.products.count() > 0

    @allure.severity(allure.severity_level.NORMAL)
    @allure.title("A search without matches says so")
    def test_search_without_results(self, page: Page) -> None:
        results = HomePage(page).open().search("qwertyzxcv")

        expect(page.get_by_text("Your search returned no results.")).to_be_visible()
        expect(results.products).to_have_count(0)


@allure.feature("Storefront")
@allure.story("Catalog")
class TestCategoryPage:
    @allure.severity(allure.severity_level.CRITICAL)
    @allure.title("Size and colour filters narrow the list to products offered in both")
    def test_filter_by_size_and_colour(self, page: Page) -> None:
        jackets = ProductListPage(page, JACKETS).open()
        all_jackets = item_count(jackets)

        jackets.filter_by("Size", "M").filter_by("Color", "Black")

        expect(jackets.active_filters).to_contain_text(["Size", "Color"])
        expect(jackets.active_filters).to_contain_text(["M", "Black"])
        assert 0 < jackets.products.count() < all_jackets
        for product in jackets.products.all():
            assert {"M", "Black"} <= set(jackets.offered_options(product))

        jackets.clear_filters()
        assert item_count(jackets) == all_jackets

    @allure.severity(allure.severity_level.NORMAL)
    @allure.title("The price filter keeps only products in the chosen range")
    def test_filter_by_price(self, page: Page) -> None:
        jackets = ProductListPage(page, JACKETS).open()

        jackets.filter_by("Price", "€50.00 - €59.99")

        found = prices(jackets)
        assert found
        assert all(Decimal(50) <= price < Decimal(60) for price in found), found

    @pytest.mark.parametrize("descending", [False, True], ids=["ascending", "descending"])
    @allure.severity(allure.severity_level.NORMAL)
    @allure.title("Products can be sorted by price")
    def test_sort_by_price(self, page: Page, descending: bool) -> None:
        jackets = ProductListPage(page, JACKETS).open()

        jackets.sort_by("Price", descending=descending)

        found = prices(jackets)
        assert len(found) > 1
        assert found == sorted(found, reverse=descending)


@allure.feature("Storefront")
@allure.story("Catalog")
class TestFromListToCart:
    @allure.severity(allure.severity_level.BLOCKER)
    @allure.title("A shopper filters jackets, picks a size and colour and adds one to the cart")
    def test_filter_choose_and_add(self, page: Page) -> None:
        jackets = ProductListPage(page, JACKETS).open()
        jackets.filter_by("Size", "M").filter_by("Color", "Black")

        product = jackets.open_product(JACKET)
        expect(product.title).to_have_text(JACKET)
        product.choose(size="M", color="Black").add_to_cart()

        expect(product.header.cart_count).to_have_text("1")
        mini_cart = product.header.open_mini_cart()
        expect(mini_cart.product_names).to_have_text([JACKET])

    @pytest.mark.browser_context_args(**PHONE)
    @allure.severity(allure.severity_level.CRITICAL)
    @allure.title("On a phone a shopper searches, filters and adds a product to the cart")
    def test_on_a_phone(self, page: Page) -> None:
        assert page.viewport_size == PHONE["viewport"]
        results = HomePage(page).open().search("jacket")
        expect(results.heading).to_have_text("Search results for: 'jacket'")

        jackets = ProductListPage(page, JACKETS).open()
        jackets.filter_by("Size", "M")
        expect(jackets.active_filters).to_contain_text(["M"])

        product = jackets.open_product(JACKET)
        product.choose(size="M", color="Black").add_to_cart()

        expect(product.header.cart_count).to_have_text("1")
