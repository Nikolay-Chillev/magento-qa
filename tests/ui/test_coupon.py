"""Coupons on the cart page: what a shopper sees when they enter a code."""

from collections.abc import Callable, Sequence
from decimal import Decimal

import allure
import pytest
from playwright.sync_api import Page, expect

from magento_qa.api.catalog import CatalogClient
from magento_qa.ui.cart_seed import SeedItem
from magento_qa.ui.pages import CartPage, money

pytestmark = pytest.mark.ui

WATER_BOTTLE_SKU = "24-UG06"  # Affirm Water Bottle, the only product H20 discounts
BAG_SKU = "24-MB01"


@allure.feature("Promotions")
@allure.story("Coupon codes in the cart")
class TestCouponInCart:
    @allure.severity(allure.severity_level.CRITICAL)
    @allure.title("H20 entered in the cart shows its 70% discount, and cancelling removes it")
    def test_coupon_discount_shows_and_can_be_cancelled(
        self,
        page: Page,
        seed: Callable[[Sequence[SeedItem]], None],
        catalog: CatalogClient,
    ) -> None:
        bottle = catalog.product(WATER_BOTTLE_SKU)
        seed([SeedItem(bottle.id)])
        discount = bottle.price * Decimal("0.70")

        cart = CartPage(page).open().apply_coupon("H20")

        expect(cart.message('You used coupon code "H20".')).to_be_visible()
        expect(cart.discount_row).to_contain_text(f"-{money(discount)}")
        expect(cart.order_total).to_contain_text(money(bottle.price - discount))
        expect(cart.coupon_field).to_have_value("H20")
        expect(cart.coupon_field).to_be_disabled()

        cart.cancel_coupon()

        expect(cart.message("You canceled the coupon code.")).to_be_visible()
        expect(cart.discount_row).to_have_count(0)
        expect(cart.order_total).to_contain_text(money(bottle.price))

    @allure.severity(allure.severity_level.NORMAL)
    @allure.title("A code that does not apply to the cart is refused with a clear message")
    def test_code_that_does_not_apply_is_refused(
        self,
        page: Page,
        seed: Callable[[Sequence[SeedItem]], None],
        catalog: CatalogClient,
    ) -> None:
        seed([SeedItem(catalog.product(BAG_SKU).id)])

        cart = CartPage(page).open().apply_coupon("H20")

        expect(cart.message('The coupon code "H20" is not valid.')).to_be_visible()
        expect(cart.discount_row).to_have_count(0)
        expect(cart.coupon_field).to_be_enabled()
