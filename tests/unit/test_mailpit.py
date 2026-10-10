"""Unit tests for reading Mailpit messages."""

from datetime import UTC, datetime

import pytest

from magento_qa.mail.mailpit import Address, Message


def message(html: str) -> Message:
    return Message(
        id="1",
        subject="Reset your password",
        sender=Address(name="Store", address="store@example.com"),
        to=[Address(name="", address="qa@example.com")],
        date=datetime(2026, 10, 10, tzinfo=UTC),
        text="",
        html=html,
    )


def test_link_is_found_and_unescaped() -> None:
    email = message(
        '<a href="http://store/">Store</a>'
        '<a href="http://store/createPassword/?id=7&amp;token=abc">Set a New Password</a>'
    )

    assert email.link("createPassword") == "http://store/createPassword/?id=7&token=abc"


def test_missing_link_names_the_email() -> None:
    with pytest.raises(LookupError, match="Reset your password"):
        message('<a href="http://store/">Store</a>').link("createPassword")
