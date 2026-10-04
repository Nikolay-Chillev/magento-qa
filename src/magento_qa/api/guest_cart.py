"""Guest checkout: cart, shipping and order placement without a customer account."""

from collections.abc import Sequence
from typing import Any

from magento_qa.api.errors import raise_for_magento_error
from magento_qa.api.http import HttpClient
from magento_qa.models.address import Address
from magento_qa.models.cart import (
    Cart,
    CartItem,
    PaymentDetails,
    ShippingMethod,
    Totals,
    VariantOption,
)


class GuestCartClient:
    """Steps of a guest checkout. Every method raises MagentoApiError on a non-2xx response."""

    def __init__(self, http: HttpClient) -> None:
        self.http = http

    def create(self) -> str:
        """Create an empty cart and return its masked id."""
        response = self.http.post("rest/V1/guest-carts")
        raise_for_magento_error(response)
        cart_id: str = response.json()
        return cart_id

    def get(self, cart_id: str) -> Cart:
        response = self.http.get(f"rest/V1/guest-carts/{cart_id}")
        raise_for_magento_error(response)
        return Cart.model_validate(response.json())

    def add_item(
        self,
        cart_id: str,
        sku: str,
        qty: float = 1,
        *,
        options: Sequence[VariantOption] = (),
    ) -> CartItem:
        """Add a product; ``options`` choose the variant of a configurable product."""
        item: dict[str, Any] = {"sku": sku, "qty": qty, "quote_id": cart_id}
        if options:
            item["product_option"] = {
                "extension_attributes": {
                    "configurable_item_options": [option.model_dump() for option in options]
                }
            }
        response = self.http.post(f"rest/V1/guest-carts/{cart_id}/items", json={"cartItem": item})
        raise_for_magento_error(response)
        return CartItem.model_validate(response.json())

    def update_item(self, cart_id: str, item_id: int, qty: float) -> CartItem:
        response = self.http.put(
            f"rest/V1/guest-carts/{cart_id}/items/{item_id}",
            json={"cartItem": {"qty": qty, "quote_id": cart_id}},
        )
        raise_for_magento_error(response)
        return CartItem.model_validate(response.json())

    def remove_item(self, cart_id: str, item_id: int) -> None:
        response = self.http.delete(f"rest/V1/guest-carts/{cart_id}/items/{item_id}")
        raise_for_magento_error(response)

    def items(self, cart_id: str) -> list[CartItem]:
        response = self.http.get(f"rest/V1/guest-carts/{cart_id}/items")
        raise_for_magento_error(response)
        return [CartItem.model_validate(item) for item in response.json()]

    def apply_coupon(self, cart_id: str, code: str) -> None:
        response = self.http.put(f"rest/V1/guest-carts/{cart_id}/coupons/{code}")
        raise_for_magento_error(response)

    def remove_coupon(self, cart_id: str) -> None:
        response = self.http.delete(f"rest/V1/guest-carts/{cart_id}/coupons")
        raise_for_magento_error(response)

    def totals(self, cart_id: str) -> Totals:
        response = self.http.get(f"rest/V1/guest-carts/{cart_id}/totals")
        raise_for_magento_error(response)
        return Totals.model_validate(response.json())

    def estimate_shipping(self, cart_id: str, address: Address) -> list[ShippingMethod]:
        response = self.http.post(
            f"rest/V1/guest-carts/{cart_id}/estimate-shipping-methods",
            json={"address": address.payload()},
        )
        raise_for_magento_error(response)
        return [ShippingMethod.model_validate(method) for method in response.json()]

    def set_shipping_information(
        self,
        cart_id: str,
        address: Address,
        *,
        carrier_code: str = "flatrate",
        method_code: str = "flatrate",
    ) -> PaymentDetails:
        """Set shipping and billing address (the same) and the shipping method."""
        response = self.http.post(
            f"rest/V1/guest-carts/{cart_id}/shipping-information",
            json={
                "addressInformation": {
                    "shipping_address": address.payload(),
                    "billing_address": address.payload(),
                    "shipping_carrier_code": carrier_code,
                    "shipping_method_code": method_code,
                }
            },
        )
        raise_for_magento_error(response)
        return PaymentDetails.model_validate(response.json())

    def place_order(
        self, cart_id: str, *, email: str, billing_address: Address, payment_method: str = "checkmo"
    ) -> int:
        """Pay and place the order; returns the order's entity id."""
        response = self.http.post(
            f"rest/V1/guest-carts/{cart_id}/payment-information",
            json={
                "email": email,
                "paymentMethod": {"method": payment_method},
                "billingAddress": billing_address.payload(),
            },
        )
        raise_for_magento_error(response)
        return int(response.json())
