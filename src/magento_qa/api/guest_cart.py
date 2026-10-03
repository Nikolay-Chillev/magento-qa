"""Guest checkout: cart, shipping and order placement without a customer account."""

from magento_qa.api.errors import raise_for_magento_error
from magento_qa.api.http import HttpClient
from magento_qa.models.address import Address
from magento_qa.models.cart import CartItem, PaymentDetails, ShippingMethod


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

    def add_item(self, cart_id: str, sku: str, qty: int = 1) -> CartItem:
        response = self.http.post(
            f"rest/V1/guest-carts/{cart_id}/items",
            json={"cartItem": {"sku": sku, "qty": qty, "quote_id": cart_id}},
        )
        raise_for_magento_error(response)
        return CartItem.model_validate(response.json())

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
