"""Guest cart through the REST API: contents, product variants, quantity rules and access.

Each test works on its own new cart, so the tests are independent and safe in parallel.
Catalog data comes from the Luma sample data and is only read.
"""

import uuid

import allure
import pytest

from magento_qa.api.admin import AdminClient
from magento_qa.api.errors import MagentoApiError
from magento_qa.api.guest_cart import GuestCartClient
from magento_qa.models.cart import VariantOption

pytestmark = pytest.mark.api

SIMPLE_SKU = "24-MB01"  # Joust Duffle Bag
HOODIE_SKU = "MH01"  # Chaz Kangeroo Hoodie: Color Black/Gray/Orange, Size XS-XL
QTY_FINDING = (
    "Finding #29: the REST cart API turns zero and negative quantities into 1 "
    "instead of rejecting them"
)


@pytest.fixture
def cart_id(guest_cart: GuestCartClient) -> str:
    return guest_cart.create()


@pytest.fixture(scope="module")
def black_xs(admin: AdminClient) -> list[VariantOption]:
    return admin.variant_options(HOODIE_SKU, {"Color": "Black", "Size": "XS"})


@allure.feature("Cart")
@allure.story("Cart contents")
class TestCartContents:
    @allure.severity(allure.severity_level.CRITICAL)
    @allure.title("Totals follow the items: row = price x quantity, subtotal = sum of rows")
    def test_totals_follow_the_items(
        self, guest_cart: GuestCartClient, cart_id: str, black_xs: list[VariantOption]
    ) -> None:
        guest_cart.add_item(cart_id, SIMPLE_SKU, qty=2)
        guest_cart.add_item(cart_id, HOODIE_SKU, qty=1, options=black_xs)

        totals = guest_cart.totals(cart_id)

        assert totals.items_qty == 3
        for row in totals.items:
            assert row.row_total == row.price * row.qty
        assert totals.subtotal == sum(row.row_total for row in totals.items)

    @allure.severity(allure.severity_level.CRITICAL)
    @allure.title("Changing the quantity recalculates the row")
    def test_changing_quantity_recalculates_the_row(
        self, guest_cart: GuestCartClient, cart_id: str
    ) -> None:
        item = guest_cart.add_item(cart_id, SIMPLE_SKU, qty=1)

        updated = guest_cart.update_item(cart_id, item.item_id, qty=3)

        assert updated.qty == 3
        (row,) = guest_cart.totals(cart_id).items
        assert row.row_total == item.price * 3

    @allure.severity(allure.severity_level.NORMAL)
    @allure.title("A removed item leaves the cart and the totals")
    def test_removed_item_leaves_the_cart(self, guest_cart: GuestCartClient, cart_id: str) -> None:
        item = guest_cart.add_item(cart_id, SIMPLE_SKU, qty=2)

        guest_cart.remove_item(cart_id, item.item_id)

        assert guest_cart.items(cart_id) == []
        assert guest_cart.totals(cart_id).subtotal == 0


@allure.feature("Cart")
@allure.story("Product variants")
class TestProductVariants:
    @allure.severity(allure.severity_level.CRITICAL)
    @allure.title("A chosen variant is added as that size and colour")
    def test_variant_is_added_with_the_chosen_options(
        self, guest_cart: GuestCartClient, cart_id: str, black_xs: list[VariantOption]
    ) -> None:
        item = guest_cart.add_item(cart_id, HOODIE_SKU, options=black_xs)

        assert item.sku == f"{HOODIE_SKU}-XS-Black"
        assert item.product_type == "configurable"
        assert item.variant_options == black_xs

    @allure.severity(allure.severity_level.NORMAL)
    @allure.title("A product with variants cannot be added without choosing one")
    def test_variant_must_be_chosen(self, guest_cart: GuestCartClient, cart_id: str) -> None:
        with pytest.raises(MagentoApiError, match="You need to choose options for your item"):
            guest_cart.add_item(cart_id, HOODIE_SKU)

        assert guest_cart.items(cart_id) == []

    @allure.severity(allure.severity_level.NORMAL)
    @allure.title("A colour the product is not made in cannot be added")
    def test_variant_the_product_does_not_offer_is_rejected(
        self, guest_cart: GuestCartClient, cart_id: str, admin: AdminClient
    ) -> None:
        red_xs = admin.variant_options(HOODIE_SKU, {"Color": "Red", "Size": "XS"})

        with pytest.raises(MagentoApiError):
            guest_cart.add_item(cart_id, HOODIE_SKU, options=red_xs)

        assert guest_cart.items(cart_id) == []


@allure.feature("Cart")
@allure.story("Quantity rules")
class TestQuantityRules:
    @allure.severity(allure.severity_level.CRITICAL)
    @allure.title("More than the stock cannot be added")
    def test_more_than_in_stock_is_rejected(
        self, guest_cart: GuestCartClient, cart_id: str, admin: AdminClient
    ) -> None:
        stock = admin.stock_item(SIMPLE_SKU).qty

        with pytest.raises(MagentoApiError, match="Not enough items for sale"):
            guest_cart.add_item(cart_id, SIMPLE_SKU, qty=float(stock + 1))

        assert guest_cart.items(cart_id) == []

    @allure.severity(allure.severity_level.NORMAL)
    @allure.title("Fractions of a product cannot be added")
    def test_decimal_quantity_is_rejected(self, guest_cart: GuestCartClient, cart_id: str) -> None:
        with pytest.raises(MagentoApiError, match="You cannot use decimal quantity"):
            guest_cart.add_item(cart_id, SIMPLE_SKU, qty=1.5)

    @pytest.mark.xfail(strict=True, reason=QTY_FINDING)
    @allure.severity(allure.severity_level.CRITICAL)
    @allure.title("A zero or negative quantity is rejected when adding")
    @pytest.mark.parametrize("qty", [0, -1])
    def test_non_positive_quantity_is_rejected_when_adding(
        self, guest_cart: GuestCartClient, cart_id: str, qty: int
    ) -> None:
        with pytest.raises(MagentoApiError):
            guest_cart.add_item(cart_id, SIMPLE_SKU, qty=qty)

    @pytest.mark.xfail(strict=True, reason=QTY_FINDING)
    @allure.severity(allure.severity_level.CRITICAL)
    @allure.title("Updating an item to quantity 0 is rejected, not turned into 1")
    def test_zero_quantity_is_rejected_when_updating(
        self, guest_cart: GuestCartClient, cart_id: str
    ) -> None:
        item = guest_cart.add_item(cart_id, SIMPLE_SKU, qty=3)

        with pytest.raises(MagentoApiError):
            guest_cart.update_item(cart_id, item.item_id, qty=0)


@allure.feature("Cart")
@allure.story("Cart access")
class TestCartAccess:
    @allure.severity(allure.severity_level.CRITICAL)
    @allure.title("A guest cart cannot be reached by its internal numeric id")
    def test_cart_is_not_reachable_by_internal_id(
        self, guest_cart: GuestCartClient, cart_id: str
    ) -> None:
        internal_id = guest_cart.get(cart_id).id

        with pytest.raises(MagentoApiError) as error:
            guest_cart.items(str(internal_id))

        assert error.value.status == 404

    @allure.severity(allure.severity_level.NORMAL)
    @allure.title("An unknown cart id is rejected")
    def test_unknown_cart_id_is_rejected(self, guest_cart: GuestCartClient) -> None:
        with pytest.raises(MagentoApiError, match="No such entity with cartId") as error:
            guest_cart.items(uuid.uuid4().hex)

        assert error.value.status == 404
