"""Fixtures for browser tests (pytest-playwright).

Every UI test records a Playwright trace; when the test fails, the trace and a
full-page screenshot are attached to the Allure report. Open the trace with
``uv run python -m playwright show-trace trace.zip`` or at https://trace.playwright.dev.
"""

from collections.abc import Callable, Generator, Sequence
from pathlib import Path
from typing import Any

import allure
import pytest
from playwright.sync_api import BrowserContext, Page, expect

from magento_qa.config import Settings
from magento_qa.ui.cart_seed import SeedItem, seed_cart

# Luma renders parts of each page with JavaScript; the first visits after a
# fresh start are slow in developer mode.
expect.set_options(timeout=10_000)


@pytest.fixture(scope="session")
def base_url(settings: Settings, environment_ready: None) -> str:
    """Overrides pytest-base-url, so pages open relative to the store under test."""
    return str(settings.base_url)


@pytest.fixture(scope="session")
def browser_context_args(browser_context_args: dict[str, Any]) -> dict[str, Any]:
    return {**browser_context_args, "locale": "en-US", "viewport": {"width": 1366, "height": 900}}


@pytest.fixture
def seed(page: Page, base_url: str) -> Callable[[Sequence[SeedItem]], None]:
    """Fill this test's cart before it opens the first page."""
    return lambda items: seed_cart(page, base_url, items)


_reports_key = pytest.StashKey[dict[str, pytest.TestReport]]()


@pytest.hookimpl(wrapper=True)
def pytest_runtest_makereport(
    item: pytest.Item, call: pytest.CallInfo[None]
) -> Generator[None, pytest.TestReport, pytest.TestReport]:
    report = yield
    item.stash.setdefault(_reports_key, {})[report.when] = report
    return report


@pytest.fixture(autouse=True)
def _evidence_on_failure(
    request: pytest.FixtureRequest, context: BrowserContext, page: Page, tmp_path: Path
) -> Generator[None]:
    context.tracing.start(screenshots=True, snapshots=True)
    yield
    report = request.node.stash.get(_reports_key, {}).get("call")
    if report is None or not report.failed:
        context.tracing.stop()
        return
    allure.attach(
        page.screenshot(full_page=True),
        name="screenshot",
        attachment_type=allure.attachment_type.PNG,
    )
    trace = tmp_path / "trace.zip"
    context.tracing.stop(path=trace)
    allure.attach.file(trace, name="playwright-trace", extension="zip")
