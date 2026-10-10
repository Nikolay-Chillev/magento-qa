"""Customer accounts as the REST API returns them."""

from typing import Any

from pydantic import BaseModel


class Customer(BaseModel):
    id: int
    email: str
    firstname: str
    lastname: str
    group_id: int
    website_id: int
    store_id: int


class NewCustomer(BaseModel):
    """What a shopper enters on the registration form."""

    email: str
    firstname: str
    lastname: str
    password: str

    @property
    def full_name(self) -> str:
        return f"{self.firstname} {self.lastname}"

    def payload(self, **fields: Any) -> dict[str, Any]:
        """The JSON body for registration; ``fields`` add to the customer object."""
        customer = self.model_dump(exclude={"password"})
        return {"customer": {**customer, **fields}, "password": self.password}
