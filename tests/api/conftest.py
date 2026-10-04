"""Fixtures for REST API tests."""

import uuid
from collections.abc import Callable, Generator
from datetime import date

import pytest

from magento_qa.api.admin import AdminClient
from magento_qa.api.guest_cart import GuestCartClient
from magento_qa.api.http import HttpClient
from magento_qa.models.promotions import Coupon


@pytest.fixture
def guest_cart(store_http: HttpClient) -> GuestCartClient:
    return GuestCartClient(store_http)


@pytest.fixture
def make_coupon(admin: AdminClient) -> Generator[Callable[..., Coupon]]:
    """Create percentage-off coupons with unique codes; their rules are deleted afterwards."""
    rule_ids: list[int] = []

    def make(
        *, percent_off: float = 10, to_date: date | None = None, uses_per_coupon: int = 0
    ) -> Coupon:
        code = f"QA-{uuid.uuid4().hex[:10].upper()}"
        rule, coupon = admin.create_coupon_rule(
            f"QA test coupon {code}",
            code=code,
            percent_off=percent_off,
            to_date=to_date,
            uses_per_coupon=uses_per_coupon,
        )
        rule_ids.append(rule.rule_id)
        return coupon

    yield make
    for rule_id in rule_ids:
        admin.delete_cart_rule(rule_id)
