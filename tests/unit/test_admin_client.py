"""Unit tests for AdminClient behaviour that needs no store, using a scripted HTTP client."""

import json
from collections import deque
from typing import Any

import pytest
import requests
from pydantic import SecretStr

from magento_qa.api.admin import AdminClient
from magento_qa.api.errors import MagentoApiError
from magento_qa.api.http import HttpClient


def response(status: int, body: object) -> requests.Response:
    result = requests.Response()
    result.status_code = status
    result._content = json.dumps(body).encode()
    return result


class ScriptedHttp(HttpClient):
    """Answers requests from a script and records what was asked."""

    def __init__(self, *answers: requests.Response) -> None:
        super().__init__("http://shop.test/", timeout=1)
        self.answers = deque(answers)
        self.calls: list[tuple[str, str]] = []

    def request(
        self, method: str, path: str, *, redact_response: bool = False, **kwargs: Any
    ) -> requests.Response:
        self.calls.append((method, path))
        return self.answers.popleft()


def test_rule_is_deleted_when_its_coupon_cannot_be_created() -> None:
    http = ScriptedHttp(
        response(200, "token"),
        response(200, {"rule_id": 42, "name": "QA", "is_active": True, "discount_amount": 10}),
        response(400, {"message": "Coupon with the same code already exists."}),
        response(200, True),
    )
    admin = AdminClient(http, username="admin", password=SecretStr("secret"))

    with pytest.raises(MagentoApiError, match="already exists"):
        admin.create_coupon_rule("QA", code="DUPLICATE", percent_off=10)

    assert http.calls[-1] == ("DELETE", "rest/all/V1/salesRules/42")


def test_expired_token_is_renewed_once() -> None:
    http = ScriptedHttp(
        response(200, "old-token"),
        response(401, {"message": "The consumer isn't authorized to access %resources."}),
        response(200, "new-token"),
        response(200, {"items": []}),
    )
    admin = AdminClient(http, username="admin", password=SecretStr("secret"))

    result = admin.request("GET", "rest/V1/orders")

    assert result.status_code == 200
    assert [path for _, path in http.calls].count("rest/V1/integration/admin/token") == 2
