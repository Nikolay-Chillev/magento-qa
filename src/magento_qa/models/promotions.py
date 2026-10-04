"""Cart price rules and coupons from the admin REST API."""

from datetime import date

from pydantic import BaseModel


class CartRule(BaseModel):
    rule_id: int
    name: str
    is_active: bool
    discount_amount: float
    to_date: date | None = None


class Coupon(BaseModel):
    coupon_id: int
    rule_id: int
    code: str
    times_used: int | None = None  # null on a coupon that was just created
