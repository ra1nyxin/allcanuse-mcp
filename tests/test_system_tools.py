from __future__ import annotations

import os
import unittest

from allcanuse_mcp.tools import system as system_tools


class DummyMCP:
    def tool(self, **_kwargs):
        def decorator(func):
            setattr(self, func.__name__, func)
            return func

        return decorator


class SystemToolTests(unittest.TestCase):
    def setUp(self) -> None:
        self.mcp = DummyMCP()
        system_tools.register(self.mcp)

    def test_get_env_selected_names(self) -> None:
        os.environ["ALLCANUSE_TEST_ENV"] = "ok"
        result = self.mcp.get_env(names=["ALLCANUSE_TEST_ENV", "DOES_NOT_EXIST"])
        self.assertEqual(result["variables"]["ALLCANUSE_TEST_ENV"], "ok")
        self.assertIsNone(result["variables"]["DOES_NOT_EXIST"])


if __name__ == "__main__":
    unittest.main()
