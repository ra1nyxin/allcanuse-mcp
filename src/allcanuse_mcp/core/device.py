from __future__ import annotations

import json
import platform
import shutil
import subprocess
import tempfile
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from allcanuse_mcp.core.command_runner import run_powershell

try:
    import cv2
except ImportError:
    cv2 = None


def _camera_backend() -> int | None:
    if cv2 is None:
        return None
    system = platform.system()
    if system == "Windows" and hasattr(cv2, "CAP_DSHOW"):
        return cv2.CAP_DSHOW
    if system == "Linux" and hasattr(cv2, "CAP_V4L2"):
        return cv2.CAP_V4L2
    return getattr(cv2, "CAP_ANY", 0)


def _opencv_backend_candidates() -> list[tuple[str, int | None]]:
    if cv2 is None:
        return []
    candidates: list[tuple[str, int | None]] = []
    seen: set[int | None] = set()

    def add_candidate(name: str, backend: int | None) -> None:
        if backend in seen:
            return
        seen.add(backend)
        candidates.append((name, backend))

    system = platform.system()
    if system == "Windows":
        if hasattr(cv2, "CAP_DSHOW"):
            add_candidate("opencv-dshow", cv2.CAP_DSHOW)
        if hasattr(cv2, "CAP_MSMF"):
            add_candidate("opencv-msmf", cv2.CAP_MSMF)
    elif system == "Linux":
        if hasattr(cv2, "CAP_V4L2"):
            add_candidate("opencv-v4l2", cv2.CAP_V4L2)

    add_candidate("opencv", _camera_backend())
    return candidates


def _detect_available_camera_backends() -> list[str]:
    backends: list[str] = []
    if cv2 is not None:
        backends.extend(name for name, _ in _opencv_backend_candidates())
    if platform.system() == "Linux":
        if any(Path("/dev").glob("video*")):
            backends.append("linux-devices")
        if shutil.which("ffmpeg"):
            backends.append("ffmpeg")
        if shutil.which("libcamera-still"):
            backends.append("libcamera-still")
        if shutil.which("fswebcam"):
            backends.append("fswebcam")
    elif platform.system() == "Windows":
        backends.append("powershell-cim")
        if shutil.which("ffmpeg"):
            backends.append("ffmpeg-dshow")
    return backends


def _default_output_path(camera_index: int) -> Path:
    filename = f"camera-{camera_index}-{datetime.now().strftime('%Y%m%d-%H%M%S')}.png"
    return Path(tempfile.gettempdir(), filename).resolve()


def _prepare_output_path(output_path: str | None, camera_index: int) -> Path:
    if output_path:
        target = Path(output_path).expanduser().resolve()
        target.parent.mkdir(parents=True, exist_ok=True)
        return target
    return _default_output_path(camera_index)


def _frame_mean_brightness(frame: Any) -> float | None:
    mean_attr = getattr(frame, "mean", None)
    if callable(mean_attr):
        try:
            return float(mean_attr())
        except Exception:
            pass
    if cv2 is not None and hasattr(cv2, "mean"):
        try:
            values = cv2.mean(frame)
            if values:
                channels = [float(value) for value in values[:3]]
                if channels:
                    return sum(channels) / len(channels)
        except Exception:
            return None
    return None


def _is_likely_black_frame(frame: Any) -> bool:
    brightness = _frame_mean_brightness(frame)
    if brightness is None:
        return False
    return brightness <= 3.0


def _validate_saved_photo(path: Path) -> str | None:
    if not path.exists():
        return "Captured photo file was not created."
    if path.stat().st_size <= 0:
        return "Captured photo file is empty."
    if cv2 is not None and hasattr(cv2, "imread"):
        try:
            frame = cv2.imread(str(path))
        except Exception:
            frame = None
        if frame is not None and _is_likely_black_frame(frame):
            return "Captured photo appears to be fully black."
    return None


