"""Admin REST API: what the store back office sees."""

from typing import Any

import requests
from pydantic import SecretStr

from magento_qa.api.errors import raise_for_magento_error
from magento_qa.api.http import HttpClient
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
