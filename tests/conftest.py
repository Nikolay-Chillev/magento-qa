"""Shared fixtures.

Client fixtures depend on ``environment_ready``, so any test that talks to the
store or Mailpit first waits for the environment, while unit tests never do.
"""

import pytest

from magento_qa.api.admin import AdminClient
from magento_qa.api.customers import CustomerClient
from magento_qa.api.directory import DirectoryClient
from magento_qa.api.http import HttpClient
from magento_qa.config import Settings, get_settings
from magento_qa.mail.mailpit import MailpitClient
from magento_qa.readiness import wait_for_environment


@pytest.fixture(scope="session")
def settings() -> Settings:
    return get_settings()


@pytest.fixture(scope="session")
def environment_ready(settings: Settings) -> None:
    wait_for_environment(settings)


@pytest.fixture(scope="session")
def store_http(settings: Settings, environment_ready: None) -> HttpClient:
    """HTTP client for the storefront, REST (``rest/V1/...``) and GraphQL (``graphql``)."""
    return HttpClient(str(settings.base_url), timeout=settings.request_timeout)


@pytest.fixture(scope="session")
def mailpit(settings: Settings, environment_ready: None) -> MailpitClient:
    http = HttpClient(str(settings.mailpit_url), timeout=settings.request_timeout)
    return MailpitClient(http, wait_timeout=settings.wait_timeout)


@pytest.fixture(scope="session")
def admin(settings: Settings, environment_ready: None) -> AdminClient:
    """Back-office view of the store. Has its own session, so no cookies mix with shoppers."""
    http = HttpClient(str(settings.base_url), timeout=settings.request_timeout)
    return AdminClient(http, username=settings.admin_username, password=settings.admin_password)


@pytest.fixture(scope="session")
def customers(store_http: HttpClient) -> CustomerClient:
    """Registration and sign-in. Tokens are passed per call, so one client serves every test."""
    return CustomerClient(store_http)


@pytest.fixture(scope="session")
def bulgarian_region_ids(store_http: HttpClient) -> dict[str, int]:
    """ISO 3166-2 code → Magento region id for the 28 Bulgarian oblasts."""
    return DirectoryClient(store_http).region_ids("BG")
