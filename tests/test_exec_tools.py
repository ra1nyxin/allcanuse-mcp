from __future__ import annotations

import socket
import threading
import unittest
from unittest.mock import patch

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

    def test_find_port_process_linux_fallback_without_psutil(self) -> None:
        expected = {"found": True, "port": 8000, "pid": 123}
        with patch.object(exec_tools, "psutil", None), patch.object(
            exec_tools.linux_fallbacks,
            "linux_procfs_available",
            return_value=True,
        ), patch.object(
            exec_tools.linux_fallbacks,
            "find_port_process",
            return_value=expected,
        ):
            result = self.mcp.find_port_process(8000)
        self.assertEqual(result, expected)

    def test_get_process_tree_linux_fallback_without_psutil(self) -> None:
        expected = {"root": {"pid": 1}, "children": []}
        with patch.object(exec_tools, "psutil", None), patch.object(
            exec_tools.linux_fallbacks,
            "linux_procfs_available",
            return_value=True,
        ), patch.object(
            exec_tools.linux_fallbacks,
            "get_process_tree",
            return_value=expected,
        ):
            result = self.mcp.get_process_tree(pid=1, max_depth=2)
        self.assertEqual(result, expected)


if __name__ == "__main__":
    unittest.main()
