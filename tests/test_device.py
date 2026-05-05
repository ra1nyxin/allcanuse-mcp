from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from mcp.types import CallToolResult

from allcanuse_mcp.core import device
from allcanuse_mcp.tools import device as device_tools


class FakeCapture:
    def __init__(self, opened: bool = True, frame=None, raises_on_read: Exception | None = None) -> None:
        self._opened = opened
        self._frame = frame
        self._raises_on_read = raises_on_read
        self.released = False

    def isOpened(self) -> bool:
        return self._opened

    def get(self, _prop: int) -> float:
        return 640.0

    def read(self):
        if self._raises_on_read is not None:
            raise self._raises_on_read
        return True, self._frame

    def release(self) -> None:
        self.released = True


class FakeFrame:
    shape = (480, 640, 3)

    def mean(self) -> float:
        return 120.0


class FakeBlackFrame(FakeFrame):
    def mean(self) -> float:
        return 0.0


class FakeCV2:
    CAP_DSHOW = 700
    CAP_MSMF = 1400
    CAP_V4L2 = 200
    CAP_ANY = 0
    CAP_PROP_FRAME_WIDTH = 3
    CAP_PROP_FRAME_HEIGHT = 4
    CAP_PROP_FPS = 5

    def __init__(self, captures: list[FakeCapture]) -> None:
        self._captures = captures
        self.imwrite_calls: list[str] = []

    def VideoCapture(self, _index: int, _backend: int | None = None):
        return self._captures.pop(0)

    def imwrite(self, path: str, _frame) -> bool:
        self.imwrite_calls.append(path)
        Path(path).write_bytes(b"fake")
        return True

    def imread(self, path: str):
        if Path(path).exists():
            return FakeFrame()
        return None


