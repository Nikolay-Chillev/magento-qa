"""Smoke tests: every service the suite depends on answers as expected."""

import pytest

from magento_qa.api.http import HttpClient
from magento_qa.mail.mailpit import MailpitClient
from magento_qa.readiness import CATALOG_SEARCH_QUERY

pytestmark = pytest.mark.smoke


def test_storefront_home_page_loads(store_http: HttpClient) -> None:
    """The Luma storefront renders its home page."""
    response = store_http.get("/")

    assert response.status_code == 200
    assert "<title>Home Page</title>" in response.text


def test_rest_api_reports_euro_as_store_currency(store_http: HttpClient) -> None:
    """The anonymous REST API answers; the store sells in EUR, like a Bulgarian shop since 2026."""
    response = store_http.get("rest/V1/directory/currency")

    assert response.status_code == 200
    currency = response.json()
    assert currency["base_currency_code"] == "EUR"
    assert currency["available_currency_codes"] == ["EUR"]


def test_graphql_catalog_search_returns_products(store_http: HttpClient) -> None:
    """GraphQL search is served by Elasticsearch, so results prove the search stack works."""
    response = store_http.post("graphql", json={"query": CATALOG_SEARCH_QUERY})

    assert response.status_code == 200
    body = response.json()
    assert "errors" not in body
    assert body["data"]["products"]["total_count"] > 0


def test_mailpit_api_is_available(mailpit: MailpitClient) -> None:
    """Mailpit answers, so tests can assert on the emails the store sends."""
    info = mailpit.info()

    assert info["Version"]
