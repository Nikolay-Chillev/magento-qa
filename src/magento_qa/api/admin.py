"""Admin REST API: what the store back office sees."""

from collections.abc import Mapping
from typing import Any

import requests
from pydantic import SecretStr

from magento_qa.api.errors import raise_for_magento_error
from magento_qa.api.http import HttpClient
from magento_qa.models.cart import VariantOption
from magento_qa.models.catalog import AttributeOption, ConfigurableAttribute, StockItem
from magento_qa.models.order import Order


class AdminClient:
    """Authenticates as an admin user and keeps the bearer token for the session.

    Admin tokens expire after an hour, so a 401 fetches a new token and retries once.
    """

    def __init__(self, http: HttpClient, *, username: str, password: SecretStr) -> None:
        self.http = http
        self.username = username
        self.password = password
        self._token: str | None = None

    def request(self, method: str, path: str, **kwargs: Any) -> requests.Response:
        response = self.http.request(method, path, headers=self._auth_header(), **kwargs)
        if response.status_code == 401:
            self._token = None
            response = self.http.request(method, path, headers=self._auth_header(), **kwargs)
        return response

    def get_order(self, order_id: int) -> Order:
        response = self.request("GET", f"rest/V1/orders/{order_id}")
        raise_for_magento_error(response)
        return Order.model_validate(response.json())

    def find_order(self, increment_id: str) -> Order:
        """The order a shopper sees as e.g. ``000000067``."""
        criteria = "searchCriteria[filterGroups][0][filters][0]"
        response = self.request(
            "GET",
            "rest/V1/orders",
            params={
                f"{criteria}[field]": "increment_id",
                f"{criteria}[value]": increment_id,
                f"{criteria}[conditionType]": "eq",
            },
        )
        raise_for_magento_error(response)
        items = response.json()["items"]
        if len(items) != 1:
            raise LookupError(f"Expected one order {increment_id}, found {len(items)}")
        return Order.model_validate(items[0])

    def configurable_attributes(self, sku: str) -> list[ConfigurableAttribute]:
        response = self.request("GET", f"rest/V1/configurable-products/{sku}/options/all")
        raise_for_magento_error(response)
        return [ConfigurableAttribute.model_validate(item) for item in response.json()]

    def attribute_options(self, attribute_id: int) -> list[AttributeOption]:
        response = self.request("GET", f"rest/V1/products/attributes/{attribute_id}/options")
        raise_for_magento_error(response)
        return [
            AttributeOption.model_validate(option)
            for option in response.json()
            if option["value"] != ""  # the empty "please select" entry
        ]

    def stock_item(self, sku: str) -> StockItem:
        response = self.request("GET", f"rest/V1/stockItems/{sku}")
        raise_for_magento_error(response)
        return StockItem.model_validate(response.json())

    def variant_options(self, sku: str, choice: Mapping[str, str]) -> list[VariantOption]:
        """Translate a variant chosen by labels, e.g. ``{"Color": "Black", "Size": "XS"}``,
        into the attribute and option ids the cart API expects.

        Ids differ between stores, so tests name variants the way a shopper sees them.
        A value the product does not offer is still resolved, so tests can try to buy it.
        """
        options = []
        for attribute in self.configurable_attributes(sku):
            label = choice[attribute.label]
            values = {o.label: int(o.value) for o in self.attribute_options(attribute.attribute_id)}
            if label not in values:
                raise KeyError(f"{attribute.label} has no option {label!r}")
            options.append(
                VariantOption(option_id=attribute.attribute_id, option_value=values[label])
            )
        return options

    def _auth_header(self) -> dict[str, str]:
        if self._token is None:
            self._token = self._fetch_token()
        return {"Authorization": f"Bearer {self._token}"}

    def _fetch_token(self) -> str:
        # A wrong password must fail fast: repeated failures lock the admin user for 30 minutes.
        response = self.http.post(
            "rest/V1/integration/admin/token",
            json={"username": self.username, "password": self.password.get_secret_value()},
            redact_response=True,
        )
        raise_for_magento_error(response)
        token: str = response.json()
        return token
