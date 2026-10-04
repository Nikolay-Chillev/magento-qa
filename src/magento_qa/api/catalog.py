"""Storefront catalog through GraphQL (anonymous), e.g. to find a product's id and URL."""

from decimal import Decimal
from typing import Any

from pydantic import BaseModel

from magento_qa.api.http import HttpClient

PRODUCT_BY_SKU = """
query ($sku: String!) {
  products(filter: { sku: { eq: $sku } }) {
    items {
      id sku name url_key url_suffix
      price_range { minimum_price { final_price { value } } }
    }
  }
}
"""


class GraphQLError(AssertionError):
    """GraphQL answers errors with HTTP 200, so they are raised explicitly."""


class _Price(BaseModel):
    value: Decimal


class _PriceRange(BaseModel):
    minimum_price: dict[str, _Price]


class Product(BaseModel):
    id: int
    sku: str
    name: str
    url_key: str
    url_suffix: str
    price_range: _PriceRange

    @property
    def price(self) -> Decimal:
        """Final price for a simple product (the lowest variant price for others)."""
        return self.price_range.minimum_price["final_price"].value

    @property
    def url_path(self) -> str:
        """Path of the product page relative to the store URL, e.g. ``joust-duffle-bag.html``."""
        return f"{self.url_key}{self.url_suffix}"


class CatalogClient:
    def __init__(self, http: HttpClient) -> None:
        self.http = http

    def query(self, query: str, variables: dict[str, Any] | None = None) -> dict[str, Any]:
        """POST a GraphQL query (GET would be served from the full-page cache)."""
        response = self.http.post("graphql", json={"query": query, "variables": variables or {}})
        response.raise_for_status()
        body: dict[str, Any] = response.json()
        if body.get("errors"):
            raise GraphQLError(body["errors"])
        data: dict[str, Any] = body["data"]
        return data

    def product(self, sku: str) -> Product:
        items = self.query(PRODUCT_BY_SKU, {"sku": sku})["products"]["items"]
        if not items:
            raise LookupError(f"No product with SKU {sku!r}")
        return Product.model_validate(items[0])
