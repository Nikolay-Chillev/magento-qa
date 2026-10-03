"""Unit tests for condition-based waiting."""

import re

import pytest

from magento_qa.waits import WaitTimeoutError, wait_until


def test_returns_the_first_truthy_value() -> None:
    values = iter([None, 0, "ready"])

    result = wait_until(lambda: next(values), description="a value", timeout=1, interval=0)

    assert result == "ready"


def test_times_out_with_a_descriptive_message() -> None:
    expected = re.escape("Timed out after 0.05s waiting for the moon")
    with pytest.raises(WaitTimeoutError, match=expected):
        wait_until(lambda: None, description="the moon", timeout=0.05, interval=0.01)


def test_ignored_exceptions_are_retried_and_reported_on_timeout() -> None:
    def always_failing() -> None:
        raise ConnectionError("refused")

    with pytest.raises(WaitTimeoutError, match="last error: ConnectionError"):
        wait_until(
            always_failing,
            description="a server",
            timeout=0.05,
            interval=0.01,
            ignored_exceptions=(ConnectionError,),
        )


def test_other_exceptions_propagate_immediately() -> None:
    def broken() -> None:
        raise KeyError("bug")

    with pytest.raises(KeyError):
        wait_until(broken, description="anything", timeout=5, ignored_exceptions=(ConnectionError,))
