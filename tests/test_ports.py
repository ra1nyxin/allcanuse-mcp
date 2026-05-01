from __future__ import annotations

import socket
import unittest
from unittest.mock import patch

from allcanuse_mcp.core.networking import list_listening_ports
from allcanuse_mcp.core import networking


class PortListingTests(unittest.TestCase):
    def test_list_listening_ports_contains_bound_socket(self) -> None:
        listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        listener.bind(("127.0.0.1", 0))
        listener.listen(1)
        port = listener.getsockname()[1]
        try:
            result = list_listening_ports()
            ports = [item["port"] for item in result["listeners"]]
            self.assertIn(port, ports)
        finally:
            listener.close()

    def test_list_listening_ports_linux_fallback_without_psutil(self) -> None:
        expected = {"count": 1, "listeners": [{"ip": "127.0.0.1", "port": 9000, "pid": 321}]}
        real_import = __import__

        def fake_import(name, *args, **kwargs):
            if name == "psutil":
                raise ImportError("psutil missing")
            return real_import(name, *args, **kwargs)

        with patch.object(networking, "os") as mocked_os, patch.object(
            networking.linux_fallbacks,
            "list_listening_ports",
            return_value=expected,
        ), patch("builtins.__import__", side_effect=fake_import):
            mocked_os.name = "posix"
            result = list_listening_ports()
        self.assertEqual(result, expected)


if __name__ == "__main__":
    unittest.main()
