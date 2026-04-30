from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from allcanuse_mcp.core import device


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


class FakeCV2:
    CAP_DSHOW = 700
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


class DeviceTests(unittest.TestCase):
    def test_list_cameras_without_opencv(self) -> None:
        with patch.object(device, "cv2", None):
            result = device.list_cameras()
        self.assertFalse(result["ok"])
        self.assertEqual(result["missing_python_package"], "opencv-python")

    def test_capture_camera_photo_handles_runtime_error(self) -> None:
        fake_cv2 = FakeCV2([FakeCapture(raises_on_read=RuntimeError("boom"))])
        with patch.object(device, "cv2", fake_cv2):
            result = device.capture_camera_photo()
        self.assertFalse(result["ok"])
        self.assertIn("boom", result["error"])

    def test_capture_camera_photo_saves_file(self) -> None:
        fake_cv2 = FakeCV2([FakeCapture(frame=FakeFrame())])
        output = Path(tempfile.gettempdir(), "allcanuse-camera-test.png")
        if output.exists():
            output.unlink()
        with patch.object(device, "cv2", fake_cv2):
            result = device.capture_camera_photo(output_path=str(output))
        self.assertTrue(result["ok"])
        self.assertTrue(output.exists())
        output.unlink()


if __name__ == "__main__":
    unittest.main()
