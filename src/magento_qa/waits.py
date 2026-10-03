"""Condition-based waiting, used instead of fixed sleeps."""

import time
from collections.abc import Callable


class WaitTimeoutError(AssertionError):
    """A condition was not met in time. Subclasses AssertionError so pytest reports a failure."""


def wait_until[T](
    condition: Callable[[], T | None],
    *,
    description: str,
    timeout: float,
    interval: float = 0.5,
    ignored_exceptions: tuple[type[Exception], ...] = (),
) -> T:
    """Call ``condition`` until it returns a truthy value, and return that value.

    Exceptions listed in ``ignored_exceptions`` count as "not yet"; any other
    exception propagates immediately. Raises WaitTimeoutError after ``timeout`` seconds.
    """
    deadline = time.monotonic() + timeout
    last_error: Exception | None = None
    while True:
        try:
            result = condition()
        except ignored_exceptions as error:
            result, last_error = None, error
        if result:
            return result
        if time.monotonic() >= deadline:
            detail = f"; last error: {last_error!r}" if last_error else ""
            raise WaitTimeoutError(f"Timed out after {timeout}s waiting for {description}{detail}")
        time.sleep(interval)
