from __future__ import annotations

import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from mcp.types import CallToolResult

from allcanuse_mcp.core import windows
from allcanuse_mcp.tools import windows as window_tools


class WindowsCoreTests(unittest.TestCase):
    def test_list_windows_linux_requires_display(self) -> None:
        with patch.object(windows.platform, "system", return_value="Linux"), patch.dict(
            windows.os.environ, {}, clear=True
        ):
            result = windows.list_windows_info()
        self.assertFalse(result["ok"])
        self.assertIn("graphical", result["error"])

    def test_active_window_linux_without_xprop(self) -> None:
        with patch.object(windows.platform, "system", return_value="Linux"), patch.dict(
            windows.os.environ, {"DISPLAY": ":0"}, clear=True
        ), patch.object(windows.shutil, "which", return_value=None):
            result = windows.get_active_window_info()
        self.assertFalse(result["ok"])
        self.assertEqual(result["missing_command"], "xprop")

    def test_capture_screenshot_headless_linux_returns_hint(self) -> None:
        with patch.object(windows.platform, "system", return_value="Linux"), patch.object(
            windows, "ImageGrab", SimpleNamespace(grab=lambda **_: (_ for _ in ()).throw(RuntimeError("headless")))
        ), patch.object(windows.shutil, "which", return_value=None):
            result = windows.capture_desktop_screenshot()
        self.assertFalse(result["ok"])
        self.assertIn("imagegrab_error", result)

    def test_get_desktop_context_aggregates_foreground_and_background(self) -> None:
        with patch.object(
            windows,
            "get_active_window_info",
            return_value={"ok": True, "platform": "Windows", "found": True, "window": {"title": "Front", "is_foreground": True}},
        ), patch.object(
            windows,
            "list_windows_info",
            return_value={
                "ok": True,
                "platform": "Windows",
                "windows": [
                    {"title": "Front", "is_foreground": True},
                    {"title": "Back1", "is_foreground": False},
                    {"title": "Back2", "is_foreground": False},
                ],
            },
        ):
            result = windows.get_desktop_context()
        self.assertTrue(result["ok"])
        self.assertEqual(result["foreground_window"]["title"], "Front")
        self.assertEqual(result["background_window_count"], 2)

    def test_list_windows_linux_without_xprop_still_returns_windows(self) -> None:
        wmctrl_output = "0x01200001 0 1234 10 20 800 600 host Demo App\n"
        with patch.object(windows.platform, "system", return_value="Linux"), patch.dict(
            windows.os.environ, {"DISPLAY": ":0"}, clear=True
        ), patch.object(
            windows.shutil,
            "which",
            side_effect=lambda name: None if name == "xprop" else "/usr/bin/wmctrl",
        ), patch.object(
            windows.subprocess,
            "run",
            return_value=SimpleNamespace(returncode=0, stdout=wmctrl_output, stderr=""),
        ):
            result = windows.list_windows_info()
        self.assertTrue(result["ok"])
        self.assertEqual(result["count"], 1)
        self.assertIn("foreground_detection_warning", result)

    def test_list_windows_windows_skips_bad_window(self) -> None:
        fake_gui = SimpleNamespace(
            GetForegroundWindow=lambda: 1,
            EnumWindows=lambda callback, _: [callback(1, 0), callback(2, 0)],
        )
        with patch.object(windows.platform, "system", return_value="Windows"), patch.object(
            windows, "win32gui", fake_gui
        ), patch.object(
            windows, "win32process", SimpleNamespace()
        ), patch.object(
            windows,
            "_window_info",
            side_effect=[
                {"hwnd": 1, "title": "Good", "visible": True, "pid": 10, "process_name": "ok.exe", "process_exe": "C:\\ok.exe", "rect": {}},
                RuntimeError("bad hwnd"),
            ],
        ):
            result = windows.list_windows_info()
        self.assertTrue(result["ok"])
        self.assertEqual(result["count"], 1)
        self.assertEqual(result["skipped_count"], 1)

    def test_capture_screenshot_tool_can_return_image_content(self) -> None:
        class DummyMCP:
            def tool(self, **_kwargs):
                def decorator(func):
                    setattr(self, func.__name__, func)
                    return func

                return decorator

        mcp = DummyMCP()
        window_tools.register(mcp)
        fake_result = {
            "ok": True,
            "platform": "Linux",
            "path": "C:/tmp/test-screenshot.png",
            "width": 800,
            "height": 600,
        }
        with patch.object(window_tools, "capture_desktop_screenshot", return_value=fake_result), patch(
            "allcanuse_mcp.core.vision_payloads.Path.resolve",
            return_value=Path("C:/tmp/test-screenshot.png"),
        ), patch(
            "builtins.open",
            create=True,
        ) as mocked_open:
            mocked_open.return_value.__enter__.return_value.read.return_value = b"fakepng"
            result = mcp.capture_screenshot(return_image_content=True)
        self.assertIsInstance(result, CallToolResult)
        self.assertEqual(result.content[-1].type, "image")


if __name__ == "__main__":
    unittest.main()