def _populate_saved_photo_metadata(result: dict[str, Any]) -> dict[str, Any]:
    path_value = result.get("path")
    if not path_value:
        return result
    path = Path(str(path_value))
    if path.exists():
        result["file_size"] = path.stat().st_size
    if cv2 is not None and hasattr(cv2, "imread") and path.exists():
        try:
            frame = cv2.imread(str(path))
        except Exception:
            frame = None
        if frame is not None:
            shape = getattr(frame, "shape", None)
            if shape and len(shape) >= 2:
                result.setdefault("height", int(shape[0]))
                result.setdefault("width", int(shape[1]))
            brightness = _frame_mean_brightness(frame)
            if brightness is not None:
                result["brightness"] = brightness
    return result


def _result_quality_score(result: dict[str, Any]) -> tuple[float, int, int]:
    brightness = float(result.get("brightness") or -1.0)
    width = int(result.get("width") or 0)
    height = int(result.get("height") or 0)
    pixels = width * height
    file_size = int(result.get("file_size") or 0)
    return (brightness, pixels, file_size)


def _candidate_photo_path(target: Path, backend_name: str) -> Path:
    safe_backend = backend_name.replace("/", "-").replace("\\", "-").replace(" ", "-")
    suffix = target.suffix or ".png"
    return target.with_name(f"{target.stem}-{safe_backend}{suffix}")


def _opencv_camera_entry(index: int, backend_name: str, backend: int | None) -> dict[str, Any] | None:
    if cv2 is None:
        return None
    capture = None
    try:
        capture = cv2.VideoCapture(index, backend) if backend is not None else cv2.VideoCapture(index)
        if not capture.isOpened():
            return None
        width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
        fps = capture.get(cv2.CAP_PROP_FPS)
        return {
            "index": index,
            "backend": backend_name,
            "width": width,
            "height": height,
            "fps": fps,
        }
    finally:
        if capture is not None:
            capture.release()


def _opencv_list_cameras(max_devices: int) -> list[dict[str, Any]]:
    cameras: list[dict[str, Any]] = []
    seen_indexes: set[int] = set()
    for backend_name, backend in _opencv_backend_candidates():
        for index in range(max(1, max_devices)):
            if index in seen_indexes:
                continue
            try:
                entry = _opencv_camera_entry(index, backend_name, backend)
                if entry is not None:
                    seen_indexes.add(index)
                    cameras.append(entry)
            except Exception as exc:
                cameras.append({"index": index, "backend": backend_name, "error": str(exc)})
    return cameras


def _normalize_warmup_ms(warmup_ms: int) -> int:
    return max(0, min(int(warmup_ms), 10_000))


