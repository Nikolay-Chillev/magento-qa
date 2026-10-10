"""Cart through GraphQL, as a headless storefront builds it.

Problems with a product (unknown SKU, no stock, missing options) come back as
``user_errors`` next to the unchanged cart, not as GraphQL errors.
"""

from decimal import Decimal

from pydantic import BaseModel

from magento_qa.api.graphql import GraphQLClient

CART_FIELDS = """
  total_quantity
  items {
    uid quantity
    product { sku }
    prices { price { value } row_total { value } }
  }
  prices { subtotal_excluding_tax { value currency } grand_total { value } }
"""


class _Money(BaseModel):
    value: Decimal


class _Currency(_Money):
    currency: str


class _ItemPrices(BaseModel):
    price: _Money
    row_total: _Money


class _ProductRef(BaseModel):
    sku: str


class GraphQLCartItem(BaseModel):
    uid: str
    quantity: Decimal
    product: _ProductRef
    prices: _ItemPrices


class _CartPrices(BaseModel):
    subtotal_excluding_tax: _Currency
    grand_total: _Money


class GraphQLCart(BaseModel):
    total_quantity: Decimal
    items: list[GraphQLCartItem]
    prices: _CartPrices

    def item(self, sku: str) -> GraphQLCartItem:
        matches = [item for item in self.items if item.product.sku == sku]
        if len(matches) != 1:
            raise LookupError(f"Expected one {sku} in the cart, found {len(matches)}")
        return matches[0]


class UserError(BaseModel):
    code: str
    message: str


class AddResult(BaseModel):
    cart: GraphQLCart
    user_errors: list[UserError]


class GraphQLCartClient:
    def __init__(self, graphql: GraphQLClient) -> None:
        self.graphql = graphql

    def create(self) -> str:
        """A new guest cart; returns its id (32 random characters)."""
        data = self.graphql.execute("mutation { createGuestCart { cart { id } } }")
        cart_id: str = data["createGuestCart"]["cart"]["id"]
        return cart_id

    def customer_cart_id(self) -> str:
        """The signed-in customer's cart (needs a client with a token)."""
        data = self.graphql.execute("{ customerCart { id } }")
        cart_id: str = data["customerCart"]["id"]
        return cart_id

    def get(self, cart_id: str) -> GraphQLCart:
        data = self.graphql.execute(
            f"query ($cartId: String!) {{ cart(cart_id: $cartId) {{ {CART_FIELDS} }} }}",
            {"cartId": cart_id},
        )
        return GraphQLCart.model_validate(data["cart"])

    def add(self, cart_id: str, sku: str, quantity: float = 1) -> AddResult:
        data = self.graphql.execute(
            f"""
            mutation ($cartId: String!, $sku: String!, $quantity: Float!) {{
              addProductsToCart(cartId: $cartId, cartItems: [{{sku: $sku, quantity: $quantity}}]) {{
                cart {{ {CART_FIELDS} }}
                user_errors {{ code message }}
              }}
            }}
            """,
            {"cartId": cart_id, "sku": sku, "quantity": quantity},
        )
        return AddResult.model_validate(data["addProductsToCart"])

    def update(self, cart_id: str, item_uid: str, quantity: float) -> GraphQLCart:
        """Change an item's quantity; 0 removes the item."""
        data = self.graphql.execute(
            f"""
            mutation ($cartId: String!, $uid: ID!, $quantity: Float!) {{
              updateCartItems(input: {{
                cart_id: $cartId, cart_items: [{{cart_item_uid: $uid, quantity: $quantity}}]
              }}) {{ cart {{ {CART_FIELDS} }} }}
            }}
            """,
            {"cartId": cart_id, "uid": item_uid, "quantity": quantity},
        )
        return GraphQLCart.model_validate(data["updateCartItems"]["cart"])

    def remove(self, cart_id: str, item_uid: str) -> GraphQLCart:
        data = self.graphql.execute(
            f"""
            mutation ($cartId: String!, $uid: ID!) {{
              removeItemFromCart(input: {{cart_id: $cartId, cart_item_uid: $uid}}) {{
                cart {{ {CART_FIELDS} }}
              }}
            }}
            """,
            {"cartId": cart_id, "uid": item_uid},
        )
        return GraphQLCart.model_validate(data["removeItemFromCart"]["cart"])
