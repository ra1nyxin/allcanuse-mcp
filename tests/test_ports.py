from __future__ import annotations

import socket
import unittest

from allcanuse_mcp.core.networking import list_listening_ports


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


if __name__ == "__main__":
    unittest.main()
