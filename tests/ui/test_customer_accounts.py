"""Customer accounts in the browser: registration, sign-in and sign-out.

Only registration goes through the form; the other tests create their customer
through the API and use the browser for what they verify.
"""

import re

import allure
import pytest
from playwright.sync_api import Page, expect

from magento_qa.api.customers import CustomerClient
from magento_qa.data.factories import new_customer
from magento_qa.ui.pages import AccountPage, LoginPage, RegisterPage

pytestmark = pytest.mark.ui

SIGN_IN_FAILED = "The account sign-in was incorrect or your account is disabled temporarily."
PASSWORD_CLASSES = "Minimum of different classes of characters in password is 3."


@allure.feature("Customer accounts")
class TestCustomerAccountsInTheBrowser:
    @allure.story("Registration")
    @allure.severity(allure.severity_level.CRITICAL)
    @allure.title("A shopper registers and lands on their account dashboard")
    def test_register(self, page: Page) -> None:
        customer = new_customer()

        account = RegisterPage(page).open().register(customer)

        expect(account.heading).to_have_text("My Account")
        expect(account.contact_information).to_contain_text(customer.full_name)
        expect(account.contact_information).to_contain_text(customer.email)
        expect(account.header.greeting).to_have_text(f"Welcome, {customer.full_name}!")

    @allure.story("Registration")
    @allure.severity(allure.severity_level.NORMAL)
    @allure.title("A weak password is explained and no account is created")
    def test_weak_password(self, page: Page, customers: CustomerClient) -> None:
        customer = new_customer()
        form = RegisterPage(page).open()

        form.fill(customer.model_copy(update={"password": "onlylowercase"}))
        form.create_button.click()

        # Luma checks the password in the browser once its scripts have loaded and the
        # server checks it again, so the same message can come from either.
        expect(page.get_by_text(PASSWORD_CLASSES)).to_be_visible()
        expect(page).to_have_url(re.compile(r"/customer/account/create/$"))
        customers.register(customer)  # the email is still free

    @allure.story("Sign-in")
    @allure.severity(allure.severity_level.CRITICAL)
    @allure.title("A customer signs in, is greeted by name and signs out")
    def test_sign_in_and_out(self, page: Page, customers: CustomerClient) -> None:
        customer = new_customer()
        customers.register(customer)

        LoginPage(page).open().sign_in(customer.email, customer.password)
        account = AccountPage(page)
        expect(account.heading).to_have_text("My Account")
        expect(account.header.greeting).to_have_text(f"Welcome, {customer.full_name}!")

        account.header.sign_out()
        expect(page.get_by_role("heading", level=1)).to_have_text("You are signed out")
        expect(account.header.sign_in_link).to_be_visible()

        page.goto(AccountPage.path)
        expect(page).to_have_url(re.compile(r"/customer/account/login/"))

    @allure.story("Sign-in")
    @allure.severity(allure.severity_level.NORMAL)
    @allure.title("A wrong password is refused without saying which part was wrong")
    def test_wrong_password(self, page: Page, customers: CustomerClient) -> None:
        customer = new_customer()
        customers.register(customer)
        login = LoginPage(page).open()

        login.sign_in(customer.email, f"Wrong{customer.password}")

        expect(login.message(SIGN_IN_FAILED)).to_be_visible()
        expect(page).to_have_url(re.compile(r"/customer/account/login/"))
        expect(login.header.sign_in_link).to_be_visible()
