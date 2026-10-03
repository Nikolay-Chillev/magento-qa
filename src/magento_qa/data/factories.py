"""Realistic Bulgarian customers for the store, generated with bg-test-data."""

import uuid
from collections.abc import Mapping

from bg_test_data import BgTestData

from magento_qa.models.address import Address

_bg = BgTestData()


def unique_email(prefix: str = "qa") -> str:
    """An address no other test uses, so emails can be found by recipient in parallel runs."""
    return f"{prefix}+{uuid.uuid4().hex[:12]}@example.com"


def bulgarian_address(
    region_ids: Mapping[str, int], *, oblast_code: str | None = None, email: str | None = None
) -> Address:
    """A Bulgarian name, mobile phone and postal address in Magento's format.

    ``region_ids`` maps ISO 3166-2 codes to Magento region ids (see DirectoryClient);
    the oblast is matched by code because Magento names regions in English only.
    """
    name = _bg.name()
    address = _bg.address(oblast_code=oblast_code)
    code = address["oblast_code"]
    return Address(
        firstname=name["first_name"],
        lastname=name["last_name"],
        street=[f"ул. {address['street']} {address['number']}"],
        city=address["city"],
        postcode=address["postal_code"],
        country_id="BG",
        region_id=region_ids[code],
        region_code=code,
        telephone=_bg.phone(phone_type="mobile"),
        email=email or unique_email(),
    )
