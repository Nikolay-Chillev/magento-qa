"""Storefront catalog through GraphQL (anonymous): product search, filters and sorting."""

from decimal import Decimal
from typing import Any

from pydantic import BaseModel

from magento_qa.api.graphql import GraphQLClient
from magento_qa.api.http import HttpClient

PRODUCT_FIELDS = """
  id sku name url_key url_suffix
  categories { id }
  price_range { minimum_price { final_price { value } } }
"""

PRODUCT_SEARCH = f"""
query (
  $search: String, $filter: ProductAttributeFilterInput, $sort: ProductAttributeSortInput,
  $pageSize: Int, $currentPage: Int
) {{
  products(
    search: $search, filter: $filter, sort: $sort, pageSize: $pageSize, currentPage: $currentPage
  ) {{
    total_count
    page_info {{ current_page page_size total_pages }}
    items {{ {PRODUCT_FIELDS} }}
  }}
}}
"""

CATEGORY_BY_NAME = """
query ($name: String!) { categoryList(filters: { name: { match: $name } }) { id name } }
"""


class _Price(BaseModel):
    value: Decimal


class _PriceRange(BaseModel):
    minimum_price: dict[str, _Price]


class _CategoryRef(BaseModel):
    id: int


class Product(BaseModel):
    id: int
    sku: str
    name: str
    url_key: str
    url_suffix: str
    categories: list[_CategoryRef] = []
    price_range: _PriceRange

    @property
    def price(self) -> Decimal:
        """Final price for a simple product (the lowest variant price for others)."""
        return self.price_range.minimum_price["final_price"].value

    @property
    def url_path(self) -> str:
        """Path of the product page relative to the store URL, e.g. ``joust-duffle-bag.html``."""
        return f"{self.url_key}{self.url_suffix}"

    @property
    def category_ids(self) -> set[int]:
        return {category.id for category in self.categories}


class PageInfo(BaseModel):
    current_page: int
    page_size: int
    total_pages: int


class SearchResult(BaseModel):
    total_count: int
    page_info: PageInfo
    items: list[Product]

    @property
    def skus(self) -> list[str]:
        return [product.sku for product in self.items]


class CatalogClient:
    def __init__(self, http: HttpClient) -> None:
        self.graphql = GraphQLClient(http)

    def product(self, sku: str) -> Product:
        items = self.search(filter={"sku": {"eq": sku}}).items
        if not items:
            raise LookupError(f"No product with SKU {sku!r}")
        return items[0]

    def search(
        self,
        text: str | None = None,
        *,
        filter: dict[str, Any] | None = None,
        sort: dict[str, str] | None = None,
        page_size: int = 20,
        page: int = 1,
    ) -> SearchResult:
        """Products as the storefront's search and category pages list them.

        ``filter`` and ``sort`` take GraphQL input, e.g. ``{"price": {"from": "30"}}``
        and ``{"price": "ASC"}``.
        """
        variables = {
            "search": text,
            "filter": filter or {},
            "sort": sort or {},
            "pageSize": page_size,
            "currentPage": page,
        }
        data = self.graphql.execute(PRODUCT_SEARCH, variables)
        return SearchResult.model_validate(data["products"])

    def category_id(self, name: str) -> int:
        categories = self.graphql.execute(CATEGORY_BY_NAME, {"name": name})["categoryList"]
        matches = [category["id"] for category in categories if category["name"] == name]
        if len(matches) != 1:
            raise LookupError(f"Expected one category named {name!r}, found {len(matches)}")
        return int(matches[0])
