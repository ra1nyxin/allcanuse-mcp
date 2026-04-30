from __future__ import annotations

import platform
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any

try:
    import cv2
except ImportError:
    cv2 = None


def _camera_backend() -> int | None:
    if cv2 is None:
        return None
    if platform.system() == "Windows" and hasattr(cv2, "CAP_DSHOW"):
        return cv2.CAP_DSHOW
    return getattr(cv2, "CAP_ANY", 0)


def list_cameras(*, max_devices: int = 8) -> dict[str, Any]:
    if cv2 is None:
        return {
            "ok": False,
            "error": "OpenCV is not installed.",
            "missing_python_package": "opencv-python",
            "hint": "Install `opencv-python` if the current task requires camera access.",
        }

    backend = _camera_backend()
    cameras: list[dict[str, Any]] = []
    for index in range(max(1, max_devices)):
        capture = None
        try:
            capture = cv2.VideoCapture(index, backend) if backend is not None else cv2.VideoCapture(index)
            if not capture.isOpened():
                continue
            width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
            fps = capture.get(cv2.CAP_PROP_FPS)
            cameras.append(
                {
                    "index": index,
                    "width": width,
                    "height": height,
                    "fps": fps,
                }
            )
        except Exception as exc:
            cameras.append(
                {
                    "index": index,
                    "error": str(exc),
                }
            )
        finally:
            if capture is not None:
                capture.release()

    return {
        "ok": True,
        "platform": platform.system(),
        "backend": "opencv",
        "count": len(cameras),
        "cameras": cameras,
    }


def capture_camera_photo(camera_index: int = 0, output_path: str | None = None) -> dict[str, Any]:
    if cv2 is None:
        return {
            "ok": False,
            "error": "OpenCV is not installed.",
            "missing_python_package": "opencv-python",
            "hint": "Install `opencv-python` if the current task requires camera capture.",
        }

    backend = _camera_backend()
    capture = None
    try:
        capture = cv2.VideoCapture(camera_index, backend) if backend is not None else cv2.VideoCapture(camera_index)
        if not capture.isOpened():
            return {
                "ok": False,
                "error": f"Camera {camera_index} could not be opened.",
                "camera_index": camera_index,
            }
        ok, frame = capture.read()
        if not ok or frame is None:
            return {
                "ok": False,
                "error": f"Failed to read a frame from camera {camera_index}.",
                "camera_index": camera_index,
            }

        if output_path:
            target = Path(output_path).expanduser().resolve()
            target.parent.mkdir(parents=True, exist_ok=True)
        else:
            filename = f"camera-{camera_index}-{datetime.now().strftime('%Y%m%d-%H%M%S')}.png"
            target = Path(tempfile.gettempdir(), filename).resolve()

        saved = cv2.imwrite(str(target), frame)
        if not saved:
            return {"ok": False, "error": "OpenCV failed to save the captured frame.", "path": str(target)}

        height, width = frame.shape[:2]
        return {
            "ok": True,
            "platform": platform.system(),
            "backend": "opencv",
            "camera_index": camera_index,
            "path": str(target),
            "width": int(width),
            "height": int(height),
            "file_size": target.stat().st_size,
        }
    except Exception as exc:
        return {
            "ok": False,
            "error": str(exc),
            "camera_index": camera_index,
            "backend": "opencv",
        }
    finally:
        if capture is not None:
            capture.release()
