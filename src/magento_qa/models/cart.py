"""Cart, shipping and totals models of the checkout API."""

from decimal import Decimal

from pydantic import BaseModel


class CartItem(BaseModel):
    item_id: int
    sku: str
    name: str
    qty: Decimal
    price: Decimal


class ShippingMethod(BaseModel):
    carrier_code: str
    method_code: str
    amount: Decimal
    available: bool


class PaymentMethod(BaseModel):
    code: str
    title: str


class Totals(BaseModel):
    subtotal: Decimal
    shipping_amount: Decimal
    tax_amount: Decimal
    discount_amount: Decimal
    grand_total: Decimal
    quote_currency_code: str


class PaymentDetails(BaseModel):
    """What Magento returns once the shipping information is set."""

    payment_methods: list[PaymentMethod]
    totals: Totals