def _opencv_capture_camera_photo(
    camera_index: int,
    target: Path,
    backend_name: str,
    backend: int | None,
    *,
    warmup_ms: int = 10_000,
) -> dict[str, Any]:
    capture = None
    warmup_ms = _normalize_warmup_ms(warmup_ms)
    try:
        capture = cv2.VideoCapture(camera_index, backend) if backend is not None else cv2.VideoCapture(camera_index)
        if not capture.isOpened():
            return {
                "ok": False,
                "error": f"Camera {camera_index} could not be opened.",
                "camera_index": camera_index,
                "backend": backend_name,
            }
        warmup_frames_discarded = 0
        if warmup_ms > 0:
            deadline = time.monotonic() + warmup_ms / 1000
            while time.monotonic() < deadline:
                ok, frame = capture.read()
                if ok and frame is not None:
                    warmup_frames_discarded += 1
                time.sleep(0.05)
        frames: list[Any] = []
        for _ in range(5):
            ok, frame = capture.read()
            if ok and frame is not None:
                frames.append(frame)
        if not frames:
            return {
                "ok": False,
                "error": f"Failed to read a frame from camera {camera_index}.",
                "camera_index": camera_index,
                "backend": backend_name,
            }
        frame = max(frames, key=lambda item: _frame_mean_brightness(item) or -1.0)
        brightness = _frame_mean_brightness(frame)
        if _is_likely_black_frame(frame):
            return {
                "ok": False,
                "error": f"Captured frame from camera {camera_index} appears to be fully black.",
                "camera_index": camera_index,
                "backend": backend_name,
                "brightness": brightness,
            }
        saved = cv2.imwrite(str(target), frame)
        if not saved:
            return {
                "ok": False,
                "error": "OpenCV failed to save the captured frame.",
                "path": str(target),
                "camera_index": camera_index,
                "backend": backend_name,
            }
        validation_error = _validate_saved_photo(target)
        if validation_error:
            return {
                "ok": False,
                "error": validation_error,
                "path": str(target),
                "camera_index": camera_index,
                "backend": backend_name,
                "brightness": brightness,
            }
        height, width = frame.shape[:2]
        return {
            "ok": True,
            "platform": platform.system(),
            "backend": backend_name,
            "camera_index": camera_index,
            "path": str(target),
            "width": int(width),
            "height": int(height),
            "file_size": target.stat().st_size,
            "brightness": brightness,
            "warmup_ms": warmup_ms,
            "warmup_frames_discarded": warmup_frames_discarded,
        }
    except Exception as exc:
        return {
            "ok": False,
            "error": str(exc),
            "camera_index": camera_index,
            "backend": backend_name,
        }
    finally:
        if capture is not None:
            capture.release()


def _linux_video_device_entries(max_devices: int) -> list[dict[str, Any]]:
    cameras: list[dict[str, Any]] = []
    for device_path in sorted(Path("/dev").glob("video*")):
        name = device_path.name
        suffix = name.removeprefix("video")
        if not suffix.isdigit():
            continue
        index = int(suffix)
        if index >= max(1, max_devices):
            continue
        sys_dir = Path("/sys/class/video4linux", name)
        entry: dict[str, Any] = {
            "index": index,
            "backend": "linux-devices",
            "device": str(device_path),
        }
        display_name = sys_dir.joinpath("name")
        if display_name.exists():
            try:
                entry["name"] = display_name.read_text(encoding="utf-8", errors="replace").strip()
            except OSError:
                pass
        cameras.append(entry)
    return cameras


def _windows_powershell_camera_entries(max_devices: int) -> list[dict[str, Any]]:
    script = """
$devices = Get-CimInstance Win32_PnPEntity |
  Where-Object {
    ($_.PNPClass -eq 'Camera') -or
    ($_.PNPClass -eq 'Image') -or
    ($_.Service -match 'usbvideo') -or
    ($_.Name -match 'camera|webcam|integrated camera')
  } |
  Select-Object Name, DeviceID, PNPClass, Service -Unique
$devices | ConvertTo-Json -Depth 3 -Compress
""".strip()
    result = run_powershell(script, timeout_ms=20_000, max_output_chars=80_000)
    if not result.get("ok") or not result.get("stdout", "").strip():
        return []
    try:
        parsed = json.loads(result["stdout"])
    except json.JSONDecodeError:
        return []
    if isinstance(parsed, dict):
        parsed = [parsed]
    cameras: list[dict[str, Any]] = []
    for index, item in enumerate(parsed[: max(1, max_devices)]):
        cameras.append(
            {
                "index": index,
                "backend": "powershell-cim",
                "name": item.get("Name"),
                "device_id": item.get("DeviceID"),
                "pnp_class": item.get("PNPClass"),
                "service": item.get("Service"),
            }
        )
    return cameras


def _run_command_capture(command: list[str], *, timeout_ms: int = 30_000) -> dict[str, Any]:
    completed = subprocess.run(
        command,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=max(timeout_ms, 1) / 1000,
        shell=False,
    )
    return {
        "ok": completed.returncode == 0,
        "returncode": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
    }


def _ffmpeg_linux_input(camera_index: int) -> tuple[list[str], str]:
    device = f"/dev/video{camera_index}"
    return ["-f", "video4linux2", "-i", device], device


