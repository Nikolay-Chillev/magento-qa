"""The GraphQL storefront API that headless and mobile storefronts use.

Catalog tests only read the sample data; cart tests create their own guest carts.
"""

import math
from decimal import Decimal

import allure
import pytest

from magento_qa.api.catalog import CatalogClient
from magento_qa.api.customers import CustomerClient
from magento_qa.api.graphql import GraphQLClient, GraphQLError
from magento_qa.api.graphql_cart import GraphQLCartClient
from magento_qa.api.http import HttpClient
from magento_qa.data.factories import new_customer

pytestmark = pytest.mark.api

SIMPLE_SKU = "24-MB01"  # Joust Duffle Bag
CONFIGURABLE_SKU = "MH01"  # Chaz Kangeroo Hoodie, needs a size and a colour
LOW_STOCK_SKU = "24-UG04"  # five in stock, see the README


@pytest.fixture
def carts(graphql: GraphQLClient) -> GraphQLCartClient:
    return GraphQLCartClient(graphql)


@pytest.fixture
def cart_id(carts: GraphQLCartClient) -> str:
    return carts.create()


@allure.feature("GraphQL")
@allure.story("Catalog search")
class TestCatalogSearch:
    @allure.severity(allure.severity_level.CRITICAL)
    @allure.title("A filter by category and price returns only matching products")
    def test_filter_by_category_and_price(self, catalog: CatalogClient) -> None:
        bags = catalog.category_id("Bags")

        result = catalog.search(
            filter={"category_id": {"eq": str(bags)}, "price": {"from": "30", "to": "40"}}
        )

        assert result.total_count == len(result.items) > 0
        for product in result.items:
            assert bags in product.category_ids, product.sku
            assert Decimal(30) <= product.price <= Decimal(40), product.sku

    @pytest.mark.parametrize("direction", ["ASC", "DESC"])
    @allure.severity(allure.severity_level.NORMAL)
    @allure.title("Search results can be sorted by price ({direction})")
    def test_sort_by_price(self, catalog: CatalogClient, direction: str) -> None:
        result = catalog.search("bag", sort={"price": direction}, page_size=50)

        prices = [product.price for product in result.items]
        assert len(prices) > 1
        assert prices == sorted(prices, reverse=direction == "DESC")

    @allure.severity(allure.severity_level.NORMAL)
    @allure.title("Result pages do not overlap and add up to the total")
    def test_pages(self, catalog: CatalogClient) -> None:
        first = catalog.search("bag", sort={"price": "ASC"}, page_size=5, page=1)
        second = catalog.search("bag", sort={"price": "ASC"}, page_size=5, page=2)

        assert first.total_count == second.total_count
        assert first.page_info.total_pages == math.ceil(first.total_count / 5)
        assert not set(first.skus) & set(second.skus)
        assert len(first.items) + len(second.items) == min(first.total_count, 10)

    @allure.severity(allure.severity_level.MINOR)
    @allure.title("A page after the last one is refused with the number of pages")
    def test_page_after_the_last(self, catalog: CatalogClient) -> None:
        pages = catalog.search("bag", page_size=5).page_info.total_pages

        with pytest.raises(GraphQLError) as error:
            catalog.search("bag", page_size=5, page=pages + 1)

        assert error.value.messages == [
            f"currentPage value {pages + 1} specified is greater than "
            f"the {pages} page(s) available."
        ]
        assert error.value.categories == ["graphql-input"]


