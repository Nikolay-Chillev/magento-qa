"""Bulgarian delivery addresses and VAT through the REST API.

Every one of the 28 oblasts must work as a delivery region, incomplete addresses
must be refused, and Bulgarian shoppers must pay 20% VAT on taxable goods. The VAT
rule is created by the environment setup (see the README).
"""

from collections.abc import Callable
from decimal import ROUND_HALF_UP, Decimal

import allure
import pytest
from bg_test_data import list_oblasts

from magento_qa.api.admin import AdminClient
from magento_qa.api.errors import MagentoApiError
from magento_qa.api.guest_cart import GuestCartClient
from magento_qa.data.factories import bulgarian_address, unique_email
from magento_qa.models.address import Address
from magento_qa.models.cart import VariantOption

pytestmark = pytest.mark.api

BAG_SKU = "24-MB01"  # Joust Duffle Bag (no tax class, see finding #39)
TEE_SKU = "WS12"  # Radiant Tee, taxable goods
VAT_RATE = Decimal("0.20")
OBLAST_CODES = [oblast["code"] for oblast in list_oblasts()]
REQUIRED_FIELDS = {
    "street": "Street Address",
    "city": "City",
    "postcode": "Zip/Postal Code",
    "telephone": "Phone Number",
}


def cents(amount: Decimal) -> Decimal:
    return amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


@pytest.fixture
def cart_with(guest_cart: GuestCartClient) -> Callable[..., str]:
    """A new guest cart holding ``qty`` of ``sku`` (with variant ``options``)."""

    def make(sku: str, qty: int = 1, options: list[VariantOption] | None = None) -> str:
        cart_id = guest_cart.create()
        guest_cart.add_item(cart_id, sku, qty=qty, options=options or [])
        return cart_id

    return make


@pytest.fixture(scope="module")
def blue_xs_tee(admin: AdminClient) -> list[VariantOption]:
    return admin.variant_options(TEE_SKU, {"Color": "Blue", "Size": "XS"})


@allure.feature("Checkout")
@allure.story("Bulgarian addresses")
class TestBulgarianOblasts:
    @allure.severity(allure.severity_level.CRITICAL)
    @allure.title("The store and the test data know the same 28 oblasts")
    def test_store_knows_every_oblast(self, bulgarian_region_ids: dict[str, int]) -> None:
        assert sorted(bulgarian_region_ids) == sorted(OBLAST_CODES)
        assert len(OBLAST_CODES) == 28

    @allure.severity(allure.severity_level.CRITICAL)
    @allure.title("An order can be delivered to oblast {oblast_code}")
    @pytest.mark.parametrize("oblast_code", OBLAST_CODES)
    def test_order_ships_to_every_oblast(
        self,
        guest_cart: GuestCartClient,
        cart_with: Callable[..., str],
        admin: AdminClient,
        bulgarian_region_ids: dict[str, int],
        oblast_code: str,
    ) -> None:
        cart_id = cart_with(BAG_SKU)
        address = bulgarian_address(bulgarian_region_ids, oblast_code=oblast_code)
        assert address.email
        guest_cart.set_shipping_information(cart_id, address)

        order_id = guest_cart.place_order(cart_id, email=address.email, billing_address=address)

        billing = admin.get_order(order_id).billing_address
        assert (billing.region_id, billing.city, billing.postcode) == (
            bulgarian_region_ids[oblast_code],
            address.city,
            address.postcode,
        )


@allure.feature("Checkout")
@allure.story("Bulgarian addresses")
class TestRequiredAddressFields:
    @allure.severity(allure.severity_level.NORMAL)
    @allure.title("An address without {field} is refused at the shipping step")
    @pytest.mark.parametrize("field", list(REQUIRED_FIELDS))
    def test_incomplete_address_is_refused(
        self,
        guest_cart: GuestCartClient,
        cart_with: Callable[..., str],
        bulgarian_region_ids: dict[str, int],
        field: str,
    ) -> None:
        empty: str | list[str] = [""] if field == "street" else ""
        address = bulgarian_address(bulgarian_region_ids).model_copy(update={field: empty})

        with pytest.raises(
            MagentoApiError, match=f'"{REQUIRED_FIELDS[field]}" is a required value'
        ):
            guest_cart.set_shipping_information(cart_with(BAG_SKU), address)


@allure.feature("Checkout")
@allure.story("VAT")
class TestVat:
    @allure.severity(allure.severity_level.BLOCKER)
    @allure.title("A Bulgarian order is charged 20% VAT on taxable goods")
    def test_bulgarian_order_is_charged_20_percent_vat(
        self,
        guest_cart: GuestCartClient,
        cart_with: Callable[..., str],
        admin: AdminClient,
        bulgarian_region_ids: dict[str, int],
        blue_xs_tee: list[VariantOption],
    ) -> None:
        cart_id = cart_with(TEE_SKU, qty=2, options=blue_xs_tee)
        address = bulgarian_address(bulgarian_region_ids)
        assert address.email

        totals = guest_cart.set_shipping_information(cart_id, address).totals

        # Shipping is not taxed and discounts come off before tax (Magento defaults).
        assert totals.tax_amount == cents((totals.subtotal + totals.discount_amount) * VAT_RATE)
        assert totals.tax_amount > 0
        assert totals.grand_total == (
            totals.subtotal + totals.shipping_amount + totals.tax_amount + totals.discount_amount
        )
        order_id = guest_cart.place_order(cart_id, email=address.email, billing_address=address)
        order = admin.get_order(order_id)
        assert (order.tax_amount, order.grand_total) == (totals.tax_amount, totals.grand_total)

    @allure.severity(allure.severity_level.NORMAL)
    @allure.title("Bulgarian VAT is not charged on a delivery outside Bulgaria")
    def test_vat_is_not_charged_outside_bulgaria(
        self,
        guest_cart: GuestCartClient,
        cart_with: Callable[..., str],
        blue_xs_tee: list[VariantOption],
    ) -> None:
        amsterdam = Address(
            firstname="Jan",
            lastname="Jansen",
            street=["Damrak 1"],
            city="Amsterdam",
            postcode="1012 LG",
            country_id="NL",
            telephone="+31 20 123 4567",
            email=unique_email(),
        )

        totals = guest_cart.set_shipping_information(
            cart_with(TEE_SKU, options=blue_xs_tee), amsterdam
        ).totals

        assert totals.tax_amount == 0

    @pytest.mark.xfail(strict=True, reason="Finding #39: five sample products have no tax class")
    @allure.severity(allure.severity_level.CRITICAL)
    @allure.title("Every product in the catalog has a tax class")
    def test_every_product_has_a_tax_class(self, admin: AdminClient) -> None:
        assert admin.skus_without_tax_class() == []
