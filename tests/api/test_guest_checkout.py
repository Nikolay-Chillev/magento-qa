"""Guest checkout through the REST API, the journey that brings in the money.

A guest with a Bulgarian address buys two units of a simple product, pays by
check / money order and gets flat-rate shipping. Each test places its own order
with a unique email, so the tests are independent and safe to run in parallel.
"""

from dataclasses import dataclass
from decimal import Decimal

import allure
import pytest

from magento_qa.api.admin import AdminClient
from magento_qa.api.errors import MagentoApiError
from magento_qa.api.guest_cart import GuestCartClient
from magento_qa.data.factories import bulgarian_address
from magento_qa.mail.mailpit import MailpitClient
from magento_qa.models.address import Address
from magento_qa.models.cart import CartItem, Totals

pytestmark = pytest.mark.api

PRODUCT_SKU = "24-MB01"  # Joust Duffle Bag, a simple product from the Luma sample data
QUANTITY = 2


@dataclass(frozen=True)
class PlacedOrder:
    order_id: int
    address: Address
    item: CartItem
    totals: Totals


@pytest.fixture
def placed_order(guest_cart: GuestCartClient, bulgarian_region_ids: dict[str, int]) -> PlacedOrder:
    address = bulgarian_address(bulgarian_region_ids)
    assert address.email
    cart_id = guest_cart.create()
    item = guest_cart.add_item(cart_id, PRODUCT_SKU, qty=QUANTITY)
    details = guest_cart.set_shipping_information(cart_id, address)
    order_id = guest_cart.place_order(cart_id, email=address.email, billing_address=address)
    return PlacedOrder(order_id=order_id, address=address, item=item, totals=details.totals)


@allure.feature("Checkout")
@allure.story("Guest checkout")
class TestGuestCheckout:
    @allure.severity(allure.severity_level.CRITICAL)
    @allure.title("Cart totals add up: price x quantity + shipping + tax")
    def test_totals_add_up(self, placed_order: PlacedOrder) -> None:
        totals = placed_order.totals

        assert totals.subtotal == placed_order.item.price * QUANTITY
        assert totals.shipping_amount > 0
        assert totals.grand_total == (
            totals.subtotal + totals.shipping_amount + totals.tax_amount + totals.discount_amount
        )
        assert totals.quote_currency_code == "EUR"

    @allure.severity(allure.severity_level.BLOCKER)
    @allure.title("The back office records the guest order as placed")
    def test_order_is_recorded(self, placed_order: PlacedOrder, admin: AdminClient) -> None:
        order = admin.get_order(placed_order.order_id)

        assert (order.state, order.status) == ("new", "pending")
        assert order.customer_is_guest
        assert order.customer_email == placed_order.address.email
        ordered = [(item.sku, item.qty_ordered) for item in order.items]
        assert ordered == [(PRODUCT_SKU, Decimal(QUANTITY))]
        assert order.grand_total == placed_order.totals.grand_total
        assert order.order_currency_code == "EUR"
        assert order.payment.method == "checkmo"

    @allure.severity(allure.severity_level.CRITICAL)
    @allure.title("The order keeps the Bulgarian address and oblast")
    def test_order_keeps_bulgarian_address(
        self, placed_order: PlacedOrder, admin: AdminClient
    ) -> None:
        billing = admin.get_order(placed_order.order_id).billing_address
        sent = placed_order.address

        assert (billing.firstname, billing.lastname) == (sent.firstname, sent.lastname)
        assert (billing.street, billing.city, billing.postcode) == (
            sent.street,
            sent.city,
            sent.postcode,
        )
        assert (billing.country_id, billing.region_id) == ("BG", sent.region_id)

    @pytest.mark.email
    @allure.severity(allure.severity_level.CRITICAL)
    @allure.title("The guest gets an order confirmation email with the order number and item")
    def test_confirmation_email(
        self, placed_order: PlacedOrder, admin: AdminClient, mailpit: MailpitClient
    ) -> None:
        assert placed_order.address.email
        order = admin.get_order(placed_order.order_id)

        email = mailpit.wait_for_message(
            to=placed_order.address.email, subject="order confirmation"
        )

        assert f"#{order.increment_id}" in email.html
        assert placed_order.item.name in email.html
        assert placed_order.address.firstname in email.html

    @allure.severity(allure.severity_level.NORMAL)
    @allure.title("A Bulgarian address without an oblast cannot be used to place an order")
    def test_address_without_region_is_rejected(
        self, guest_cart: GuestCartClient, bulgarian_region_ids: dict[str, int]
    ) -> None:
        address = bulgarian_address(bulgarian_region_ids).model_copy(
            update={"region_id": None, "region_code": None}
        )
        assert address.email
        cart_id = guest_cart.create()
        guest_cart.add_item(cart_id, PRODUCT_SKU)
        guest_cart.set_shipping_information(cart_id, address)

        with pytest.raises(MagentoApiError, match='"regionId" is required') as error:
            guest_cart.place_order(cart_id, email=address.email, billing_address=address)

        assert error.value.status == 400
