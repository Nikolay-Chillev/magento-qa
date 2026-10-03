"""Fixtures for REST API tests."""

import pytest

from magento_qa.api.guest_cart import GuestCartClient
from magento_qa.api.http import HttpClient


@pytest.fixture
def guest_cart(store_http: HttpClient) -> GuestCartClient:
    return GuestCartClient(store_http)
