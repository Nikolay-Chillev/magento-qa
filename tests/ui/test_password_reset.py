"""Password reset from the email to the browser.

The reset is requested through the API, as the "Forgot Your Password?" form would;
the test then follows the link in the email the way the customer does.
"""

import re
import time

import allure
import pytest
from playwright.sync_api import Page, expect

from magento_qa.api.customers import CustomerClient
from magento_qa.api.errors import MagentoApiError
from magento_qa.data.factories import new_customer, strong_password
from magento_qa.mail.mailpit import MailpitClient
from magento_qa.models.customer import NewCustomer
from magento_qa.ui.pages import AccountPage, LoginPage, ResetPasswordPage
from magento_qa.waits import wait_until

pytestmark = [pytest.mark.ui, pytest.mark.email]

RESET_SUBJECT = "Reset your Main Website Store password"
LINK_PATH = "customer/account/createPassword"
SIGNED_OUT = re.compile(r"/customer/account/login/")


@pytest.fixture
def customer(customers: CustomerClient) -> NewCustomer:
    registered = new_customer()
    customers.register(registered)
    return registered


@pytest.fixture
def reset_link(customers: CustomerClient, mailpit: MailpitClient, customer: NewCustomer) -> str:
    customers.request_password_reset(customer.email)
    return mailpit.wait_for_message(to=customer.email, subject=RESET_SUBJECT).link(LINK_PATH)


@allure.feature("Customer accounts")
@allure.story("Password reset")
class TestPasswordResetInTheBrowser:
    @allure.severity(allure.severity_level.CRITICAL)
    @allure.title("A customer sets a new password from the email link and signs in with it")
    def test_reset_from_the_email(
        self, page: Page, customers: CustomerClient, customer: NewCustomer, reset_link: str
    ) -> None:
        new_password = strong_password()

        form = ResetPasswordPage(page).open_link(reset_link)
        expect(form.heading).to_have_text("Set a New Password")
        # The token leaves the address bar, so it cannot leak through history or referrers.
        expect(page).not_to_have_url(re.compile("token="))
        login = form.set_password(new_password)
        expect(login.message("You updated your password.")).to_be_visible()

        login.sign_in(customer.email, new_password)
        expect(AccountPage(page).heading).to_have_text("My Account")
        with pytest.raises(MagentoApiError) as old_password:
            customers.token(customer.email, customer.password)
        assert old_password.value.status == 401

    @allure.severity(allure.severity_level.CRITICAL)
    @allure.title("The email link cannot be used a second time")
    def test_link_works_only_once(self, page: Page, reset_link: str) -> None:
        ResetPasswordPage(page).open_link(reset_link).set_password(strong_password())

        form = ResetPasswordPage(page).open_link(reset_link)

        expect(page).to_have_url(re.compile(r"/customer/account/forgotpassword/"))
        expect(form.message("Your password reset link has expired.")).to_be_visible()
        expect(form.heading).to_have_text("Forgot Your Password?")
        expect(form.save_button).to_have_count(0)

    @pytest.mark.xfail(
        strict=True,
        reason="Finding #59: the first request after the reset fails with HTTP 500",
    )
    @allure.severity(allure.severity_level.NORMAL)
    @allure.title("A browser signed in before the reset is signed out")
    def test_signed_in_browser_is_signed_out(
        self,
        page: Page,
        customers: CustomerClient,
        mailpit: MailpitClient,
        customer: NewCustomer,
    ) -> None:
        LoginPage(page).open().sign_in(customer.email, customer.password)
        expect(AccountPage(page).heading).to_have_text("My Account")
        # Magento compares whole seconds: a session from the same second as the reset
        # survives it, so the reset has to happen in a later second.
        signed_in_at = int(time.time())
        wait_until(
            lambda: int(time.time()) > signed_in_at,
            description="the second after the sign-in",
            timeout=2,
            interval=0.1,
        )
        customers.request_password_reset(customer.email)
        email = mailpit.wait_for_message(to=customer.email, subject=RESET_SUBJECT)
        token = re.search(r"token=([^&]+)", email.link(LINK_PATH))
        assert token
        customers.reset_password(customer.email, token.group(1), strong_password())

        response = page.goto(AccountPage.path)

        assert response is not None
        assert response.ok, f"HTTP {response.status} instead of the sign-in page"
        expect(page).to_have_url(SIGNED_OUT)