def _ffmpeg_windows_input(camera_index: int) -> tuple[list[str], str] | None:
    devices = _windows_powershell_camera_entries(max_devices=max(camera_index + 1, 8))
    if camera_index >= len(devices):
        return None
    name = str(devices[camera_index].get("name") or "").replace('"', '\\"')
    if not name:
        return None
    return ["-f", "dshow", "-i", f"video={name}"], name


def _ffmpeg_capture_camera_photo(camera_index: int, target: Path, *, warmup_ms: int = 10_000) -> dict[str, Any]:
    warmup_ms = _normalize_warmup_ms(warmup_ms)
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg is None:
        return {"ok": False, "error": "ffmpeg was not found.", "backend": "ffmpeg"}
    system = platform.system()
    if system == "Linux":
        input_args, source = _ffmpeg_linux_input(camera_index)
        backend_name = "ffmpeg"
    elif system == "Windows":
        resolved = _ffmpeg_windows_input(camera_index)
        if resolved is None:
            return {
                "ok": False,
                "error": f"Unable to resolve camera name for Windows camera index {camera_index}.",
                "camera_index": camera_index,
                "backend": "ffmpeg-dshow",
            }
        input_args, source = resolved
        backend_name = "ffmpeg-dshow"
    else:
        return {"ok": False, "error": f"Unsupported platform for ffmpeg camera capture: {system}.", "backend": "ffmpeg"}

    command = [
        ffmpeg,
        "-y",
        "-hide_banner",
        "-loglevel",
        "error",
        *input_args,
        "-ss",
        f"{warmup_ms / 1000:.3f}",
        "-frames:v",
        "1",
        str(target),
    ]
    try:
        result = _run_command_capture(command, timeout_ms=45_000)
    except Exception as exc:
        return {
            "ok": False,
            "error": str(exc),
            "camera_index": camera_index,
            "backend": backend_name,
        }
    if not result.get("ok") or not target.exists():
        return {
            "ok": False,
            "error": (result.get("stderr") or result.get("stdout") or "ffmpeg camera capture failed.").strip(),
            "camera_index": camera_index,
            "backend": backend_name,
            "source": source,
        }
    validation_error = _validate_saved_photo(target)
    if validation_error:
        return {
            "ok": False,
            "error": validation_error,
            "camera_index": camera_index,
            "backend": backend_name,
            "source": source,
        }
    return {
        "ok": True,
        "platform": system,
        "backend": backend_name,
        "camera_index": camera_index,
        "path": str(target),
        "file_size": target.stat().st_size,
        "source": source,
        "warmup_ms": warmup_ms,
    }


def _libcamera_capture_camera_photo(camera_index: int, target: Path, *, warmup_ms: int = 10_000) -> dict[str, Any]:
    warmup_ms = _normalize_warmup_ms(warmup_ms)
    executable = shutil.which("libcamera-still")
    if executable is None:
        return {"ok": False, "error": "libcamera-still was not found.", "backend": "libcamera-still"}
    command = [
        executable,
        "--camera",
        str(camera_index),
        "--nopreview",
        "--timeout",
        str(max(warmup_ms, 1000)),
        "--output",
        str(target),
    ]
    try:
        result = _run_command_capture(command, timeout_ms=30_000)
    except Exception as exc:
        return {
            "ok": False,
            "error": str(exc),
            "camera_index": camera_index,
            "backend": "libcamera-still",
        }
    if not result.get("ok") or not target.exists():
        return {
            "ok": False,
            "error": (result.get("stderr") or result.get("stdout") or "libcamera-still failed.").strip(),
            "camera_index": camera_index,
            "backend": "libcamera-still",
        }
    validation_error = _validate_saved_photo(target)
    if validation_error:
        return {
            "ok": False,
            "error": validation_error,
            "camera_index": camera_index,
            "backend": "libcamera-still",
        }
    return {
        "ok": True,
        "platform": "Linux",
        "backend": "libcamera-still",
        "camera_index": camera_index,
        "path": str(target),
        "file_size": target.stat().st_size,
        "warmup_ms": warmup_ms,
    }


