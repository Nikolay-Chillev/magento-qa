"""Errors returned by the Magento REST API."""

import re
from collections.abc import Mapping, Sequence
from typing import Any

import requests


class MagentoApiError(Exception):
    """A non-2xx response from Magento, with its message in readable form."""

    def __init__(self, status: int, message: str) -> None:
        super().__init__(f"HTTP {status}: {message}")
        self.status = status
        self.message = message


def render_message(message: str, parameters: Mapping[str, Any] | Sequence[Any] | None) -> str:
    """Fill Magento's placeholders: ``%1``, ``%2`` for a list, ``%name`` for a mapping."""
    if not parameters:
        return message
    if isinstance(parameters, Mapping):
        values = {str(key): value for key, value in parameters.items()}
    else:
        values = {str(index): value for index, value in enumerate(parameters, start=1)}
    return re.sub(
        r"%(\w+)",
        lambda match: str(values.get(match.group(1), match.group(0))),
        message,
    )


def raise_for_magento_error(response: requests.Response) -> None:
    """Raise MagentoApiError for a non-2xx response; do nothing otherwise."""
    if response.ok:
        return
    try:
        body = response.json()
    except ValueError:
        raise MagentoApiError(response.status_code, response.text[:500]) from None
    if not isinstance(body, dict):
        raise MagentoApiError(response.status_code, str(body))
    message = render_message(str(body.get("message", "")), body.get("parameters"))
    raise MagentoApiError(response.status_code, message)