@allure.feature("GraphQL")
@allure.story("Cart")
class TestGraphQLCart:
    @allure.severity(allure.severity_level.CRITICAL)
    @allure.title("Added products are priced: row total and subtotal follow the quantity")
    def test_add(self, carts: GraphQLCartClient, catalog: CatalogClient, cart_id: str) -> None:
        price = catalog.product(SIMPLE_SKU).price

        result = carts.add(cart_id, SIMPLE_SKU, quantity=2)

        assert result.user_errors == []
        item = result.cart.item(SIMPLE_SKU)
        assert item.quantity == 2
        assert item.prices.row_total.value == price * 2
        assert result.cart.prices.subtotal_excluding_tax.value == price * 2
        assert result.cart.prices.subtotal_excluding_tax.currency == "EUR"

    @allure.severity(allure.severity_level.CRITICAL)
    @allure.title("Changing the quantity updates the totals; quantity 0 removes the item")
    def test_update(self, carts: GraphQLCartClient, catalog: CatalogClient, cart_id: str) -> None:
        price = catalog.product(SIMPLE_SKU).price
        uid = carts.add(cart_id, SIMPLE_SKU).cart.item(SIMPLE_SKU).uid

        updated = carts.update(cart_id, uid, 3)
        assert updated.total_quantity == 3
        assert updated.item(SIMPLE_SKU).prices.row_total.value == price * 3

        emptied = carts.update(cart_id, uid, 0)
        assert emptied.items == []

    @allure.severity(allure.severity_level.CRITICAL)
    @allure.title("A removed item leaves the cart")
    def test_remove(self, carts: GraphQLCartClient, cart_id: str) -> None:
        uid = carts.add(cart_id, SIMPLE_SKU).cart.item(SIMPLE_SKU).uid

        cart = carts.remove(cart_id, uid)

        assert cart.items == []
        assert carts.get(cart_id).total_quantity == 0

    @pytest.mark.parametrize(
        ("sku", "quantity", "code", "message"),
        [
            pytest.param(
                "NO-SUCH-SKU",
                1,
                "PRODUCT_NOT_FOUND",
                'Could not find a product with SKU "NO-SUCH-SKU"',
                id="unknown product",
            ),
            pytest.param(
                CONFIGURABLE_SKU,
                1,
                "REQUIRED_PARAMETER_MISSING",
                "You need to choose options for your item.",
                id="no size or colour",
            ),
            pytest.param(
                LOW_STOCK_SKU, 50, "INSUFFICIENT_STOCK", "Not enough items for sale", id="no stock"
            ),
            # The REST API turns 0 into 1 instead (finding #29).
            pytest.param(
                SIMPLE_SKU,
                0,
                "UNDEFINED",
                "The product quantity should be greater than 0",
                id="quantity 0",
            ),
        ],
    )
    @allure.severity(allure.severity_level.CRITICAL)
    @allure.title("A product that cannot be added is reported with a reason, the cart stays as is")
    def test_rejected_products(
        self,
        carts: GraphQLCartClient,
        cart_id: str,
        sku: str,
        quantity: int,
        code: str,
        message: str,
    ) -> None:
        result = carts.add(cart_id, sku, quantity)

        assert [(error.code, error.message) for error in result.user_errors] == [(code, message)]
        assert result.cart.items == []


@allure.feature("GraphQL")
@allure.story("Errors")
class TestGraphQLErrors:
    @allure.severity(allure.severity_level.CRITICAL)
    @allure.title("Errors arrive with HTTP 200, so clients must read the errors list")
    def test_errors_arrive_with_http_200(
        self, store_http: HttpClient, graphql: GraphQLClient
    ) -> None:
        query = '{ products(search: "bag") { no_such_field } }'

        response = store_http.post("graphql", json={"query": query})
        assert response.status_code == 200
        assert response.json()["errors"]

        with pytest.raises(GraphQLError, match='Cannot query field "no_such_field"'):
            graphql.execute(query)

    @allure.severity(allure.severity_level.NORMAL)
    @allure.title("Invalid input is reported in the graphql-input category")
    def test_invalid_input(self, catalog: CatalogClient) -> None:
        with pytest.raises(GraphQLError) as error:
            catalog.search("bag", page_size=0)

        assert error.value.messages == ["pageSize value must be greater than 0."]
        assert error.value.categories == ["graphql-input"]

    @allure.severity(allure.severity_level.NORMAL)
    @allure.title("An unknown cart id is reported in the graphql-no-such-entity category")
    def test_unknown_cart(self, carts: GraphQLCartClient) -> None:
        with pytest.raises(GraphQLError) as error:
            carts.get("x" * 32)

        assert error.value.categories == ["graphql-no-such-entity"]

    @allure.severity(allure.severity_level.CRITICAL)
    @allure.title("A customer's cart is refused to other customers and to guests")
    def test_customer_cart_is_private(
        self, graphql: GraphQLClient, customers: CustomerClient
    ) -> None:
        def signed_in() -> GraphQLCartClient:
            customer = new_customer()
            customers.register(customer)
            return GraphQLCartClient(
                graphql.with_token(customers.token(customer.email, customer.password))
            )

        owner, someone_else = signed_in(), signed_in()
        cart_id = owner.customer_cart_id()

        for caller in (someone_else, GraphQLCartClient(graphql)):
            with pytest.raises(GraphQLError) as error:
                caller.get(cart_id)
            assert error.value.categories == ["graphql-authorization"]
        assert owner.get(cart_id).items == []

    @allure.severity(allure.severity_level.CRITICAL)
    @allure.title("Customer data needs a signed-in customer")
    def test_customer_query_needs_a_token(self, graphql: GraphQLClient) -> None:
        with pytest.raises(GraphQLError) as error:
            graphql.execute("{ customer { email } }")

        assert error.value.messages == ["The current customer isn't authorized."]
        assert error.value.categories == ["graphql-authorization"]
