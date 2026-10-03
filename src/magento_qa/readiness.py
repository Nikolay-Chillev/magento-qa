"""Wait until the environment can serve tests."""

import requests

from magento_qa.api.http import HttpClient
from magento_qa.config import Settings
from magento_qa.mail.mailpit import MailpitClient
from magento_qa.waits import wait_until

# Search depends on Elasticsearch, the slowest service to start, so a search
# with results means the whole store is up.
CATALOG_SEARCH_QUERY = '{ products(search: "bag", pageSize: 1) { total_count } }'


def catalog_search_works(store: HttpClient) -> bool:
    response = store.post("graphql", json={"query": CATALOG_SEARCH_QUERY})
    if response.status_code != 200:
        return False
    total = response.json().get("data", {}).get("products", {}).get("total_count", 0)
    return isinstance(total, int) and total > 0


def wait_for_environment(settings: Settings) -> None:
    """Block until Magento catalog search answers with results and Mailpit responds."""
    store = HttpClient(str(settings.base_url), timeout=settings.request_timeout)
    mailpit = MailpitClient(
        HttpClient(str(settings.mailpit_url), timeout=settings.request_timeout),
        wait_timeout=settings.wait_timeout,
    )
    wait_until(
        lambda: catalog_search_works(store),
        description=f"Magento catalog search at {settings.base_url}",
        timeout=settings.wait_timeout,
        interval=2,
        ignored_exceptions=(requests.RequestException,),
    )
    wait_until(
        mailpit.info,
        description=f"Mailpit at {settings.mailpit_url}",
        timeout=settings.wait_timeout,
        interval=2,
        ignored_exceptions=(requests.RequestException,),
    )
