"""Catalog data from the admin REST API: variants of configurable products and stock."""

from decimal import Decimal

from pydantic import BaseModel


class OptionValue(BaseModel):
    value_index: int


class ConfigurableAttribute(BaseModel):
    """An attribute a configurable product varies by, e.g. Color or Size."""

    attribute_id: int
    label: str
    values: list[OptionValue]


class AttributeOption(BaseModel):
    label: str
    value: str


class StockItem(BaseModel):
    qty: Decimal
    is_in_stock: bool
