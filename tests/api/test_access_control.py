"""Access rules of the REST API: each customer reaches only their own data.

Every test registers its own customers: "you", signed in with your token, and
"other", whose data must stay out of your reach.
"""

from collections.abc import Callable
from dataclasses import dataclass

import allure
import pytest

from magento_qa.api.customers import CustomerClient, SignedInCustomer
from magento_qa.api.errors import MagentoApiError
from magento_qa.api.guest_cart import GuestCartClient
from magento_qa.api.http import HttpClient
from magento_qa.data.factories import bulgarian_address, new_customer

pytestmark = pytest.mark.api

PRODUCT_SKU = "24-MB01"  # Joust Duffle Bag, a simple product


@dataclass(frozen=True)
class Account:
    id: int
    session: SignedInCustomer


@pytest.fixture
def register(
    customers: CustomerClient, bulgarian_region_ids: dict[str, int]
) -> Callable[[], Account]:
    """Register a customer with a default address and sign them in."""

    def make() -> Account:
        new = new_customer()
        address = bulgarian_address(bulgarian_region_ids).model_copy(
            update={"email": None, "region_code": None}
        )
        created = customers.register(
            new,
            addresses=[{**address.payload(), "default_shipping": True, "default_billing": True}],
        )
        return Account(id=created.id, session=customers.sign_in(new.email, new.password))

    return make


@pytest.fixture
def you(register: Callable[[], Account]) -> Account:
    return register()


@pytest.fixture
def other(register: Callable[[], Account]) -> Account:
    return register()


@allure.feature("Customer accounts")
@allure.story("Access control")
class TestOtherCustomersData:
    @allure.severity(allure.severity_level.CRITICAL)
    @allure.title("Saving your profile with another customer's id changes only your own")
    def test_profile_update_ignores_another_id(self, you: Account, other: Account) -> None:
        before = other.session.profile()

        saved = you.session.update_profile(id=other.id, firstname="Changed")

        assert saved.id == you.id
        assert you.session.profile().firstname == "Changed"
        assert other.session.profile() == before

    @allure.severity(allure.severity_level.CRITICAL)
    @allure.title("Another customer's address cannot be edited through your profile")
    def test_cannot_edit_another_address(self, you: Account, other: Account) -> None:
        their_address = other.session.profile().addresses[0]

        # Refused, though with a misleading message ("A customer with the same email
        # address already exists"), so only the status is checked.
        with pytest.raises(MagentoApiError) as error:
            you.session.update_profile(
                addresses=[{"id": their_address.id, "street": ["Changed"], "city": "Changed"}]
            )

        assert error.value.status == 400
        assert other.session.profile().addresses == [their_address]

    @allure.severity(allure.severity_level.CRITICAL)
    @allure.title("A cart item sent with another customer's cart id lands in your own cart")
    def test_item_goes_to_your_own_cart(self, you: Account, other: Account) -> None:
        their_cart = other.session.create_cart()
        your_cart = you.session.create_cart()

        item = you.session.add_to_cart(PRODUCT_SKU, quote_id=their_cart)

        assert item.sku == PRODUCT_SKU
        assert you.session.cart().id == your_cart
        assert you.session.cart().items_count == 1
        assert other.session.cart().items_count == 0

    @allure.severity(allure.severity_level.CRITICAL)
    @allure.title("Another customer's cart cannot be read by its id")
    def test_cannot_read_another_cart(self, you: Account, other: Account) -> None:
        their_cart = other.session.create_cart()

        response = you.session.request("GET", f"rest/V1/carts/{their_cart}")

        assert response.status_code == 401


# Back-office endpoints. Magento checks the caller's rights before it looks the
# record up, so the ids do not need to exist.
ADMIN_ONLY = [
    pytest.param("GET", "rest/V1/customers/1", None, id="read a customer"),
    pytest.param("GET", "rest/V1/customers/search", None, id="search customers"),
    pytest.param("GET", "rest/V1/orders/1", None, id="read an order"),
    pytest.param("GET", "rest/V1/orders", None, id="search orders"),
    pytest.param("GET", "rest/V1/carts/search", None, id="search carts"),
    pytest.param("GET", "rest/V1/invoices", None, id="search invoices"),
    pytest.param(
        "PUT", f"rest/V1/products/{PRODUCT_SKU}", {"product": {"price": 1}}, id="change a price"
    ),
    pytest.param("POST", "rest/V1/salesRules", {"rule": {"name": "QA"}}, id="create a promotion"),
    pytest.param(
        "POST",
        "rest/V1/coupons/generate",
        {"couponSpec": {"rule_id": 1, "qty": 1}},
        id="generate coupons",
    ),
]
SEARCH_ALL = {"searchCriteria[pageSize]": 1}


@allure.feature("Customer accounts")
@allure.story("Access control")
class TestBackOfficeEndpoints:
    @pytest.mark.parametrize(("method", "path", "body"), ADMIN_ONLY)
    @allure.severity(allure.severity_level.CRITICAL)
    @allure.title("Back-office endpoints refuse anonymous callers")
    def test_refuse_anonymous_callers(
        self, store_http: HttpClient, method: str, path: str, body: dict[str, object] | None
    ) -> None:
        response = store_http.request(method, path, params=SEARCH_ALL, json=body)

        assert response.status_code == 401

    @pytest.mark.parametrize(("method", "path", "body"), ADMIN_ONLY)
    @allure.severity(allure.severity_level.CRITICAL)
    @allure.title("Back-office endpoints refuse customer tokens")
    def test_refuse_customer_tokens(
        self, you: Account, method: str, path: str, body: dict[str, object] | None
    ) -> None:
        response = you.session.request(method, path, params=SEARCH_ALL, json=body)

        assert response.status_code == 401


@allure.feature("Customer accounts")
@allure.story("Access control")
class TestGuestCarts:
    @allure.severity(allure.severity_level.CRITICAL)
    @allure.title("Guest endpoints do not open carts by their numeric id")
    def test_numeric_id_does_not_open_a_cart(
        self, guest_cart: GuestCartClient, other: Account
    ) -> None:
        # Guest carts are reached only by a random 32-character id, so cart numbers,
        # which are easy to guess, open nothing.
        their_cart = other.session.create_cart()

        with pytest.raises(MagentoApiError) as error:
            guest_cart.get(str(their_cart))

        assert error.value.status == 404

    @allure.severity(allure.severity_level.CRITICAL)
    @allure.title("A guest cart taken over at sign-in belongs to that customer only")
    def test_taken_over_cart_belongs_to_the_caller(
        self, guest_cart: GuestCartClient, you: Account, other: Account
    ) -> None:
        cart_id = guest_cart.create()
        guest_cart.add_item(cart_id, PRODUCT_SKU)

        # The customer id in the request is ignored: the cart goes to the token's owner.
        you.session.take_over_guest_cart(cart_id, customerId=other.id)

        assert you.session.cart().items_count == 1
        with pytest.raises(MagentoApiError) as no_cart:
            other.session.cart()
        assert no_cart.value.status == 404
        with pytest.raises(MagentoApiError) as old_id:
            guest_cart.get(cart_id)
        assert old_id.value.status == 404
