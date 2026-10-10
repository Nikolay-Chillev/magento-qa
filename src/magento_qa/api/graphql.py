"""GraphQL client for the storefront API that headless and mobile storefronts use."""

from typing import Any

from magento_qa.api.http import HttpClient


class GraphQLError(AssertionError):
    """Errors from a GraphQL response.

    Magento answers most of them with HTTP 200 and an ``errors`` list (a syntax
    error gets 400), so the status alone would hide them; the client raises instead.
    """

    def __init__(self, errors: list[dict[str, Any]]) -> None:
        self.errors = errors
        super().__init__("; ".join(self.messages))

    @property
    def messages(self) -> list[str]:
        return [str(error.get("message", "")) for error in self.errors]

    @property
    def categories(self) -> list[str]:
        """Magento's error categories, e.g. ``graphql-authorization`` or ``graphql-input``."""
        return [str(error.get("extensions", {}).get("category", "")) for error in self.errors]


class GraphQLClient:
    def __init__(self, http: HttpClient, *, token: str | None = None) -> None:
        self.http = http
        self._headers = {"Authorization": f"Bearer {token}"} if token else {}

    def with_token(self, token: str) -> "GraphQLClient":
        """A client acting as the customer the token belongs to, with its own cookies.

        Magento keeps a session for GraphQL: a call with a token returns a session cookie
        that signs later calls in even without the token (finding #65). Separate cookies
        keep that session away from the anonymous client.
        """
        return GraphQLClient(self.http.fresh(), token=token)

    def execute(self, query: str, variables: dict[str, Any] | None = None) -> dict[str, Any]:
        """POST a query or mutation and return its ``data``; raise GraphQLError on errors.

        Always POST: GET requests would be answered from the full-page cache.
        """
        response = self.http.post(
            "graphql", json={"query": query, "variables": variables or {}}, headers=self._headers
        )
        try:
            body: dict[str, Any] = response.json()
        except ValueError:  # not JSON, e.g. an error page from the web server
            response.raise_for_status()
            raise
        if body.get("errors"):
            raise GraphQLError(body["errors"])
        response.raise_for_status()
        data: dict[str, Any] = body["data"]
        return data
