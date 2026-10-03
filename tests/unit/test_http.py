"""Unit tests for the HTTP client helpers; no network involved."""

import json

import pytest
import requests

from magento_qa.api.http import MASK, HttpClient, format_exchange


@pytest.mark.parametrize("base_url", ["http://shop.test", "http://shop.test/"])
@pytest.mark.parametrize("path", ["rest/V1/carts", "/rest/V1/carts"])
def test_paths_resolve_against_the_base_url(base_url: str, path: str) -> None:
    client = HttpClient(base_url, timeout=1)

    assert client.url(path) == "http://shop.test/rest/V1/carts"


def make_response(
    request_body: dict[str, object], *, request_headers: dict[str, str]
) -> requests.Response:
    response = requests.Response()
    response.request = requests.Request(
        "POST",
        "http://shop.test/rest/V1/integration/customer/token",
        json=request_body,
        headers=request_headers,
    ).prepare()
    response.status_code = 200
    response.reason = "OK"
    response.headers["Set-Cookie"] = "PHPSESSID=abc"
    response._content = json.dumps({"customer": {"password_hash": "x", "email": "a@b.c"}}).encode()
    return response


def test_exchange_masks_credentials_in_headers_and_bodies() -> None:
    response = make_response(
        {"username": "a@b.c", "password": "s3cret"},
        request_headers={"Authorization": "Bearer t0ken"},
    )

    text = format_exchange(response)

    assert "s3cret" not in text
    assert "t0ken" not in text
    assert "PHPSESSID" not in text
    assert f'"password": "{MASK}"' in text
    assert f'"password_hash": "{MASK}"' in text
    assert '"email": "a@b.c"' in text
    assert text.startswith("POST http://shop.test/rest/V1/integration/customer/token")
