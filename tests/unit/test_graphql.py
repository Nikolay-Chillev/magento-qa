"""Unit tests for the GraphQL client's handling of answers, using a scripted HTTP client."""

import json
from typing import Any

import pytest
import requests

from magento_qa.api.graphql import GraphQLClient, GraphQLError
from magento_qa.api.http import HttpClient


def response(status: int, body: str) -> requests.Response:
    result = requests.Response()
    result.status_code = status
    result._content = body.encode()
    return result


class ScriptedHttp(HttpClient):
    """Answers every request with one response and records the headers sent."""

    def __init__(self, answer: requests.Response) -> None:
        super().__init__("http://shop.test/", timeout=1)
        self.answer = answer
        self.headers: dict[str, str] = {}

    def request(
        self, method: str, path: str, *, redact_response: bool = False, **kwargs: Any
    ) -> requests.Response:
        self.headers = kwargs.get("headers", {})
        return self.answer


AUTHORIZATION_ERROR = {
    "message": "The current customer isn't authorized.",
    "extensions": {"category": "graphql-authorization"},
}


def test_data_is_returned() -> None:
    http = ScriptedHttp(response(200, json.dumps({"data": {"cart": {"total_quantity": 2}}})))

    assert GraphQLClient(http).execute("{ cart }") == {"cart": {"total_quantity": 2}}


def test_errors_with_http_200_are_raised() -> None:
    body = {"errors": [AUTHORIZATION_ERROR], "data": {"customer": None}}
    http = ScriptedHttp(response(200, json.dumps(body)))

    with pytest.raises(GraphQLError) as error:
        GraphQLClient(http).execute("{ customer { email } }")

    assert error.value.messages == ["The current customer isn't authorized."]
    assert error.value.categories == ["graphql-authorization"]


def test_syntax_errors_with_http_400_are_graphql_errors() -> None:
    body = {"errors": [{"message": "Syntax Error: Expected Name, found {"}]}
    http = ScriptedHttp(response(400, json.dumps(body)))

    with pytest.raises(GraphQLError, match="Syntax Error"):
        GraphQLClient(http).execute("{ products(search: ")


def test_an_error_page_raises_an_http_error() -> None:
    http = ScriptedHttp(response(502, "<html>Bad Gateway</html>"))

    with pytest.raises(requests.HTTPError):
        GraphQLClient(http).execute("{ products }")


def test_token_is_sent_only_by_the_client_that_has_it() -> None:
    http = ScriptedHttp(response(200, json.dumps({"data": {}})))
    anonymous = GraphQLClient(http)

    anonymous.with_token("abc").execute("{ customer { email } }")
    assert http.headers == {"Authorization": "Bearer abc"}

    anonymous.execute("{ products }")
    assert http.headers == {}
