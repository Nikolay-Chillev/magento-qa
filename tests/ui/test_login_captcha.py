"""CAPTCHA on the storefront sign-in form.

Magento asks for a CAPTCHA after three wrong passwords for the same email
(Stores > Configuration > Customers > Customer Configuration > CAPTCHA, at their
defaults). Each test uses a fresh customer, so the counts of other tests do not
interfere. A failed test is not retried: a retry would start with the CAPTCHA shown.
"""

import re

import allure
import pytest
from playwright.sync_api import BrowserContext, Page, expect
from pytest_playwright.pytest_playwright import CreateContextCallback

from magento_qa.api.customers import CustomerClient
from magento_qa.data.factories import new_customer
from magento_qa.models.customer import NewCustomer
from magento_qa.ui.pages import AccountPage, LoginPage

pytestmark = pytest.mark.ui

FAILURES_BEFORE_CAPTCHA = 3
WRONG_PASSWORD = "Wrong!Passw0rd1"
SIGN_IN_FAILED = "The account sign-in was incorrect"
INCORRECT_CAPTCHA = "Incorrect CAPTCHA"
SIGNED_OUT = re.compile(r"/customer/account/login/")


@pytest.fixture
def customer(customers: CustomerClient) -> NewCustomer:
    registered = new_customer()
    customers.register(registered)
    return registered


def fail_sign_in(login: LoginPage, email: str, *, times: int) -> None:
    for _ in range(times):
        login.sign_in(email, WRONG_PASSWORD)
        expect(login.message(SIGN_IN_FAILED)).to_be_visible()


def post_sign_in(context: BrowserContext, email: str, password: str) -> None:
    """Send the sign-in form the way a script would: only email and password."""
    form_key = next(cookie["value"] for cookie in context.cookies() if cookie["name"] == "form_key")
    response = context.request.post(
        "customer/account/loginPost/",
        form={"form_key": form_key, "login[username]": email, "login[password]": password},
        max_redirects=0,
    )
    assert response.status == 302


@allure.feature("Customer accounts")
@allure.story("Brute-force protection")
class TestSignInCaptcha:
    @allure.severity(allure.severity_level.CRITICAL)
    @allure.title("After three wrong passwords the sign-in form asks for a CAPTCHA")
    def test_captcha_appears_after_three_failures(self, page: Page, customer: NewCustomer) -> None:
        login = LoginPage(page).open()

        fail_sign_in(login, customer.email, times=FAILURES_BEFORE_CAPTCHA - 1)
        expect(login.captcha).to_be_hidden()

        fail_sign_in(login, customer.email, times=1)
        expect(login.captcha).to_be_visible()
        expect(login.captcha_image).to_be_visible()

    @allure.severity(allure.severity_level.CRITICAL)
    @allure.title("The right password is refused while the CAPTCHA is wrong")
    def test_wrong_captcha_is_refused(self, page: Page, customer: NewCustomer) -> None:
        login = LoginPage(page).open()
        fail_sign_in(login, customer.email, times=FAILURES_BEFORE_CAPTCHA)

        login.sign_in(customer.email, customer.password, captcha="WRONG")

        expect(login.message(INCORRECT_CAPTCHA)).to_be_visible()
        expect(page).to_have_url(SIGNED_OUT)
        expect(login.header.sign_in_link).to_be_visible()

    @allure.severity(allure.severity_level.CRITICAL)
    @allure.title("Leaving the CAPTCHA out of the request does not skip it")
    def test_captcha_cannot_be_skipped(
        self, page: Page, context: BrowserContext, customer: NewCustomer
    ) -> None:
        login = LoginPage(page).open()
        for _ in range(FAILURES_BEFORE_CAPTCHA):
            post_sign_in(context, customer.email, WRONG_PASSWORD)
        login.open()
        expect(login.captcha).to_be_visible()  # the server counted the scripted attempts

        post_sign_in(context, customer.email, customer.password)

        page.goto(AccountPage.path)
        expect(page).to_have_url(SIGNED_OUT)

    @allure.severity(allure.severity_level.NORMAL)
    @allure.title("The CAPTCHA follows the account to another browser")
    def test_captcha_follows_the_account(
        self, page: Page, new_context: CreateContextCallback, customer: NewCustomer
    ) -> None:
        fail_sign_in(LoginPage(page).open(), customer.email, times=FAILURES_BEFORE_CAPTCHA)
        # A new browser has no cookies, so clearing them would not help an attacker.
        other_browser = LoginPage(new_context().new_page()).open()

        other_browser.sign_in(customer.email, customer.password)

        expect(other_browser.message(INCORRECT_CAPTCHA)).to_be_visible()
        expect(other_browser.captcha).to_be_visible()

    @allure.severity(allure.severity_level.NORMAL)
    @allure.title("Other customers signing in from the same address are not asked")
    def test_other_customers_are_not_asked(
        self,
        page: Page,
        new_context: CreateContextCallback,
        customer: NewCustomer,
        customers: CustomerClient,
    ) -> None:
        fail_sign_in(LoginPage(page).open(), customer.email, times=FAILURES_BEFORE_CAPTCHA)
        other = new_customer()
        customers.register(other)
        other_page = new_context().new_page()

        LoginPage(other_page).open().sign_in(other.email, other.password)

        expect(AccountPage(other_page).heading).to_have_text("My Account")

    @allure.severity(allure.severity_level.NORMAL)
    @allure.title("Signing in resets the count, so occasional typos never lead to a CAPTCHA")
    def test_signing_in_resets_the_count(self, page: Page, customer: NewCustomer) -> None:
        login = LoginPage(page).open()
        fail_sign_in(login, customer.email, times=FAILURES_BEFORE_CAPTCHA - 1)
        login.sign_in(customer.email, customer.password)
        account = AccountPage(page)
        expect(account.heading).to_have_text("My Account")
        account.header.sign_out()

        login.open()
        fail_sign_in(login, customer.email, times=FAILURES_BEFORE_CAPTCHA - 1)

        expect(login.captcha).to_be_hidden()
