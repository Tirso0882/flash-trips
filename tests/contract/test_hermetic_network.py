import socket

import pytest
from pytest_socket import SocketBlockedError


def test_ordinary_tests_reject_live_network_access() -> None:
    with (
        pytest.warns(UserWarning, match="tried to use socket"),
        pytest.raises(SocketBlockedError),
    ):
        socket.socket()
