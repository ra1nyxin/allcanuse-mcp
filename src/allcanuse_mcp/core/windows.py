from __future__ import annotations

import os
import platform
import psutil
import shutil
import subprocess
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any

try:
    from PIL import ImageGrab
except ImportError:
    ImageGrab = None

if platform.system() == "Windows":
    try:
        import win32gui
        import win32process
    except ImportError:
        win32gui = None
        win32process = None
else:
    win32gui = None
    win32process = None


def _window_info(hwnd: int) -> dict[str, Any]:
    if win32gui is None or win32process is None:
        raise RuntimeError("Win32 APIs are not available.")
    title = win32gui.GetWindowText(hwnd)
    class_name = win32gui.GetClassName(hwnd)
    visible = bool(win32gui.IsWindowVisible(hwnd))
    rect = win32gui.GetWindowRect(hwnd)
    _, pid = win32process.GetWindowThreadProcessId(hwnd)
    process_name = None
    process_exe = None
    try:
        process = psutil.Process(pid)
        process_name = process.name()
        process_exe = process.exe()
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        pass
    return {
        "hwnd": hwnd,
        "title": title,
        "class_name": class_name,
        "visible": visible,
        "pid": pid,
        "process_name": process_name,
        "process_exe": process_exe,
        "rect": {
            "left": rect[0],
            "top": rect[1],
            "right": rect[2],
            "bottom": rect[3],
            "width": rect[2] - rect[0],
            "height": rect[3] - rect[1],
        },
    }


def list_windows_info(
    *,
    include_invisible: bool = False,
    title_filter: str | None = None,
    limit: int = 200,
) -> dict[str, Any]:
    system = platform.system()
    if system == "Windows":
        return _list_windows_windows(
            include_invisible=include_invisible,
            title_filter=title_filter,
            limit=limit,
        )
    if system == "Linux":
        return _list_windows_linux(include_invisible=include_invisible, title_filter=title_filter, limit=limit)
    return {"ok": False, "error": f"Unsupported platform for list_windows: {system}"}


def _list_windows_windows(
    *,
    include_invisible: bool = False,
    title_filter: str | None = None,
    limit: int = 200,
) -> dict[str, Any]:
    if win32gui is None or win32process is None:
        return {"ok": False, "platform": "Windows", "error": "Win32 APIs are not available."}
    windows: list[dict[str, Any]] = []
    skipped_windows: list[dict[str, Any]] = []
    lowered_filter = title_filter.lower() if title_filter else None
    foreground_hwnd = win32gui.GetForegroundWindow()

    def callback(hwnd: int, _: int) -> None:
        if len(windows) >= limit:
            return
        try:
            info = _window_info(hwnd)
        except Exception as exc:
            if len(skipped_windows) < 20:
                skipped_windows.append({"hwnd": hwnd, "error": str(exc)})
            return
        if not include_invisible and not info["visible"]:
            return
        if lowered_filter and lowered_filter not in info["title"].lower():
            return
        if not info["title"] and not include_invisible:
            return
        info["is_foreground"] = hwnd == foreground_hwnd
        windows.append(info)

    win32gui.EnumWindows(callback, 0)
    return {
        "ok": True,
        "platform": "Windows",
        "count": len(windows),
        "foreground_count": sum(1 for item in windows if item.get("is_foreground")),
        "background_count": sum(1 for item in windows if not item.get("is_foreground")),
        "skipped_count": len(skipped_windows),
        "skipped_windows": skipped_windows,
        "windows": windows,
    }


