"""Brute-force protection of the customer sign-in API.

Magento counts wrong passwords per account and refuses tokens for 30 minutes
after the sixth one (Stores > Configuration > Services > OAuth > Authentication
Locks, at their defaults). Every test locks only its own fresh customer. A failed
test is not retried: a retry would start from an account that is already locked.
"""

import allure
import pytest

from magento_qa.api.customers import CustomerClient
from magento_qa.api.errors import MagentoApiError
from magento_qa.data.factories import new_customer
from magento_qa.models.customer import NewCustomer

pytestmark = pytest.mark.api

MAX_FAILURES = 6
WRONG_PASSWORD = "Wrong!Passw0rd1"


@pytest.fixture
def customer(customers: CustomerClient) -> NewCustomer:
    registered = new_customer()
    customers.register(registered)
    return registered


def fail_sign_in(customers: CustomerClient, email: str, *, times: int) -> MagentoApiError:
    """Sign in with a wrong password ``times`` times; return the last refusal."""
    for _ in range(times):
        with pytest.raises(MagentoApiError) as error:
            customers.token(email, WRONG_PASSWORD)
        assert error.value.status == 401
    return error.value


@allure.feature("Customer accounts")
@allure.story("Brute-force protection")
class TestSignInLockout:
    @allure.severity(allure.severity_level.CRITICAL)
    @allure.title("Five wrong passwords do not lock the account, and signing in resets the count")
    def test_failures_below_the_limit_do_not_lock(
        self, customers: CustomerClient, customer: NewCustomer
    ) -> None:
        # Twice in a row: without the reset, the second round would reach the limit.
        for _ in range(2):
            fail_sign_in(customers, customer.email, times=MAX_FAILURES - 1)
            assert customers.token(customer.email, customer.password)

    @allure.severity(allure.severity_level.CRITICAL)
    @allure.title("The sixth wrong password locks the account, even against the right password")
    def test_account_locks_at_the_limit(
        self, customers: CustomerClient, customer: NewCustomer
    ) -> None:
        wrong_password = fail_sign_in(customers, customer.email, times=MAX_FAILURES)

        with pytest.raises(MagentoApiError) as locked:
            customers.token(customer.email, customer.password)

        # The same answer as a wrong password: nothing tells an attacker that the
        # account exists or that it is locked.
        assert locked.value.status == 401
        assert locked.value.message == wrong_password.message

    @allure.severity(allure.severity_level.NORMAL)
    @allure.title("A locked account does not keep other customers out")
    def test_lock_does_not_affect_other_customers(
        self, customers: CustomerClient, customer: NewCustomer
    ) -> None:
        fail_sign_in(customers, customer.email, times=MAX_FAILURES)
        other = new_customer()
        customers.register(other)

        assert customers.token(other.email, other.password)
