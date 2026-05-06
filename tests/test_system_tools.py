from __future__ import annotations

import os
import unittest
from unittest.mock import patch

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

    def test_get_system_info_linux_fallback_without_psutil(self) -> None:
        with patch.object(system_tools, "psutil", None), patch.object(
            system_tools.linux_fallbacks,
            "linux_procfs_available",
            return_value=True,
        ), patch.object(
            system_tools.linux_fallbacks,
            "get_virtual_memory",
            return_value={"total": 1000, "available": 400, "percent": 60.0},
        ), patch.object(
            system_tools.linux_fallbacks,
            "get_cpu_count_physical",
            return_value=4,
        ), patch.object(
            system_tools.linux_fallbacks,
            "get_boot_time",
            return_value=1_700_000_000.0,
        ):
            result = self.mcp.get_system_info()
        self.assertEqual(result["memory_total"], 1000)
        self.assertEqual(result["memory_available"], 400)
        self.assertEqual(result["cpu_count_physical"], 4)
        self.assertIsNotNone(result["boot_time"])

    def test_list_network_adapters_linux_fallback_without_psutil(self) -> None:
        expected = {"count": 1, "adapters": [{"name": "eth0", "addresses": []}]}
        with patch.object(system_tools, "psutil", None), patch.object(
            system_tools.linux_fallbacks,
            "linux_procfs_available",
            return_value=True,
        ), patch.object(
            system_tools.linux_fallbacks,
            "list_network_adapters",
            return_value=expected,
        ):
            result = system_tools._collect_network_adapters()
        self.assertEqual(result, expected)

    def test_get_network_config_linux_returns_adapter_snapshot_when_commands_fail(self) -> None:
        expected = {"count": 1, "adapters": [{"name": "eth0", "addresses": []}]}

        def failed_shell(*_args, **_kwargs):
            return {"ok": False, "returncode": 127, "stdout": "", "stderr": "missing command"}

        with patch.object(system_tools.platform, "system", return_value="Linux"), patch.object(
            system_tools,
            "run_shell",
            side_effect=failed_shell,
        ), patch.object(
            system_tools.linux_fallbacks,
            "linux_procfs_available",
            return_value=True,
        ), patch.object(
            system_tools.linux_fallbacks,
            "list_network_adapters",
            return_value=expected,
        ):
            result = system_tools._get_network_config(max_output_chars=4000, timeout_ms=1000)

        self.assertTrue(result["ok"])
        self.assertEqual(result["fallback_backend"], "procfs_snapshot")
        self.assertEqual(result["network_adapters"], expected)
        self.assertEqual([item["backend"] for item in result["attempts"]], ["ip", "ifconfig"])

    def test_get_network_config_windows_falls_back_to_powershell(self) -> None:
        with patch.object(system_tools.platform, "system", return_value="Windows"), patch.object(
            system_tools,
            "run_cmd",
            return_value={"ok": False, "returncode": 1, "stdout": "", "stderr": "ipconfig failed"},
        ), patch.object(
            system_tools,
            "run_powershell",
            return_value={"ok": True, "returncode": 0, "stdout": "adapter", "stderr": ""},
        ), patch.object(
            system_tools,
            "_collect_network_adapters",
            return_value={"count": 0, "adapters": []},
        ):
            result = system_tools._get_network_config(max_output_chars=4000, timeout_ms=1000)

        self.assertTrue(result["ok"])
        self.assertEqual(result["command"], "Get-NetIPConfiguration | Get-NetRoute")
        self.assertEqual([item["backend"] for item in result["attempts"]], ["ipconfig", "powershell"])


if __name__ == "__main__":
    unittest.main()
