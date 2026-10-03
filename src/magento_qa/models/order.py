"""Order as returned by the admin REST API."""

from decimal import Decimal

from pydantic import BaseModel


class OrderItem(BaseModel):
    sku: str
    name: str
    qty_ordered: Decimal
    price: Decimal


class OrderAddress(BaseModel):
    firstname: str
    lastname: str
    street: list[str]
    city: str
    postcode: str
    country_id: str
    telephone: str
    region_id: int | None = None
    region_code: str | None = None


class OrderPayment(BaseModel):
    method: str


class Order(BaseModel):
    entity_id: int
    increment_id: str
    state: str
    status: str
    customer_email: str
    customer_is_guest: bool
    order_currency_code: str
    subtotal: Decimal
    shipping_amount: Decimal
    tax_amount: Decimal
    discount_amount: Decimal
    grand_total: Decimal
    items: list[OrderItem]
    billing_address: OrderAddress
    payment: OrderPayment
