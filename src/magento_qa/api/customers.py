"""Customer accounts through the REST API, as headless storefronts and mobile apps use it."""

from typing import Any

from magento_qa.api.errors import raise_for_magento_error
from magento_qa.api.http import HttpClient
from magento_qa.models.customer import Customer, NewCustomer


class CustomerClient:
    def __init__(self, http: HttpClient) -> None:
        self.http = http

    def register(self, customer: NewCustomer, **fields: Any) -> Customer:
        """Self-registration, open to anyone; ``fields`` are extra customer attributes."""
        response = self.http.post("rest/V1/customers", json=customer.payload(**fields))
        raise_for_magento_error(response)
        return Customer.model_validate(response.json())

    def token(self, email: str, password: str) -> str:
        """Sign in; the token authorises the customer's own ``/me`` endpoints."""
        response = self.http.post(
            "rest/V1/integration/customer/token",
            json={"username": email, "password": password},
            redact_response=True,
        )
        raise_for_magento_error(response)
        token: str = response.json()
        return token

    def me(self, token: str) -> Customer:
        response = self.http.get(
            "rest/V1/customers/me", headers={"Authorization": f"Bearer {token}"}
        )
        raise_for_magento_error(response)
        return Customer.model_validate(response.json())
