"""Unit tests for turning Magento error responses into readable exceptions."""

import json

import pytest
import requests

from magento_qa.api.errors import MagentoApiError, raise_for_magento_error, render_message


@pytest.mark.parametrize(
    ("message", "parameters", "expected"),
    [
        pytest.param(
            "No such entity with %fieldName = %fieldValue",
            {"fieldName": "cartId", "fieldValue": "abc"},
            "No such entity with cartId = abc",
            id="named",
        ),
        pytest.param(
            'The "%1" value is invalid for "%2".',
            ["0", "qty"],
            'The "0" value is invalid for "qty".',
            id="positional",
        ),
        pytest.param("Nothing to fill", None, "Nothing to fill", id="no-parameters"),
        pytest.param("Keeps %unknown as is", {"other": 1}, "Keeps %unknown as is", id="unknown"),
    ],
)
def test_placeholders_are_filled(
    message: str, parameters: dict[str, str] | list[str] | None, expected: str
) -> None:
    assert render_message(message, parameters) == expected


def make_response(status: int, body: bytes) -> requests.Response:
    response = requests.Response()
    response.status_code = status
    response._content = body
    return response


def test_error_response_raises_with_rendered_message() -> None:
    body = {
        "message": "The consumer isn't authorized to access %resources.",
        "parameters": {"resources": "Magento_Sales::actions_view"},
    }
    response = make_response(401, json.dumps(body).encode())

    with pytest.raises(MagentoApiError) as error:
        raise_for_magento_error(response)

    assert error.value.status == 401
    assert error.value.message == (
        "The consumer isn't authorized to access Magento_Sales::actions_view."
    )


def test_non_json_error_keeps_the_text() -> None:
    with pytest.raises(MagentoApiError, match="HTTP 502: Bad Gateway"):
        raise_for_magento_error(make_response(502, b"Bad Gateway"))


def test_success_does_not_raise() -> None:
    raise_for_magento_error(make_response(200, b'"ok"'))
