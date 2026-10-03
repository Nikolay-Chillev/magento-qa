"""Client for the Mailpit API: find and read the emails the store sent."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_pascal

from magento_qa.api.http import HttpClient
from magento_qa.waits import wait_until


class _MailpitModel(BaseModel):
    # Mailpit uses PascalCase keys ("Subject", "To"); acronyms ("ID", "HTML") get explicit aliases.
    model_config = ConfigDict(alias_generator=to_pascal, populate_by_name=True, extra="ignore")


class Address(_MailpitModel):
    name: str
    address: str


class MessageSummary(_MailpitModel):
    id: str = Field(alias="ID")
    subject: str
    to: list[Address]
    created: datetime


class Message(_MailpitModel):
    id: str = Field(alias="ID")
    subject: str
    sender: Address = Field(alias="From")
    to: list[Address]
    date: datetime
    text: str
    html: str = Field(alias="HTML")


class MailpitClient:
    def __init__(self, http: HttpClient, *, wait_timeout: float) -> None:
        self.http = http
        self.wait_timeout = wait_timeout

    def info(self) -> dict[str, Any]:
        response = self.http.get("api/v1/info")
        response.raise_for_status()
        info: dict[str, Any] = response.json()
        return info

    def search(self, query: str) -> list[MessageSummary]:
        """Search with Mailpit's query syntax, e.g. ``to:"a@example.com"``. Newest first."""
        response = self.http.get("api/v1/search", params={"query": query})
        response.raise_for_status()
        return [MessageSummary.model_validate(item) for item in response.json()["messages"]]

    def get_message(self, message_id: str) -> Message:
        response = self.http.get(f"api/v1/message/{message_id}")
        response.raise_for_status()
        return Message.model_validate(response.json())

    def wait_for_message(
        self, *, to: str, subject: str | None = None, timeout: float | None = None
    ) -> Message:
        """Wait for the newest email to ``to`` (optionally containing ``subject``) and return it.

        Tests use a unique recipient each, so searching by recipient stays correct
        when tests run in parallel against the same Mailpit.
        """
        query = f'to:"{to}"' + (f' subject:"{subject}"' if subject else "")
        summary = wait_until(
            lambda: next(iter(self.search(query)), None),
            description=f"an email matching {query}",
            timeout=self.wait_timeout if timeout is None else timeout,
        )
        return self.get_message(summary.id)
