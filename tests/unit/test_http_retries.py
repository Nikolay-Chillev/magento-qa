"""Retries on dropped connections, against a local socket server that closes them."""

import socket
import threading
from collections.abc import Iterator

import pytest
import requests

from magento_qa.api.http import HttpClient


class DroppingServer:
    """Listens on 127.0.0.1 and closes the first ``drops`` connections without answering."""

    def __init__(self, drops: int) -> None:
        self.drops = drops
        self.requests = 0
        self._socket = socket.create_server(("127.0.0.1", 0))
        self._thread = threading.Thread(target=self._serve, daemon=True)
        self._thread.start()

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self._socket.getsockname()[1]}/"

    def _serve(self) -> None:
        while True:
            try:
                connection, _ = self._socket.accept()
            except OSError:  # closed by close()
                return
            with connection:
                connection.recv(65536)
                self.requests += 1
                if self.requests > self.drops:
                    connection.sendall(
                        b"HTTP/1.1 200 OK\r\nContent-Length: 2\r\nConnection: close\r\n\r\nok"
                    )

    def close(self) -> None:
        self._socket.close()
        self._thread.join(timeout=1)


@pytest.fixture
def server(request: pytest.FixtureRequest) -> Iterator[DroppingServer]:
    dropping = DroppingServer(drops=request.param)
    yield dropping
    dropping.close()


@pytest.mark.parametrize("server", [1], indirect=True)
def test_a_get_is_retried_when_the_connection_drops(server: DroppingServer) -> None:
    response = HttpClient(server.url, timeout=2).get("api/v1/search")

    assert response.text == "ok"
    assert server.requests == 2


@pytest.mark.parametrize("server", [1], indirect=True)
def test_a_post_is_not_sent_twice(server: DroppingServer) -> None:
    with pytest.raises(requests.ConnectionError):
        HttpClient(server.url, timeout=2).post("rest/V1/guest-carts")

    assert server.requests == 1


@pytest.mark.parametrize("server", [10], indirect=True)
def test_a_get_gives_up_after_two_retries(server: DroppingServer) -> None:
    with pytest.raises(requests.ConnectionError):
        HttpClient(server.url, timeout=2).get("api/v1/search")

    assert server.requests == 3