class DeviceTests(unittest.TestCase):
    def test_list_cameras_without_opencv_returns_backend_hints(self) -> None:
        with patch.object(device, "cv2", None), patch("allcanuse_mcp.core.device.platform.system", return_value="Linux"):
            result = device.list_cameras()
        self.assertFalse(result["ok"])
        self.assertEqual(result["missing_python_package"], "opencv-python")
        self.assertIn("available_backends", result)

    def test_list_cameras_uses_opencv_when_available(self) -> None:
        fake_cv2 = FakeCV2([FakeCapture(frame=FakeFrame()), FakeCapture(opened=False)])
        with (
            patch.object(device, "cv2", fake_cv2),
            patch("allcanuse_mcp.core.device.platform.system", return_value="Windows"),
        ):
            result = device.list_cameras(max_devices=2)
        self.assertTrue(result["ok"])
        self.assertGreaterEqual(result["count"], 1)
        self.assertIn("opencv", result["backends_used"])

    def test_list_cameras_linux_fallback_reads_dev_video_entries(self) -> None:
        class FakeGlobPath:
            def __init__(self, value: str) -> None:
                self.name = Path(value).name
                self._value = value

            def __str__(self) -> str:
                return self._value

        class FakeSysFile:
            def exists(self) -> bool:
                return True

            def read_text(self, encoding: str = "utf-8", errors: str = "replace") -> str:
                return "Integrated Camera\n"

        class FakeSysDir:
            def joinpath(self, _name: str):
                return FakeSysFile()

        with (
            patch.object(device, "cv2", None),
            patch("allcanuse_mcp.core.device.platform.system", return_value="Linux"),
            patch("allcanuse_mcp.core.device.Path.glob", return_value=[FakeGlobPath("/dev/video0")]),
            patch("allcanuse_mcp.core.device.Path", side_effect=lambda *parts: FakeSysDir() if str(parts[0]).startswith("/sys/class/video4linux") else Path(*parts)),
        ):
            result = device.list_cameras(max_devices=4)
        self.assertTrue(result["ok"])
        self.assertEqual(result["count"], 1)
        self.assertEqual(result["cameras"][0]["device"], "/dev/video0")

    def test_capture_camera_photo_handles_runtime_error(self) -> None:
        fake_cv2 = FakeCV2([FakeCapture(raises_on_read=RuntimeError("boom"))])
        with patch.object(device, "cv2", fake_cv2):
            result = device.capture_camera_photo()
        self.assertFalse(result["ok"])
        self.assertIn("Unable to capture", result["error"])
        self.assertTrue(any("boom" in attempt["error"] for attempt in result["attempts"]))

    def test_capture_camera_photo_saves_file(self) -> None:
        fake_cv2 = FakeCV2([FakeCapture(frame=FakeFrame())])
        output = Path(tempfile.gettempdir(), "allcanuse-camera-test.png")
        if output.exists():
            output.unlink()
        with patch.object(device, "cv2", fake_cv2):
            result = device.capture_camera_photo(output_path=str(output))
        self.assertTrue(result["ok"])
        self.assertIn(result["backend"], {"opencv", "opencv-dshow", "opencv-msmf", "opencv-v4l2"})
        self.assertTrue(output.exists())
        output.unlink()

    def test_capture_camera_photo_retries_opencv_backend_when_first_frame_is_black(self) -> None:
        fake_cv2 = FakeCV2(
            [
                FakeCapture(frame=FakeBlackFrame()),
                FakeCapture(frame=FakeFrame()),
            ]
        )
        output = Path(tempfile.gettempdir(), "allcanuse-camera-retry-test.png")
        if output.exists():
            output.unlink()
        with (
            patch.object(device, "cv2", fake_cv2),
            patch("allcanuse_mcp.core.device.platform.system", return_value="Windows"),
        ):
            result = device.capture_camera_photo(output_path=str(output))
        self.assertTrue(result["ok"])
        self.assertIn(result["backend"], {"opencv-msmf", "opencv"})
        self.assertTrue(any(item["backend"] == "opencv-dshow" for item in result.get("fallback_attempts", [])))
        output.unlink(missing_ok=True)

    def test_capture_camera_photo_uses_ffmpeg_fallback_on_linux(self) -> None:
        output = Path(tempfile.gettempdir(), "allcanuse-camera-ffmpeg-test.png")
        if output.exists():
            output.unlink()

        def fake_run(command: list[str], *, timeout_ms: int = 30_000):
            output.write_bytes(b"ffmpeg")
            return {"ok": True, "stdout": "", "stderr": "", "returncode": 0}

        with (
            patch.object(device, "cv2", None),
            patch("allcanuse_mcp.core.device.platform.system", return_value="Linux"),
            patch("allcanuse_mcp.core.device.shutil.which", side_effect=lambda name: "ffmpeg" if name == "ffmpeg" else None),
            patch("allcanuse_mcp.core.device._run_command_capture", side_effect=fake_run),
        ):
            result = device.capture_camera_photo(output_path=str(output))
        self.assertTrue(result["ok"])
        self.assertEqual(result["backend"], "ffmpeg")
        output.unlink(missing_ok=True)

    def test_capture_camera_photo_tool_can_return_image_content(self) -> None:
        class DummyMCP:
            def tool(self, **_kwargs):
                def decorator(func):
                    setattr(self, func.__name__, func)
                    return func

                return decorator

        fake_cv2 = FakeCV2([FakeCapture(frame=FakeFrame())])
        output = Path(tempfile.gettempdir(), "allcanuse-camera-tool-test.png")
        if output.exists():
            output.unlink()
        mcp = DummyMCP()
        device_tools.register(mcp)
        with patch.object(device, "cv2", fake_cv2), patch("allcanuse_mcp.core.device.cv2", fake_cv2):
            result = mcp.capture_camera_photo(output_path=str(output), return_image_content=True)
        self.assertIsInstance(result, CallToolResult)
        self.assertEqual(result.content[-1].type, "image")
        output.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
