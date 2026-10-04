"""Cart, shipping and totals models of the checkout API."""

from decimal import Decimal

from pydantic import BaseModel


class VariantOption(BaseModel):
    """One chosen option of a configurable product: attribute id and option value id."""

    option_id: int
    option_value: int


class _ProductOptionAttributes(BaseModel):
    configurable_item_options: list[VariantOption] = []


class _ProductOption(BaseModel):
    extension_attributes: _ProductOptionAttributes = _ProductOptionAttributes()


class CartItem(BaseModel):
    item_id: int
    sku: str
    name: str
    qty: Decimal
    price: Decimal
    product_type: str
    product_option: _ProductOption | None = None

    @property
    def variant_options(self) -> list[VariantOption]:
        """Options chosen for a configurable product; empty for simple products."""
        if self.product_option is None:
            return []
        return self.product_option.extension_attributes.configurable_item_options


class Cart(BaseModel):
    id: int
    items_count: int
    is_active: bool


class TotalsItem(BaseModel):
    item_id: int
    qty: Decimal
    price: Decimal
    row_total: Decimal


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
    items_qty: Decimal | None = None
    items: list[TotalsItem] = []
    coupon_code: str | None = None


class PaymentDetails(BaseModel):
    """What Magento returns once the shipping information is set."""

    payment_methods: list[PaymentMethod]
    totals: Totals
