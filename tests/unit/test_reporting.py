"""Unit tests for the run summary shown on the GitHub Actions job page."""

from pathlib import Path

import pytest

from magento_qa.reporting import main, summarise

JUNIT = """<?xml version="1.0" encoding="utf-8"?>
<testsuites>
  <testsuite name="pytest" errors="1" failures="1" skipped="2" tests="6" time="95.4">
    <testcase classname="tests.ui.test_catalog.TestSearch" name="test_search[firefox]"/>
    <testcase classname="tests.ui.test_catalog.TestSearch" name="test_empty[firefox]"/>
    <testcase classname="tests.ui.test_cart" name="test_coupon[firefox]">
      <failure message="AssertionError: Locator expected to be visible&#10;Actual value: None"/>
    </testcase>
    <testcase classname="tests.ui.test_cart" name="test_seed[firefox]">
      <error message="failed on setup with &quot;TimeoutError&quot;"/>
    </testcase>
    <testcase classname="tests.api.test_cart" name="test_zero_qty">
      <skipped type="pytest.xfail" message="Finding #29"/>
    </testcase>
    <testcase classname="tests.ui.test_reset" name="test_other">
      <skipped type="pytest.skip" message="not for this browser"/>
    </testcase>
  </testsuite>
</testsuites>
"""


def test_results_are_counted() -> None:
    summary = summarise(JUNIT)

    assert (summary.passed, summary.xfailed, summary.skipped) == (2, 1, 1)
    assert summary.failed == [
        (
            "tests.ui.test_cart::test_coupon[firefox]",
            "AssertionError: Locator expected to be visible",
        ),
        ("tests.ui.test_cart::test_seed[firefox]", 'failed on setup with "TimeoutError"'),
    ]
    assert summary.seconds == pytest.approx(95.4)


def test_markdown_lists_failures() -> None:
    text = summarise(JUNIT).markdown("Firefox")

    assert text.startswith("### Firefox: failed\n")
    assert "2 passed, 2 failed, 1 xfailed, 1 skipped in 95 s" in text
    assert "| `tests.ui.test_cart::test_coupon[firefox]` | AssertionError:" in text


def test_a_clean_run_has_no_table() -> None:
    passing = (
        '<testsuites><testsuite time="3">'
        '<testcase classname="a" name="b"/></testsuite></testsuites>'
    )

    text = summarise(passing).markdown("WebKit")

    assert text.startswith("### WebKit: passed\n")
    assert "|" not in text


def test_missing_report_is_said_plainly(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert main([str(tmp_path / "junit.xml"), "Chromium"]) == 0

    assert "### Chromium: no results" in capsys.readouterr().out