def _list_windows_linux(
    *,
    include_invisible: bool = False,
    title_filter: str | None = None,
    limit: int = 200,
) -> dict[str, Any]:
    if not os.environ.get("DISPLAY") and not os.environ.get("WAYLAND_DISPLAY"):
        return {
            "ok": False,
            "platform": "Linux",
            "error": "No graphical desktop session was detected.",
            "hint": "Set DISPLAY/WAYLAND_DISPLAY or run inside a graphical desktop session.",
        }
    if shutil.which("wmctrl") is None:
        return {
            "ok": False,
            "platform": "Linux",
            "error": "The `wmctrl` command is required to enumerate windows on Linux.",
            "missing_command": "wmctrl",
        }

    result = subprocess.run(
        ["wmctrl", "-lpG"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if result.returncode != 0:
        return {"ok": False, "platform": "Linux", "error": result.stderr.strip() or "wmctrl failed."}

    lowered_filter = title_filter.lower() if title_filter else None
    windows: list[dict[str, Any]] = []
    for line in result.stdout.splitlines():
        parts = line.split(None, 8)
        if len(parts) < 8:
            continue
        if len(parts) == 8:
            window_id, desktop_id, pid, x, y, width, height, host = parts
            title = ""
        else:
            window_id, desktop_id, pid, x, y, width, height, host, title = parts
        visible = desktop_id != "-1"
        if not include_invisible and not visible:
            continue
        if lowered_filter and lowered_filter not in title.lower():
            continue
        windows.append(
            {
                "hwnd": window_id,
                "title": title,
                "class_name": None,
                "visible": visible,
                "pid": int(pid),
                "process_name": _safe_process_name(int(pid)),
                "process_exe": _safe_process_exe(int(pid)),
                "host": host,
                "is_foreground": False,
                "rect": {
                    "left": int(x),
                    "top": int(y),
                    "right": int(x) + int(width),
                    "bottom": int(y) + int(height),
                    "width": int(width),
                    "height": int(height),
                },
            }
        )
        if len(windows) >= limit:
            break
    foreground_id = None
    foreground_error = ""
    if shutil.which("xprop") is not None:
        try:
            foreground_id = _get_linux_active_window_id()
        except Exception as exc:
            foreground_error = str(exc)
    else:
        foreground_error = "The `xprop` command is not available, so foreground window detection was skipped."
    for item in windows:
        item["is_foreground"] = item["hwnd"] == foreground_id
    result = {
        "ok": True,
        "platform": "Linux",
        "count": len(windows),
        "foreground_count": sum(1 for item in windows if item.get("is_foreground")),
        "background_count": sum(1 for item in windows if not item.get("is_foreground")),
        "windows": windows,
    }
    if foreground_error:
        result["foreground_detection_warning"] = foreground_error
    return result


def get_active_window_info() -> dict[str, Any]:
    system = platform.system()
    if system == "Windows":
        if win32gui is None:
            return {"ok": False, "platform": "Windows", "error": "Win32 APIs are not available."}
        hwnd = win32gui.GetForegroundWindow()
        if not hwnd:
            return {"ok": True, "platform": "Windows", "found": False}
        info = _window_info(hwnd)
        info["is_foreground"] = True
        return {"ok": True, "platform": "Windows", "found": True, "window": info}

    if system == "Linux":
        if not os.environ.get("DISPLAY") and not os.environ.get("WAYLAND_DISPLAY"):
            return {
                "ok": False,
                "platform": "Linux",
                "error": "No graphical desktop session was detected.",
            }
        if shutil.which("xprop") is None:
            return {
                "ok": False,
                "platform": "Linux",
                "error": "The `xprop` command is required to query the active window.",
                "missing_command": "xprop",
            }
        window_id = _get_linux_active_window_id()
        if window_id is None:
            return {"ok": True, "platform": "Linux", "found": False}
        details = subprocess.run(
            ["xprop", "-id", window_id, "WM_NAME", "WM_CLASS", "_NET_WM_PID"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
        return {
            "ok": True,
            "platform": "Linux",
            "found": True,
            "window": {
                "hwnd": window_id,
                "details": details.stdout.strip(),
                "query_ok": details.returncode == 0,
                "is_foreground": True,
            },
        }

    return {"ok": False, "error": f"Unsupported platform for active window: {system}"}


def capture_desktop_screenshot(output_path: str | None = None, *, all_screens: bool = True) -> dict[str, Any]:
    if output_path:
        target = Path(output_path).expanduser().resolve()
        target.parent.mkdir(parents=True, exist_ok=True)
    else:
        filename = f"screenshot-{datetime.now().strftime('%Y%m%d-%H%M%S')}.png"
        target = Path(tempfile.gettempdir(), filename).resolve()

    if ImageGrab is not None:
        try:
            image = ImageGrab.grab(all_screens=all_screens)
            image.save(target)
            return {
                "ok": True,
                "platform": platform.system(),
                "backend": "Pillow.ImageGrab",
                "path": str(target),
                "width": image.width,
                "height": image.height,
                "mode": image.mode,
                "file_size": target.stat().st_size,
            }
        except Exception as exc:
            imagegrab_error = str(exc)
        else:
            imagegrab_error = ""
    else:
        imagegrab_error = "Pillow.ImageGrab is unavailable."

    if platform.system() == "Linux":
        command_candidates = [
            ["gnome-screenshot", "-f", str(target)],
            ["scrot", str(target)],
            ["import", "-window", "root", str(target)],
        ]
        for command in command_candidates:
            if shutil.which(command[0]) is None:
                continue
            result = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="replace")
            if result.returncode == 0 and target.exists():
                return {
                    "ok": True,
                    "platform": "Linux",
                    "backend": command[0],
                    "path": str(target),
                    "file_size": target.stat().st_size,
                }
        return {
            "ok": False,
            "platform": "Linux",
            "error": "No screenshot backend succeeded.",
            "imagegrab_error": imagegrab_error,
            "hint": "Install Pillow with GUI support or one of: gnome-screenshot, scrot, imagemagick.",
        }

    return {
        "ok": False,
        "platform": platform.system(),
        "error": "Screenshot capture is unavailable on this host.",
        "imagegrab_error": imagegrab_error,
        "hint": "Install Pillow or enable a graphical desktop session.",
    }


def get_desktop_context(*, limit: int = 50, include_invisible: bool = False) -> dict[str, Any]:
    active = get_active_window_info()
    windows = list_windows_info(include_invisible=include_invisible, limit=limit)
    foreground = active.get("window") if active.get("ok") and active.get("found") else None
    background_windows = []
    if windows.get("ok"):
        background_windows = [item for item in windows.get("windows", []) if not item.get("is_foreground")]
    return {
        "ok": bool(active.get("ok")) and bool(windows.get("ok")),
        "platform": platform.system(),
        "foreground_window": foreground,
        "background_window_count": len(background_windows),
        "background_windows": background_windows,
    }


def _safe_process_name(pid: int) -> str | None:
    try:
        return psutil.Process(pid).name()
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        return None


def _safe_process_exe(pid: int) -> str | None:
    try:
        return psutil.Process(pid).exe()
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        return None


def _get_linux_active_window_id() -> str | None:
    root = subprocess.run(
        ["xprop", "-root", "_NET_ACTIVE_WINDOW"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if root.returncode != 0 or "window id # 0x0" in root.stdout.lower():
        return None
    tokens = root.stdout.split()
    if not tokens:
        return None
    return tokens[-1]
