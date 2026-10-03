"""Customer address as Magento's checkout API expects it."""

from typing import Any

from pydantic import BaseModel


class Address(BaseModel):
    firstname: str
    lastname: str
    street: list[str]
    city: str
    postcode: str
    country_id: str
    telephone: str
    email: str | None = None
    region_id: int | None = None
    region_code: str | None = None
    region: str | None = None

    def payload(self) -> dict[str, Any]:
        """The JSON body for Magento, without unset fields."""
        return self.model_dump(exclude_none=True)
