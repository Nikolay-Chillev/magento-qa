"""Promotions through the REST API: coupon codes and automatic cart price rules.

Sample-data rules are only read. Coupons a test needs are created through the admin
API with unique codes and deleted afterwards, so no global state is left behind and
parallel tests never see each other's coupons.
"""

import uuid
from collections.abc import Callable
from datetime import date, timedelta
from decimal import Decimal

import allure
import pytest

from magento_qa.api.admin import AdminClient
from magento_qa.api.errors import MagentoApiError
from magento_qa.api.guest_cart import GuestCartClient
from magento_qa.data.factories import bulgarian_address
from magento_qa.models.cart import VariantOption
from magento_qa.models.promotions import Coupon

pytestmark = pytest.mark.api

WATER_BOTTLE_SKU = "24-UG06"  # Affirm Water Bottle, the only product H20 discounts
BAG_SKU = "24-MB01"  # Joust Duffle Bag
TEE_SKU = "WS12"  # Radiant Tee, in the Tees category
INVALID_COUPON = "The coupon code isn't valid"


@pytest.fixture
def cart_id(guest_cart: GuestCartClient) -> str:
    return guest_cart.create()


@pytest.fixture(scope="module")
def blue_xs_tee(admin: AdminClient) -> list[VariantOption]:
    return admin.variant_options(TEE_SKU, {"Color": "Blue", "Size": "XS"})


@allure.feature("Promotions")
@allure.story("Coupon codes")
class TestCouponCodes:
    @allure.severity(allure.severity_level.CRITICAL)
    @allure.title("H20 takes 70% off the water bottle")
    def test_h20_takes_70_percent_off_the_water_bottle(
        self, guest_cart: GuestCartClient, cart_id: str
    ) -> None:
        bottle = guest_cart.add_item(cart_id, WATER_BOTTLE_SKU)

        guest_cart.apply_coupon(cart_id, "H20")

        totals = guest_cart.totals(cart_id)
        assert totals.coupon_code == "H20"
        assert totals.discount_amount == -(bottle.price * Decimal("0.70"))
        assert totals.grand_total == totals.subtotal + totals.discount_amount

    @allure.severity(allure.severity_level.CRITICAL)
    @allure.title("H20 is refused for a cart without the water bottle")
    def test_h20_needs_the_water_bottle(self, guest_cart: GuestCartClient, cart_id: str) -> None:
        guest_cart.add_item(cart_id, BAG_SKU)

        with pytest.raises(MagentoApiError, match=INVALID_COUPON):
            guest_cart.apply_coupon(cart_id, "H20")

        assert guest_cart.totals(cart_id).discount_amount == 0

    @allure.severity(allure.severity_level.NORMAL)
    @allure.title("An unknown code is refused")
    def test_unknown_code_is_rejected(self, guest_cart: GuestCartClient, cart_id: str) -> None:
        guest_cart.add_item(cart_id, BAG_SKU)

        with pytest.raises(MagentoApiError, match=INVALID_COUPON):
            guest_cart.apply_coupon(cart_id, f"NOPE-{uuid.uuid4().hex[:8]}")

    @allure.severity(allure.severity_level.NORMAL)
    @allure.title("Removing a coupon takes its discount away")
    def test_removing_a_coupon_removes_the_discount(
        self, guest_cart: GuestCartClient, cart_id: str
    ) -> None:
        guest_cart.add_item(cart_id, WATER_BOTTLE_SKU)
        guest_cart.apply_coupon(cart_id, "H20")

        guest_cart.remove_coupon(cart_id)

        totals = guest_cart.totals(cart_id)
        assert totals.coupon_code is None
        assert totals.discount_amount == 0

    @allure.severity(allure.severity_level.CRITICAL)
    @allure.title("A coupon works until its end date, not after")
    @pytest.mark.parametrize(
        ("to_date", "accepted"),
        [
            pytest.param(None, True, id="no-end-date"),
            pytest.param(date.today() + timedelta(days=7), True, id="ends-next-week"),
            pytest.param(date.today() - timedelta(days=2), False, id="expired"),
        ],
    )
    def test_coupon_end_date(
        self,
        guest_cart: GuestCartClient,
        cart_id: str,
        make_coupon: Callable[..., Coupon],
        to_date: date | None,
        accepted: bool,
    ) -> None:
        coupon = make_coupon(percent_off=10, to_date=to_date)
        bag = guest_cart.add_item(cart_id, BAG_SKU)

        if accepted:
            guest_cart.apply_coupon(cart_id, coupon.code)
            assert guest_cart.totals(cart_id).discount_amount == -(bag.price * Decimal("0.10"))
        else:
            with pytest.raises(MagentoApiError, match=INVALID_COUPON):
                guest_cart.apply_coupon(cart_id, coupon.code)


@allure.feature("Promotions")
@allure.story("Automatic promotions")
class TestAutomaticPromotions:
    @allure.severity(allure.severity_level.CRITICAL)
    @allure.title("Every fourth tee is free")
    @pytest.mark.parametrize(("tees", "free"), [(3, 0), (4, 1), (8, 2)])
    def test_every_fourth_tee_is_free(
        self,
        guest_cart: GuestCartClient,
        cart_id: str,
        blue_xs_tee: list[VariantOption],
        tees: int,
        free: int,
    ) -> None:
        tee = guest_cart.add_item(cart_id, TEE_SKU, qty=tees, options=blue_xs_tee)

        assert guest_cart.totals(cart_id).discount_amount == -(tee.price * free)

    @pytest.mark.xfail(
        strict=True,
        reason="Finding #35: the tee promotion discounts every product once a tee is in the cart",
    )
    @allure.severity(allure.severity_level.CRITICAL)
    @allure.title("The tee promotion does not give away other products")
    def test_tee_promotion_does_not_discount_other_products(
        self, guest_cart: GuestCartClient, cart_id: str, blue_xs_tee: list[VariantOption]
    ) -> None:
        guest_cart.add_item(cart_id, TEE_SKU, qty=1, options=blue_xs_tee)
        guest_cart.add_item(cart_id, BAG_SKU, qty=4)

        assert guest_cart.totals(cart_id).discount_amount == 0

    @allure.severity(allure.severity_level.NORMAL)
    @allure.title("Shipping is charged below the free-shipping threshold of 50")
    def test_shipping_is_charged_below_50(
        self, guest_cart: GuestCartClient, cart_id: str, bulgarian_region_ids: dict[str, int]
    ) -> None:
        bag = guest_cart.add_item(cart_id, BAG_SKU, qty=1)
        assert bag.price < 50

        totals = guest_cart.set_shipping_information(
            cart_id, bulgarian_address(bulgarian_region_ids)
        ).totals

        assert totals.shipping_amount > 0

    @pytest.mark.xfail(
        strict=True,
        reason="Finding #34: Flat Rate ignores the free shipping granted by the cart rule",
    )
    @allure.severity(allure.severity_level.CRITICAL)
    @allure.title("Shipping is free from a subtotal of 50")
    def test_shipping_is_free_from_50(
        self, guest_cart: GuestCartClient, cart_id: str, bulgarian_region_ids: dict[str, int]
    ) -> None:
        guest_cart.add_item(cart_id, BAG_SKU, qty=2)

        totals = guest_cart.set_shipping_information(
            cart_id, bulgarian_address(bulgarian_region_ids)
        ).totals

        assert totals.subtotal >= 50
        assert totals.shipping_amount == 0
