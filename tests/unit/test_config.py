"""Unit tests for the framework settings; they need no running environment."""

import pytest
from pydantic import ValidationError

from magento_qa.config import Settings


def test_defaults_point_to_local_docker_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("QA_BASE_URL", raising=False)
    monkeypatch.delenv("QA_MAILPIT_URL", raising=False)

    settings = Settings(_env_file=None)  # type: ignore[call-arg]

    assert str(settings.base_url) == "http://localhost:8080/"
    assert str(settings.mailpit_url) == "http://localhost:8025/"


def test_environment_variables_override_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("QA_BASE_URL", "https://shop.example.com")
    monkeypatch.setenv("QA_REQUEST_TIMEOUT", "5")

    settings = Settings(_env_file=None)  # type: ignore[call-arg]

    assert str(settings.base_url) == "https://shop.example.com/"
    assert settings.request_timeout == 5


@pytest.mark.parametrize("timeout", ["0", "-1"])
def test_non_positive_timeouts_are_rejected(
    monkeypatch: pytest.MonkeyPatch, timeout: str
) -> None:
    monkeypatch.setenv("QA_WAIT_TIMEOUT", timeout)

    with pytest.raises(ValidationError):
        Settings(_env_file=None)  # type: ignore[call-arg]
