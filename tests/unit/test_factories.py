"""Unit tests for the test data factories."""

import re

from magento_qa.data.factories import bulgarian_address, new_customer, strong_password, unique_email

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


def test_passwords_meet_magentos_default_rules() -> None:
    classes = [r"[a-z]", r"[A-Z]", r"\d", r"[^a-zA-Z\d]"]
    for _ in range(100):
        password = strong_password()
        assert len(password) >= 8
        assert sum(bool(re.search(pattern, password)) for pattern in classes) >= 3
        assert password == password.strip()


def test_new_customers_do_not_share_email_or_password() -> None:
    customers = [new_customer() for _ in range(100)]

    assert len({customer.email for customer in customers}) == 100
    assert len({customer.password for customer in customers}) == 100
    assert all(customer.firstname and customer.lastname for customer in customers)


def test_registration_payload_keeps_the_password_outside_the_customer() -> None:
    customer = new_customer()

    payload = customer.payload(group_id=2)

    assert payload["password"] == customer.password
    assert "password" not in payload["customer"]
    assert payload["customer"]["email"] == customer.email
    assert payload["customer"]["group_id"] == 2