def _fswebcam_capture_camera_photo(camera_index: int, target: Path, *, warmup_ms: int = 10_000) -> dict[str, Any]:
    warmup_ms = _normalize_warmup_ms(warmup_ms)
    executable = shutil.which("fswebcam")
    if executable is None:
        return {"ok": False, "error": "fswebcam was not found.", "backend": "fswebcam"}
    device_path = f"/dev/video{camera_index}"
    command = [
        executable,
        "--no-banner",
        "--delay",
        str(warmup_ms / 1000),
        "-d",
        device_path,
        str(target),
    ]
    try:
        result = _run_command_capture(command, timeout_ms=30_000)
    except Exception as exc:
        return {
            "ok": False,
            "error": str(exc),
            "camera_index": camera_index,
            "backend": "fswebcam",
        }
    if not result.get("ok") or not target.exists():
        return {
            "ok": False,
            "error": (result.get("stderr") or result.get("stdout") or "fswebcam failed.").strip(),
            "camera_index": camera_index,
            "backend": "fswebcam",
            "device": device_path,
        }
    validation_error = _validate_saved_photo(target)
    if validation_error:
        return {
            "ok": False,
            "error": validation_error,
            "camera_index": camera_index,
            "backend": "fswebcam",
            "device": device_path,
        }
    return {
        "ok": True,
        "platform": "Linux",
        "backend": "fswebcam",
        "camera_index": camera_index,
        "path": str(target),
        "file_size": target.stat().st_size,
        "device": device_path,
        "warmup_ms": warmup_ms,
    }


def list_cameras(*, max_devices: int = 8) -> dict[str, Any]:
    max_devices = max(1, max_devices)
    system = platform.system()
    cameras: list[dict[str, Any]] = []
    seen_keys: set[tuple[Any, ...]] = set()
    backends_used: list[str] = []

    def add_entries(entries: list[dict[str, Any]]) -> None:
        for entry in entries:
            if entry.get("index") is not None:
                key = ("index", entry.get("index"))
            else:
                key = (
                    "identity",
                    entry.get("device"),
                    entry.get("device_id"),
                    entry.get("name"),
                )
            if key in seen_keys:
                continue
            seen_keys.add(key)
            cameras.append(entry)

    if cv2 is not None:
        backends_used.append("opencv")
        add_entries(_opencv_list_cameras(max_devices))

    if system == "Linux":
        linux_entries = _linux_video_device_entries(max_devices)
        if linux_entries:
            backends_used.append("linux-devices")
            add_entries(linux_entries)
    elif system == "Windows":
        ps_entries = _windows_powershell_camera_entries(max_devices)
        if ps_entries:
            backends_used.append("powershell-cim")
            add_entries(ps_entries)

    available_backends = _detect_available_camera_backends()
    if cameras:
        return {
            "ok": True,
            "platform": system,
            "backends_used": backends_used,
            "available_backends": available_backends,
            "count": len(cameras),
            "cameras": sorted(cameras, key=lambda item: int(item.get("index", 0))),
        }

    result: dict[str, Any] = {
        "ok": False,
        "platform": system,
        "error": "No accessible cameras were detected.",
        "available_backends": available_backends,
        "checked_backends": backends_used,
    }
    if cv2 is None:
        result["missing_python_package"] = "opencv-python"
        result["hint"] = "Install `opencv-python`, or use a host with ffmpeg / libcamera-still / fswebcam / PowerShell camera access."
    return result


