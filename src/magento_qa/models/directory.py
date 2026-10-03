"""Countries and regions from Magento's directory API."""

from pydantic import BaseModel


class Region(BaseModel):
    id: int
    code: str
    name: str


class Country(BaseModel):
    id: str
    available_regions: list[Region] = []
