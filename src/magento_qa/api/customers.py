"""Customer accounts through the REST API, as headless storefronts and mobile apps use it."""

from typing import Any

import requests

from magento_qa.api.errors import raise_for_magento_error
from magento_qa.api.http import HttpClient
from magento_qa.models.address import Address
from magento_qa.models.cart import Cart, CartItem
from magento_qa.models.customer import Customer, NewCustomer


class CustomerClient:
    def __init__(self, http: HttpClient) -> None:
        self.http = http

    def register(self, customer: NewCustomer, **fields: Any) -> Customer:
        """Self-registration, open to anyone; ``fields`` are extra customer attributes."""
        response = self.http.post("rest/V1/customers", json=customer.payload(**fields))
        raise_for_magento_error(response)
        return Customer.model_validate(response.json())

    def token(self, email: str, password: str) -> str:
        """Sign in; the token authorises the customer's own ``/me`` endpoints."""
        response = self.http.post(
            "rest/V1/integration/customer/token",
            json={"username": email, "password": password},
            redact_response=True,
        )
        raise_for_magento_error(response)
        token: str = response.json()
        return token

    def sign_in(self, email: str, password: str) -> "SignedInCustomer":
        return SignedInCustomer(self.http, self.token(email, password))

    def me(self, token: str) -> Customer:
        response = self.http.get(
            "rest/V1/customers/me", headers={"Authorization": f"Bearer {token}"}
        )
        raise_for_magento_error(response)
        return Customer.model_validate(response.json())

    def request_password_reset(self, email: str) -> None:
        """Send the "Reset your password" email, as the "Forgot Your Password?" form does."""
        response = self.http.put(
            "rest/V1/customers/password",
            json={"email": email, "template": "email_reset", "websiteId": 1},
        )
        raise_for_magento_error(response)

    def reset_password(self, email: str, reset_token: str, new_password: str) -> None:
        """Set a new password with the token from the reset email."""
        response = self.http.post(
            "rest/V1/customers/resetPassword",
            json={"email": email, "resetToken": reset_token, "newPassword": new_password},
        )
        raise_for_magento_error(response)


class SignedInCustomer:
    """One customer's own endpoints (``/me``, ``/mine``), called with their token."""

    def __init__(self, http: HttpClient, token: str) -> None:
        self.http = http
        self._headers = {"Authorization": f"Bearer {token}"}

    def request(self, method: str, path: str, **kwargs: Any) -> requests.Response:
        """Any call with this customer's token; for checking what the token may reach."""
        return self.http.request(method, path, headers=self._headers, **kwargs)

    def profile(self) -> Customer:
        response = self.request("GET", "rest/V1/customers/me")
        raise_for_magento_error(response)
        return Customer.model_validate(response.json())

    def update_profile(self, **fields: Any) -> Customer:
        """Save the profile with ``fields`` changed, the way the account page does."""
        current = self.profile().model_dump(exclude={"addresses"})
        response = self.request(
            "PUT", "rest/V1/customers/me", json={"customer": {**current, **fields}}
        )
        raise_for_magento_error(response)
        return Customer.model_validate(response.json())

    def create_cart(self) -> int:
        """The customer's active cart, created if there is none; returns its id."""
        response = self.request("POST", "rest/V1/carts/mine")
        raise_for_magento_error(response)
        return int(response.json())

    def cart(self) -> Cart:
        response = self.request("GET", "rest/V1/carts/mine")
        raise_for_magento_error(response)
        return Cart.model_validate(response.json())

    def add_to_cart(self, sku: str, qty: float = 1, **item: Any) -> CartItem:
        """Add a product to the customer's cart; ``item`` adds fields to the cart item."""
        response = self.request(
            "POST", "rest/V1/carts/mine/items", json={"cartItem": {"sku": sku, "qty": qty, **item}}
        )
        raise_for_magento_error(response)
        return CartItem.model_validate(response.json())

    def take_over_guest_cart(self, cart_id: str, **fields: Any) -> None:
        """Make a guest cart (masked id) the customer's own, as signing in at checkout does."""
        response = self.request(
            "PUT", f"rest/V1/guest-carts/{cart_id}", json={"storeId": 1, **fields}
        )
        raise_for_magento_error(response)

    def place_order(self, sku: str, address: Address) -> int:
        """Buy one unit of ``sku`` with flat-rate shipping and check / money order."""
        self.create_cart()
        self.add_to_cart(sku)
        response = self.request(
            "POST",
            "rest/V1/carts/mine/shipping-information",
            json={
                "addressInformation": {
                    "shipping_address": address.payload(),
                    "billing_address": address.payload(),
                    "shipping_carrier_code": "flatrate",
                    "shipping_method_code": "flatrate",
                }
            },
        )
        raise_for_magento_error(response)
        response = self.request(
            "PUT", "rest/V1/carts/mine/order", json={"paymentMethod": {"method": "checkmo"}}
        )
        raise_for_magento_error(response)
        return int(response.json())
