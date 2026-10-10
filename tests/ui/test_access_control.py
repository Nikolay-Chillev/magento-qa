"""Access rules in the storefront: a signed-in customer sees only their own orders
and addresses, even when they type another customer's ids into the address bar.

The other customer and their order are created through the API.
"""

import re
from dataclasses import dataclass

import allure
import pytest
from playwright.sync_api import BrowserContext, Page, expect

from magento_qa.api.admin import AdminClient
from magento_qa.api.customers import CustomerClient
from magento_qa.data.factories import bulgarian_address, new_customer
from magento_qa.models.customer import NewCustomer
from magento_qa.ui.pages import AccountPage, LoginPage

pytestmark = pytest.mark.ui

ORDER_HISTORY = re.compile(r"/sales/order/history/")


@dataclass(frozen=True)
class OtherCustomer:
    street: str
    address_id: int
    order_id: int
    order_number: str


@pytest.fixture
def other(
    customers: CustomerClient, admin: AdminClient, bulgarian_region_ids: dict[str, int]
) -> OtherCustomer:
    new = new_customer()
    address = bulgarian_address(bulgarian_region_ids, email=new.email)
    customers.register(
        new,
        addresses=[
            {
                **address.model_copy(update={"email": None, "region_code": None}).payload(),
                "default_shipping": True,
                "default_billing": True,
            }
        ],
    )
    session = customers.sign_in(new.email, new.password)
    order_id = session.place_order("24-MB01", address)
    return OtherCustomer(
        street=address.street[0],
        address_id=session.profile().addresses[0].id,
        order_id=order_id,
        order_number=admin.get_order(order_id).increment_id,
    )


@pytest.fixture
def you(page: Page, customers: CustomerClient) -> NewCustomer:
    """A customer signed in in this test's browser."""
    customer = new_customer()
    customers.register(customer)
    LoginPage(page).open().sign_in(customer.email, customer.password)
    expect(AccountPage(page).heading).to_have_text("My Account")
    return customer


@allure.feature("Customer accounts")
@allure.story("Access control")
class TestOtherCustomersDataInTheStorefront:
    @pytest.mark.parametrize("page_name", ["view", "print"])
    @allure.severity(allure.severity_level.CRITICAL)
    @allure.title("Another customer's order cannot be opened by its id ({page_name})")
    def test_other_order_is_not_shown(
        self, page: Page, you: NewCustomer, other: OtherCustomer, page_name: str
    ) -> None:
        page.goto(f"sales/order/{page_name}/order_id/{other.order_id}/")

        expect(page).to_have_url(ORDER_HISTORY)
        expect(page.get_by_text(other.order_number)).to_have_count(0)

    @allure.severity(allure.severity_level.CRITICAL)
    @allure.title("Reordering another customer's order adds nothing to your cart")
    def test_other_order_cannot_be_reordered(
        self, page: Page, context: BrowserContext, you: NewCustomer, other: OtherCustomer
    ) -> None:
        form_key = next(c["value"] for c in context.cookies() if c["name"] == "form_key")

        response = context.request.post(
            f"sales/order/reorder/order_id/{other.order_id}/",
            form={"form_key": form_key},
            max_redirects=0,
        )

        assert response.status == 302
        assert ORDER_HISTORY.search(response.headers["location"])
        page.goto("checkout/cart/")
        expect(page.get_by_role("heading", level=1)).to_have_text("Shopping Cart")
        expect(page.get_by_text("You have no items in your shopping cart.")).to_be_visible()

    @allure.severity(allure.severity_level.CRITICAL)
    @allure.title("Another customer's address cannot be opened for editing by its id")
    def test_other_address_is_not_shown(
        self, page: Page, you: NewCustomer, other: OtherCustomer
    ) -> None:
        page.goto(f"customer/address/edit/id/{other.address_id}/")

        expect(page.get_by_role("heading", level=1)).to_be_visible()
        expect(page.get_by_text(other.street)).to_have_count(0)
        expect(page.get_by_label("Street Address: Line 1", exact=True)).not_to_have_value(
            other.street
        )
