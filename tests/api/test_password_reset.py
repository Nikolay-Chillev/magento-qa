"""Password reset through the REST API: request, email, new password.

The test environment limits reset requests per email instead of per IP address
(see the README), so every test can request a reset for its own fresh customer.
The browser journey from the email link is in ``tests/ui/test_password_reset.py``.
"""

from urllib.parse import parse_qs, urlparse

import allure
import pytest

from magento_qa.api.customers import CustomerClient
from magento_qa.api.errors import MagentoApiError
from magento_qa.data.factories import new_customer, strong_password, unique_email
from magento_qa.mail.mailpit import MailpitClient, Message
from magento_qa.models.customer import NewCustomer

pytestmark = pytest.mark.api

RESET_SUBJECT = "Reset your Main Website Store password"
TOO_MANY_REQUESTS = (
    "We received too many requests for password resets. "
    "Please wait and try again later or contact hello@example.com."
)
TOKEN_MISMATCH = "The password token is mismatched. Reset and try again."


@pytest.fixture
def customer(customers: CustomerClient) -> NewCustomer:
    registered = new_customer()
    customers.register(registered)
    return registered


def reset_email(customers: CustomerClient, mailpit: MailpitClient, email: str) -> Message:
    customers.request_password_reset(email)
    return mailpit.wait_for_message(to=email, subject=RESET_SUBJECT)


def reset_token(email: Message) -> str:
    query = parse_qs(urlparse(email.link("customer/account/createPassword")).query)
    return query["token"][0]


@allure.feature("Customer accounts")
@allure.story("Password reset")
class TestPasswordReset:
    @pytest.mark.email
    @allure.severity(allure.severity_level.CRITICAL)
    @allure.title("The reset email greets the customer and links to a new password form")
    def test_reset_email(
        self, customers: CustomerClient, mailpit: MailpitClient, customer: NewCustomer
    ) -> None:
        email = reset_email(customers, mailpit, customer.email)

        assert f"{customer.full_name}," in email.text.splitlines()
        link = urlparse(email.link("customer/account/createPassword"))
        assert link.path == "/customer/account/createPassword/"
        assert parse_qs(link.query)["token"]

    @pytest.mark.email
    @allure.severity(allure.severity_level.CRITICAL)
    @allure.title("The token from the email sets a new password, and the old one stops working")
    def test_new_password_replaces_the_old_one(
        self, customers: CustomerClient, mailpit: MailpitClient, customer: NewCustomer
    ) -> None:
        token = reset_token(reset_email(customers, mailpit, customer.email))
        new_password = strong_password()

        customers.reset_password(customer.email, token, new_password)

        assert customers.me(customers.token(customer.email, new_password)).email == customer.email
        with pytest.raises(MagentoApiError) as old_password:
            customers.token(customer.email, customer.password)
        assert old_password.value.status == 401

    @pytest.mark.email
    @allure.severity(allure.severity_level.CRITICAL)
    @allure.title("A reset token works only once")
    def test_token_works_only_once(
        self, customers: CustomerClient, mailpit: MailpitClient, customer: NewCustomer
    ) -> None:
        token = reset_token(reset_email(customers, mailpit, customer.email))
        customers.reset_password(customer.email, token, strong_password())

        with pytest.raises(MagentoApiError) as reused:
            customers.reset_password(customer.email, token, strong_password())

        assert reused.value.status == 400
        assert reused.value.message == TOKEN_MISMATCH

    @allure.severity(allure.severity_level.NORMAL)
    @allure.title("A made-up token is refused")
    def test_made_up_token_is_refused(
        self, customers: CustomerClient, customer: NewCustomer
    ) -> None:
        customers.request_password_reset(customer.email)

        with pytest.raises(MagentoApiError) as forged:
            customers.reset_password(customer.email, "x" * 32, strong_password())

        assert forged.value.status == 400
        assert forged.value.message == TOKEN_MISMATCH

    @allure.severity(allure.severity_level.NORMAL)
    @allure.title("Reset requests for one email are limited, so no one can flood an inbox")
    def test_requests_are_limited(self, customers: CustomerClient, customer: NewCustomer) -> None:
        customers.request_password_reset(customer.email)

        with pytest.raises(MagentoApiError) as second:
            customers.request_password_reset(customer.email)

        assert second.value.status == 400
        assert second.value.message == TOO_MANY_REQUESTS

    @pytest.mark.xfail(
        strict=True, reason="Finding #57: an unknown email gets 404, a registered one 200"
    )
    @allure.severity(allure.severity_level.NORMAL)
    @allure.title("A reset request does not reveal whether an email has an account")
    def test_request_does_not_reveal_accounts(self, customers: CustomerClient) -> None:
        # A registered email gets "true"; an unknown one should get the same.
        customers.request_password_reset(unique_email())

    @pytest.mark.email
    @pytest.mark.xfail(strict=True, reason="Finding #58: API tokens survive a password reset")
    @allure.severity(allure.severity_level.CRITICAL)
    @allure.title("A password reset ends the API tokens issued before it")
    def test_reset_revokes_existing_tokens(
        self, customers: CustomerClient, mailpit: MailpitClient, customer: NewCustomer
    ) -> None:
        old_token = customers.token(customer.email, customer.password)
        token = reset_token(reset_email(customers, mailpit, customer.email))

        customers.reset_password(customer.email, token, strong_password())

        with pytest.raises(MagentoApiError) as revoked:
            customers.me(old_token)
        assert revoked.value.status == 401
