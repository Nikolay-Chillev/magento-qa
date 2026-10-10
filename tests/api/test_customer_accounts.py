"""Customer registration and sign-in through the REST API.

Every test registers its own customer with a unique email, so the tests are
independent. Failed sign-ins also use fresh customers: Magento locks an account
after repeated failures, and a shared account would lock for every test.
"""

import allure
import pytest

from magento_qa.api.customers import CustomerClient
from magento_qa.api.errors import MagentoApiError
from magento_qa.data.factories import new_customer, unique_email
from magento_qa.mail.mailpit import MailpitClient

pytestmark = pytest.mark.api

GENERAL_GROUP = 1  # the group Magento gives to self-registered customers
WHOLESALE_GROUP = 2
WELCOME_SUBJECT = "Welcome to Main Website Store"
DUPLICATE_EMAIL = "A customer with the same email address already exists in an associated website."
SIGN_IN_FAILED = (
    "The account sign-in was incorrect or your account is disabled temporarily. "
    "Please wait and try again later."
)
SAME_AS_EMAIL = "{email}"  # filled in with the customer's email
PASSWORD_CLASSES = (
    "Minimum of different classes of characters in password is 3. "
    "Classes of characters: Lower Case, Upper Case, Digits, Special Characters."
)


@allure.feature("Customer accounts")
@allure.story("Registration")
class TestRegistration:
    @allure.severity(allure.severity_level.CRITICAL)
    @allure.title("A new customer can sign in and sees their own profile")
    def test_new_customer_can_sign_in(self, customers: CustomerClient) -> None:
        new = new_customer()

        created = customers.register(new)
        profile = customers.me(customers.token(new.email, new.password))

        assert profile.id == created.id
        assert (profile.email, profile.firstname, profile.lastname) == (
            new.email,
            new.firstname,
            new.lastname,
        )
        assert profile.group_id == GENERAL_GROUP

    @pytest.mark.email
    @allure.severity(allure.severity_level.NORMAL)
    @allure.title("The welcome email greets the customer and does not repeat the password")
    def test_welcome_email(self, customers: CustomerClient, mailpit: MailpitClient) -> None:
        new = new_customer()

        customers.register(new)
        email = mailpit.wait_for_message(to=new.email, subject=WELCOME_SUBJECT)

        assert f"{new.full_name}," in email.text.splitlines()  # the greeting line
        assert new.email in email.text
        assert new.password not in email.text
        assert new.password not in email.html

    @pytest.mark.parametrize("case", ["lower", "upper"])
    @allure.severity(allure.severity_level.NORMAL)
    @allure.title("An email address can be registered only once ({case} case)")
    def test_duplicate_email_is_refused(self, customers: CustomerClient, case: str) -> None:
        first = new_customer()  # registered in lower case
        customers.register(first)

        with pytest.raises(MagentoApiError) as error:
            customers.register(new_customer(email=getattr(first.email, case)()))

        assert error.value.status == 400
        assert error.value.message == DUPLICATE_EMAIL

    @pytest.mark.parametrize(
        ("password", "reason"),
        [
            pytest.param(
                "Qa!1x",
                "The password needs at least 8 characters. Create a new password and try again.",
                id="too short",
            ),
            pytest.param("onlylowercase", PASSWORD_CLASSES, id="one character class"),
            pytest.param("lowercase123", PASSWORD_CLASSES, id="two character classes"),
            pytest.param(
                SAME_AS_EMAIL,
                "The password can't be the same as the email address. "
                "Create a new password and try again.",
                id="same as the email",
            ),
            pytest.param(
                " Qa!Passw0rd ",
                "The password can't begin or end with a space. Verify the password and try again.",
                id="spaces around",
            ),
        ],
    )
    @allure.severity(allure.severity_level.NORMAL)
    @allure.title("A weak password is refused with the reason")
    def test_weak_password_is_refused(
        self, customers: CustomerClient, password: str, reason: str
    ) -> None:
        new = new_customer()
        weak = new.model_copy(update={"password": password.format(email=new.email)})

        with pytest.raises(MagentoApiError) as error:
            customers.register(weak)

        assert error.value.status == 400
        assert error.value.message == reason
        # Nothing was half-created: the email is still free.
        customers.register(new)

    @allure.severity(allure.severity_level.CRITICAL)
    @allure.title("A shopper cannot choose a customer group when registering")
    def test_customer_group_cannot_be_chosen(self, customers: CustomerClient) -> None:
        # Groups decide prices, tax classes and promotions, so a shopper who could join
        # the Wholesale group would grant themselves its conditions.
        new = new_customer()

        with pytest.raises(MagentoApiError) as error:
            customers.register(new, group_id=WHOLESALE_GROUP)

        assert error.value.status == 401
        assert customers.register(new).group_id == GENERAL_GROUP


@allure.feature("Customer accounts")
@allure.story("Sign-in")
class TestSignIn:
    @allure.severity(allure.severity_level.CRITICAL)
    @allure.title("A wrong password and an unknown email get the same answer")
    def test_failed_sign_in_does_not_reveal_accounts(self, customers: CustomerClient) -> None:
        # A different answer for unknown emails would let anyone check who has an account.
        new = new_customer()
        customers.register(new)

        with pytest.raises(MagentoApiError) as wrong_password:
            customers.token(new.email, f"Wrong{new.password}")
        with pytest.raises(MagentoApiError) as unknown_email:
            customers.token(unique_email(), new.password)

        assert wrong_password.value.status == unknown_email.value.status == 401
        assert wrong_password.value.message == unknown_email.value.message == SIGN_IN_FAILED

    @pytest.mark.parametrize("case", ["upper", "title"])
    @allure.severity(allure.severity_level.MINOR)
    @allure.title("Sign-in accepts the email in any letter case ({case} case)")
    def test_email_letter_case_does_not_matter(self, customers: CustomerClient, case: str) -> None:
        new = new_customer()
        customers.register(new)

        profile = customers.me(customers.token(getattr(new.email, case)(), new.password))

        assert profile.email == new.email
