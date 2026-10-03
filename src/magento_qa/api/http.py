"""Thin HTTP client shared by the Magento and Mailpit clients."""

import contextlib
import json
from collections.abc import Mapping
from typing import Any
from urllib.parse import urljoin

import allure
import requests

MASK = "***"
SENSITIVE_HEADERS = frozenset({"authorization", "cookie", "set-cookie"})
MAX_BODY_CHARS = 20_000


class HttpClient:
    """A requests session bound to a base URL.

    Every exchange becomes an Allure step with the request and response attached,
    so a failing test shows exactly what was sent and received.
    """

    def __init__(self, base_url: str, *, timeout: float) -> None:
        self.base_url = base_url if base_url.endswith("/") else f"{base_url}/"
        self.timeout = timeout
        self.session = requests.Session()

    def url(self, path: str) -> str:
        """Resolve ``path`` against the base URL; a leading slash is ignored."""
        return urljoin(self.base_url, path.lstrip("/"))

    def request(
        self, method: str, path: str, *, redact_response: bool = False, **kwargs: Any
    ) -> requests.Response:
        """Send a request; ``redact_response`` keeps a secret body (e.g. a token) out of reports."""
        kwargs.setdefault("timeout", self.timeout)
        with allure.step(f"{method} /{path.lstrip('/')}"):
            response = self.session.request(method, self.url(path), **kwargs)
            allure.attach(
                format_exchange(response, redact_response=redact_response),
                name=f"{method} {response.status_code}",
                attachment_type=allure.attachment_type.TEXT,
            )
        return response

    def get(self, path: str, **kwargs: Any) -> requests.Response:
        return self.request("GET", path, **kwargs)

    def post(self, path: str, **kwargs: Any) -> requests.Response:
        return self.request("POST", path, **kwargs)

    def put(self, path: str, **kwargs: Any) -> requests.Response:
        return self.request("PUT", path, **kwargs)

    def delete(self, path: str, **kwargs: Any) -> requests.Response:
        return self.request("DELETE", path, **kwargs)


def format_exchange(response: requests.Response, *, redact_response: bool = False) -> str:
    """Render the request and response as readable text, with credentials masked."""
    request = response.request
    lines = [f"{request.method} {request.url}", *_format_headers(request.headers)]
    if request.body:
        lines += ["", _format_body(request.body)]
    lines += [
        "",
        f"HTTP {response.status_code} {response.reason}",
        *_format_headers(response.headers),
        "",
        MASK if redact_response else _format_body(response.text),
    ]
    return "\n".join(lines)


def _format_headers(headers: Mapping[str, str]) -> list[str]:
    return [
        f"{name}: {MASK if name.lower() in SENSITIVE_HEADERS else value}"
        for name, value in headers.items()
    ]


def _format_body(body: str | bytes) -> str:
    text = body.decode("utf-8", "replace") if isinstance(body, bytes) else body
    with contextlib.suppress(ValueError):  # not JSON: keep the text as it is
        text = json.dumps(_mask_secrets(json.loads(text)), indent=2, ensure_ascii=False)
    if len(text) > MAX_BODY_CHARS:
        return f"{text[:MAX_BODY_CHARS]}\n... ({len(text) - MAX_BODY_CHARS} more characters)"
    return text


def _mask_secrets(value: Any) -> Any:
    """Replace the value of every key that contains 'password'."""
    if isinstance(value, dict):
        return {
            key: MASK if "password" in key.lower() else _mask_secrets(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_mask_secrets(item) for item in value]
    return value
