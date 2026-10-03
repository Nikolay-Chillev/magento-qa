"""Unit tests for the test data factories."""

from magento_qa.data.factories import bulgarian_address, unique_email

# Fake Magento ids for the 28 oblasts; only the mapping by ISO code matters here.
REGION_IDS = {f"BG-{n:02d}": 640 + n for n in range(1, 29)}


def test_emails_are_unique_and_safe_to_send_to() -> None:
    emails = {unique_email() for _ in range(1000)}

    assert len(emails) == 1000
    assert all(email.endswith("@example.com") for email in emails)


def test_address_region_is_mapped_by_iso_code() -> None:
    address = bulgarian_address(REGION_IDS, oblast_code="BG-22")

    assert address.country_id == "BG"
    assert address.region_code == "BG-22"
    assert address.region_id == REGION_IDS["BG-22"]


def test_random_addresses_always_carry_a_known_region() -> None:
    for _ in range(50):
        address = bulgarian_address(REGION_IDS)
        assert address.region_code in REGION_IDS
        assert address.region_id == REGION_IDS[address.region_code]


def test_payload_omits_unset_fields() -> None:
    address = bulgarian_address(REGION_IDS).model_copy(update={"region": None})

    payload = address.payload()

    assert "region" not in payload
    assert payload["street"]
    assert payload["telephone"].startswith("+359")