def capture_camera_photo(camera_index: int = 0, output_path: str | None = None, warmup_ms: int = 10_000) -> dict[str, Any]:
    target = _prepare_output_path(output_path, camera_index)
    warmup_ms = _normalize_warmup_ms(warmup_ms)
    attempts: list[dict[str, Any]] = []
    successes: list[dict[str, Any]] = []
    system = platform.system()

    def try_backend(name: str, func) -> dict[str, Any] | None:
        try:
            result = func()
        except Exception as exc:
            result = {"ok": False, "error": str(exc), "backend": name, "camera_index": camera_index}
        if result is None:
            return None
        if result.get("ok"):
            result = _populate_saved_photo_metadata(result)
            result.setdefault("platform", system)
            result.setdefault("camera_index", camera_index)
            successes.append(result)
            return result
        attempts.append(
            {
                "backend": name,
                "error": result.get("error", "unknown error"),
            }
        )
        return None

    if cv2 is not None:
        for backend_name, backend in _opencv_backend_candidates():
            candidate_target = _candidate_photo_path(target, backend_name)
            try_backend(
                backend_name,
                lambda selected_name=backend_name, selected_backend=backend, selected_target=candidate_target: _opencv_capture_camera_photo(
                    camera_index,
                    selected_target,
                    selected_name,
                    selected_backend,
                    warmup_ms=warmup_ms,
                ),
            )
    else:
        attempts.append({"backend": "opencv", "error": "OpenCV is not installed."})

    if system == "Linux":
        if shutil.which("ffmpeg"):
            try_backend(
                "ffmpeg",
                lambda: _ffmpeg_capture_camera_photo(
                    camera_index,
                    _candidate_photo_path(target, "ffmpeg"),
                    warmup_ms=warmup_ms,
                ),
            )
        else:
            attempts.append({"backend": "ffmpeg", "error": "ffmpeg was not found."})
        if shutil.which("libcamera-still"):
            try_backend(
                "libcamera-still",
                lambda: _libcamera_capture_camera_photo(
                    camera_index,
                    _candidate_photo_path(target, "libcamera-still"),
                    warmup_ms=warmup_ms,
                ),
            )
        else:
            attempts.append({"backend": "libcamera-still", "error": "libcamera-still was not found."})
        if shutil.which("fswebcam"):
            try_backend(
                "fswebcam",
                lambda: _fswebcam_capture_camera_photo(
                    camera_index,
                    _candidate_photo_path(target, "fswebcam"),
                    warmup_ms=warmup_ms,
                ),
            )
        else:
            attempts.append({"backend": "fswebcam", "error": "fswebcam was not found."})
    elif system == "Windows":
        if shutil.which("ffmpeg"):
            try_backend(
                "ffmpeg-dshow",
                lambda: _ffmpeg_capture_camera_photo(
                    camera_index,
                    _candidate_photo_path(target, "ffmpeg-dshow"),
                    warmup_ms=warmup_ms,
                ),
            )
        else:
            attempts.append({"backend": "ffmpeg-dshow", "error": "ffmpeg was not found."})

    if successes:
        best = max(successes, key=_result_quality_score)
        best_path = Path(str(best["path"]))
        if best_path != target:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(best_path, target)
            best["path"] = str(target)
            best["file_size"] = target.stat().st_size
        if attempts:
            best["fallback_attempts"] = attempts
        best["attempted_backends"] = [item["backend"] for item in attempts] + [item.get("backend", "") for item in successes]
        for candidate in successes:
            candidate_path_value = candidate.get("path")
            if not candidate_path_value:
                continue
            candidate_path = Path(str(candidate_path_value))
            if candidate_path != target and candidate_path.exists():
                try:
                    candidate_path.unlink()
                except OSError:
                    pass
        return best

    response: dict[str, Any] = {
        "ok": False,
        "platform": system,
        "camera_index": camera_index,
        "error": f"Unable to capture a photo from camera {camera_index} with the available backends.",
        "warmup_ms": warmup_ms,
        "available_backends": _detect_available_camera_backends(),
        "attempts": attempts,
    }
    if cv2 is None:
        response["missing_python_package"] = "opencv-python"
    return response
