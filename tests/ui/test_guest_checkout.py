"""Guest checkout in the browser: a shopper gets from a filled cart to a placed order.

The cart is filled by the test; the browser covers what only a browser can: the
checkout form, the oblast dropdown, the shipping and payment steps, the success page.
The back office and Mailpit then confirm that the order the shopper saw is real.
"""

import re
from collections.abc import Callable, Sequence

import allure
import pytest
from playwright.sync_api import Page, expect

from magento_qa.api.admin import AdminClient
from magento_qa.api.catalog import CatalogClient
from magento_qa.data.factories import bulgarian_address
from magento_qa.mail.mailpit import MailpitClient
from magento_qa.ui.cart_seed import SeedItem
from magento_qa.ui.pages import CheckoutPage

pytestmark = pytest.mark.ui

PRODUCT_SKU = "24-MB01"  # Joust Duffle Bag
REQUIRED_FIELDS = [
    "First Name",
    "Last Name",
    "Street Address: Line 1",
    "City",
    "Zip/Postal Code",
    "Phone Number",
]
REQUIRED_MESSAGE = "This is a required field."


@pytest.fixture
def checkout(
    page: Page, seed: Callable[[Sequence[SeedItem]], None], catalog: CatalogClient
) -> CheckoutPage:
    """The checkout of a guest with one product in the cart."""
    seed([SeedItem(catalog.product(PRODUCT_SKU).id)])
    return CheckoutPage(page).open()


@allure.feature("Checkout")
@allure.story("Guest checkout in the browser")
class TestGuestCheckoutInBrowser:
    @pytest.mark.email
    @allure.severity(allure.severity_level.BLOCKER)
    @allure.title("A guest with a Bulgarian address places an order and gets its number")
    def test_guest_places_an_order(
        self,
        checkout: CheckoutPage,
        bulgarian_region_ids: dict[str, int],
        admin: AdminClient,
        mailpit: MailpitClient,
    ) -> None:
        address = bulgarian_address(bulgarian_region_ids)
        assert address.email

        checkout.fill_shipping_address(address).choose_shipping().continue_to_payment()
        expect(checkout.payment_method).to_contain_text("Check / Money order")
        success = checkout.place_order()

        expect(success.heading).to_have_text("Thank you for your purchase!")
        number = success.order_number
        with allure.step(f"The back office has order {number} for this guest"):
            order = admin.find_order(number)
            assert order.customer_email == address.email
            assert order.customer_is_guest
            assert [item.sku for item in order.items] == [PRODUCT_SKU]
            assert (order.billing_address.country_id, order.billing_address.region_id) == (
                "BG",
                address.region_id,
            )
        with allure.step(f"The confirmation email names order {number}"):
            email = mailpit.wait_for_message(to=address.email, subject="order confirmation")
            assert f"#{number}" in email.html

    @allure.severity(allure.severity_level.NORMAL)
    @allure.title("Empty required fields are flagged, and announced to screen readers")
    def test_required_fields_are_flagged(self, checkout: CheckoutPage) -> None:
        checkout.field("Country").select_option("BG")
        checkout.choose_shipping()

        checkout.next_button.click()

        for label in REQUIRED_FIELDS:
            field = checkout.field(label)
            expect(field).to_have_attribute("aria-invalid", "true")
            expect(field).to_have_accessible_description(REQUIRED_MESSAGE)
        expect(checkout.region).to_have_accessible_description(REQUIRED_MESSAGE)
        expect(checkout.email).to_have_accessible_description(REQUIRED_MESSAGE)
        expect(checkout.page).to_have_url(re.compile(r"#shipping$"))
        expect(checkout.payment_method).to_be_hidden()
