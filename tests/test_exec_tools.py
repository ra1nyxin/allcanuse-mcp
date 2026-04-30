from __future__ import annotations

import socket
import threading
import unittest

from allcanuse_mcp.tools import exec as exec_tools


class DummyMCP:
    def tool(self, **_kwargs):
        def decorator(func):
            setattr(self, func.__name__, func)
            return func

        return decorator


class ExecToolTests(unittest.TestCase):
    def setUp(self) -> None:
        self.mcp = DummyMCP()
        exec_tools.register(self.mcp)

    def test_get_process_tree_current_process(self) -> None:
        result = self.mcp.get_process_tree(max_depth=1)
        self.assertIn("root", result)
        self.assertIn("pid", result["root"])

    def test_find_port_process(self) -> None:
        listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        listener.bind(("127.0.0.1", 0))
        listener.listen(1)
        port = listener.getsockname()[1]

        def accept_once() -> None:
            conn, _ = listener.accept()
            conn.close()
            listener.close()

        thread = threading.Thread(target=accept_once, daemon=True)
        thread.start()

        probe = socket.create_connection(("127.0.0.1", port), timeout=1)
        result = self.mcp.find_port_process(port)
        probe.close()
        thread.join(timeout=1)

        self.assertTrue(result["found"])
        self.assertEqual(result["port"], port)


if __name__ == "__main__":
    unittest.main()
