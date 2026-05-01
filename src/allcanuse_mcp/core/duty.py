from __future__ import annotations

import json
import socket
import threading
import time
import uuid
from collections import Counter
from datetime import datetime, timedelta, timezone as dt_timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

try:
    import psutil
except ImportError:
    psutil = None

from allcanuse_mcp.core import linux_fallbacks
from allcanuse_mcp.core.windows import list_windows_info


TASK_STATUSES = {
    "pending",
    "running",
    "waiting",
    "waiting_for_user",
    "waiting_for_condition",
    "paused",
    "completed",
    "failed",
    "cancelled",
}

WAITABLE_TASK_TYPES = {
    "sleep",
    "wait_file",
    "wait_process",
    "wait_port",
    "wait_http",
    "wait_window",
    "wait_desktop_change",
}
FINAL_TASK_STATUSES = {"completed", "failed", "cancelled"}
ACTIVE_TASK_STATUSES = {"pending", "running", "waiting", "waiting_for_condition"}

_MANAGER_SINGLETON: BackgroundTaskManager | None = None
_MANAGER_LOCK = threading.Lock()


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _utc_now() -> datetime:
    return datetime.now(dt_timezone.utc)


def _iso_now() -> str:
    return _utc_now().isoformat()


def _to_iso(dt: datetime) -> str:
    return dt.astimezone(dt_timezone.utc).isoformat()


def _parse_iso_datetime(value: str) -> datetime:
    normalized = value.strip()
    if normalized.endswith("Z"):
        normalized = normalized[:-1] + "+00:00"
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=dt_timezone.utc)
    return parsed.astimezone(dt_timezone.utc)


def _sleep_ms(duration_ms: int) -> None:
    if duration_ms <= 0:
        return
    time.sleep(duration_ms / 1000)


def _ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def _atomic_write_json(path: Path, data: Any) -> None:
    _ensure_parent(path)
    temp_path = path.with_suffix(path.suffix + ".tmp")
    temp_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    temp_path.replace(path)


def _read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def _run_polling_wait(
    checker,
    *,
    timeout_ms: int,
    poll_interval_ms: int,
) -> dict[str, Any]:
    started_at = _utc_now()
    deadline = started_at + timedelta(milliseconds=max(timeout_ms, 0))
    attempts = 0
    last_result: dict[str, Any] = {}

    while True:
        attempts += 1
        last_result = checker()
        if last_result.get("condition_met"):
            return {
                "ok": True,
                "condition_met": True,
                "attempts": attempts,
                "started_at": _to_iso(started_at),
                "finished_at": _iso_now(),
                "timeout_ms": timeout_ms,
                "poll_interval_ms": poll_interval_ms,
                "waited_ms": int((_utc_now() - started_at).total_seconds() * 1000),
                "last_result": last_result,
            }
        if last_result.get("fatal_error"):
            return {
                "ok": False,
                "condition_met": False,
                "fatal_error": True,
                "attempts": attempts,
                "started_at": _to_iso(started_at),
                "finished_at": _iso_now(),
                "timeout_ms": timeout_ms,
                "poll_interval_ms": poll_interval_ms,
                "waited_ms": int((_utc_now() - started_at).total_seconds() * 1000),
                "last_result": last_result,
            }
        if timeout_ms >= 0 and _utc_now() >= deadline:
            return {
                "ok": False,
                "condition_met": False,
                "attempts": attempts,
                "started_at": _to_iso(started_at),
                "finished_at": _iso_now(),
                "timeout_ms": timeout_ms,
                "poll_interval_ms": poll_interval_ms,
                "waited_ms": int((_utc_now() - started_at).total_seconds() * 1000),
                "last_result": last_result,
            }
        _sleep_ms(max(poll_interval_ms, 1))


def wait(duration_ms: int, reason: str | None = None) -> dict[str, Any]:
    started_at = _utc_now()
    _sleep_ms(max(duration_ms, 0))
    finished_at = _utc_now()
    return {
        "ok": True,
        "reason": reason or "",
        "requested_duration_ms": duration_ms,
        "started_at": _to_iso(started_at),
        "finished_at": _to_iso(finished_at),
        "waited_ms": int((finished_at - started_at).total_seconds() * 1000),
    }


def wait_until(timestamp: str, reason: str | None = None) -> dict[str, Any]:
    target = _parse_iso_datetime(timestamp)
    now = _utc_now()
    remaining_ms = max(int((target - now).total_seconds() * 1000), 0)
    result = wait(remaining_ms, reason=reason or "wait_until")
    result["target_time"] = _to_iso(target)
    result["remaining_ms_when_started"] = remaining_ms
    return result


def get_scheduler_time(manager: BackgroundTaskManager | None = None) -> dict[str, Any]:
    local_now = datetime.now().astimezone()
    utc_now = _utc_now()
    task_counts: dict[str, int] = {}
    scheduler_info: dict[str, Any] = {}
    if manager is not None:
        task_counts = manager.status_counts()
        scheduler_info = manager.scheduler_health()
    return {
        "local_time": local_now.isoformat(),
        "local_timezone": str(local_now.tzinfo),
        "utc_time": utc_now.isoformat(),
        "monotonic_seconds": time.monotonic(),
        "runtime_tasks_dir": str((manager.storage_dir if manager is not None else _repo_root() / "runtime" / "tasks").resolve()),
        "task_status_counts": task_counts,
        "scheduler": scheduler_info,
    }


def wait_for_file(
    path: str,
    *,
    state: str = "exists",
    timeout_ms: int = 60_000,
    poll_interval_ms: int = 1000,
    min_size_bytes: int | None = None,
    text_contains: str | None = None,
    encoding: str = "utf-8",
) -> dict[str, Any]:
    condition = {
        "path": path,
        "state": state,
        "min_size_bytes": min_size_bytes,
        "text_contains": text_contains,
        "encoding": encoding,
    }
    return _run_polling_wait(
        lambda: _check_file_condition(condition),
        timeout_ms=timeout_ms,
        poll_interval_ms=poll_interval_ms,
    )


def wait_for_process(
    *,
    pid: int | None = None,
    name: str | None = None,
    state: str = "running",
    timeout_ms: int = 60_000,
    poll_interval_ms: int = 1000,
) -> dict[str, Any]:
    condition = {"pid": pid, "name": name, "state": state}
    return _run_polling_wait(
        lambda: _check_process_condition(condition),
        timeout_ms=timeout_ms,
        poll_interval_ms=poll_interval_ms,
    )


def wait_for_port(
    host: str,
    port: int,
    *,
    state: str = "open",
    timeout_ms: int = 60_000,
    poll_interval_ms: int = 1000,
    connect_timeout_ms: int = 1500,
) -> dict[str, Any]:
    condition = {
        "host": host,
        "port": port,
        "state": state,
        "connect_timeout_ms": connect_timeout_ms,
    }
    return _run_polling_wait(
        lambda: _check_port_condition(condition),
        timeout_ms=timeout_ms,
        poll_interval_ms=poll_interval_ms,
    )


def wait_for_http(
    url: str,
    *,
    expected_statuses: list[int] | None = None,
    method: str = "GET",
    headers: dict[str, str] | None = None,
    body: str | None = None,
    timeout_ms: int = 60_000,
    poll_interval_ms: int = 2000,
    request_timeout_ms: int = 5000,
    text_contains: str | None = None,
) -> dict[str, Any]:
    condition = {
        "url": url,
        "expected_statuses": expected_statuses or [200],
        "method": method,
        "headers": headers or {},
        "body": body,
        "request_timeout_ms": request_timeout_ms,
        "text_contains": text_contains,
    }
    return _run_polling_wait(
        lambda: _check_http_condition(condition),
        timeout_ms=timeout_ms,
        poll_interval_ms=poll_interval_ms,
    )


def wait_for_window(
    *,
    title_filter: str | None = None,
    hwnd: str | int | None = None,
    process_name: str | None = None,
    state: str = "appeared",
    include_invisible: bool = False,
    limit: int = 500,
    timeout_ms: int = 60_000,
    poll_interval_ms: int = 1000,
) -> dict[str, Any]:
    condition = {
        "title_filter": title_filter,
        "hwnd": _normalize_hwnd(hwnd),
        "process_name": process_name,
        "state": state,
        "include_invisible": include_invisible,
        "limit": max(int(limit), 1),
    }
    return _run_polling_wait(
        lambda: _check_window_condition(condition),
        timeout_ms=timeout_ms,
        poll_interval_ms=poll_interval_ms,
    )


def wait_for_desktop_change(
    *,
    include_invisible: bool = False,
    limit: int = 50,
    baseline_snapshot: dict[str, Any] | None = None,
    timeout_ms: int = 60_000,
    poll_interval_ms: int = 1000,
) -> dict[str, Any]:
    try:
        baseline = baseline_snapshot or _capture_desktop_snapshot(
            include_invisible=include_invisible,
            limit=limit,
        )
    except Exception as exc:
        return {
            "ok": False,
            "condition_met": False,
            "fatal_error": True,
            "attempts": 0,
            "started_at": _iso_now(),
            "finished_at": _iso_now(),
            "timeout_ms": timeout_ms,
            "poll_interval_ms": poll_interval_ms,
            "waited_ms": 0,
            "last_result": {
                "condition_met": False,
                "fatal_error": True,
                "error": str(exc),
                "include_invisible": include_invisible,
                "limit": limit,
            },
        }
    condition = {
        "include_invisible": include_invisible,
        "limit": limit,
        "baseline_snapshot": baseline,
    }
    return _run_polling_wait(
        lambda: _check_desktop_change_condition(condition),
        timeout_ms=timeout_ms,
        poll_interval_ms=poll_interval_ms,
    )


def wait_for_background_task(
    manager: BackgroundTaskManager,
    task_id: str,
    *,
    target_statuses: list[str] | None = None,
    timeout_ms: int = 60_000,
    poll_interval_ms: int = 1000,
) -> dict[str, Any]:
    targets = set(target_statuses or ["completed", "failed", "cancelled"])

    def checker() -> dict[str, Any]:
        task = manager.get_task(task_id)
        return {
            "condition_met": task["status"] in targets,
            "task_id": task_id,
            "status": task["status"],
            "task": task,
        }

    return _run_polling_wait(checker, timeout_ms=timeout_ms, poll_interval_ms=poll_interval_ms)


def _check_file_condition(condition: dict[str, Any]) -> dict[str, Any]:
    path = Path(condition["path"]).expanduser().resolve()
    state = (condition.get("state") or "exists").lower()
    min_size_bytes = condition.get("min_size_bytes")
    text_contains = condition.get("text_contains")
    encoding = condition.get("encoding") or "utf-8"

    exists = path.exists()
    is_file = path.is_file()
    size_bytes = path.stat().st_size if exists and is_file else None
    text_match = None

    if state == "exists":
        condition_met = exists
    elif state == "missing":
        condition_met = not exists
    else:
        raise ValueError("wait_for_file state must be exists or missing")

    if condition_met and min_size_bytes is not None:
        condition_met = size_bytes is not None and size_bytes >= int(min_size_bytes)
    if condition_met and text_contains is not None:
        if exists and is_file:
            content = path.read_text(encoding=encoding, errors="replace")
            text_match = text_contains in content
        else:
            text_match = False
        condition_met = bool(text_match)

    return {
        "condition_met": condition_met,
        "path": str(path),
        "state": state,
        "exists": exists,
        "is_file": is_file,
        "size_bytes": size_bytes,
        "text_match": text_match,
    }


def _find_matching_processes(pid: int | None, name: str | None) -> list[dict[str, Any]]:
    if psutil is None and linux_fallbacks.linux_procfs_available():
        return linux_fallbacks.find_matching_processes(pid=pid, name=name)

    matches: list[dict[str, Any]] = []
    for proc in psutil.process_iter(["pid", "name", "status"]):
        try:
            info = proc.info
            if pid is not None and info["pid"] != pid:
                continue
            if name and (info.get("name") or "").casefold() != name.casefold():
                continue
            matches.append(
                {
                    "pid": info["pid"],
                    "name": info.get("name") or "",
                    "status": info.get("status") or "",
                }
            )
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return matches


def _check_process_condition(condition: dict[str, Any]) -> dict[str, Any]:
    pid = condition.get("pid")
    name = condition.get("name")
    state = (condition.get("state") or "running").lower()
    if pid is None and not name:
        raise ValueError("wait_for_process requires pid or name")
    matches = _find_matching_processes(pid, name)
    is_running = bool(matches)
    if state == "running":
        condition_met = is_running
    elif state == "exited":
        condition_met = not is_running
    else:
        raise ValueError("wait_for_process state must be running or exited")
    return {
        "condition_met": condition_met,
        "pid": pid,
        "name": name or "",
        "state": state,
        "matched_count": len(matches),
        "matches": matches[:20],
    }


def _check_port_condition(condition: dict[str, Any]) -> dict[str, Any]:
    host = condition["host"]
    port = int(condition["port"])
    state = (condition.get("state") or "open").lower()
    connect_timeout_ms = int(condition.get("connect_timeout_ms") or 1500)
    is_open = False
    error = ""
    try:
        with socket.create_connection((host, port), timeout=max(connect_timeout_ms, 1) / 1000):
            is_open = True
    except OSError as exc:
        error = str(exc)
    if state == "open":
        condition_met = is_open
    elif state == "closed":
        condition_met = not is_open
    else:
        raise ValueError("wait_for_port state must be open or closed")
    return {
        "condition_met": condition_met,
        "host": host,
        "port": port,
        "state": state,
        "is_open": is_open,
        "error": error,
    }


def _check_http_condition(condition: dict[str, Any]) -> dict[str, Any]:
    url = condition["url"]
    method = (condition.get("method") or "GET").upper()
    headers = condition.get("headers") or {}
    body = condition.get("body")
    request_timeout_ms = int(condition.get("request_timeout_ms") or 5000)
    expected_statuses = [int(item) for item in (condition.get("expected_statuses") or [200])]
    text_contains = condition.get("text_contains")

    body_bytes = body.encode("utf-8") if body is not None else None
    request = Request(url=url, method=method, headers=headers, data=body_bytes)
    status = None
    reason = ""
    final_url = url
    text = ""
    error = ""
    try:
        with urlopen(request, timeout=max(request_timeout_ms, 1) / 1000) as response:
            status = response.status
            reason = response.reason
            final_url = response.geturl()
            if text_contains is not None:
                charset = response.headers.get_content_charset() or "utf-8"
                text = response.read().decode(charset, errors="replace")
    except HTTPError as exc:
        status = exc.code
        reason = str(exc.reason)
        final_url = exc.geturl()
        if text_contains is not None:
            text = exc.read().decode("utf-8", errors="replace")
    except URLError as exc:
        error = str(exc.reason)

    condition_met = status in expected_statuses
    text_match = None
    if condition_met and text_contains is not None:
        text_match = text_contains in text
        condition_met = text_match

    return {
        "condition_met": condition_met,
        "url": url,
        "final_url": final_url,
        "method": method,
        "status": status,
        "reason": reason,
        "expected_statuses": expected_statuses,
        "text_match": text_match,
        "error": error,
    }


def _normalize_hwnd(value: str | int | None) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _match_window(item: dict[str, Any], *, title_filter: str | None, hwnd: str, process_name: str | None) -> bool:
    if hwnd and str(item.get("hwnd", "")).strip() != hwnd:
        return False
    if title_filter and title_filter.casefold() not in str(item.get("title") or "").casefold():
        return False
    if process_name and process_name.casefold() != str(item.get("process_name") or "").casefold():
        return False
    return True


def _check_window_condition(condition: dict[str, Any]) -> dict[str, Any]:
    state = (condition.get("state") or "appeared").lower()
    title_filter = condition.get("title_filter")
    hwnd = _normalize_hwnd(condition.get("hwnd"))
    process_name = condition.get("process_name")
    include_invisible = bool(condition.get("include_invisible"))
    limit = max(int(condition.get("limit") or 500), 1)

    windows_result = list_windows_info(include_invisible=include_invisible, limit=limit)
    if not windows_result.get("ok"):
        return {
            "condition_met": False,
            "fatal_error": True,
            "state": state,
            "title_filter": title_filter or "",
            "hwnd": hwnd,
            "process_name": process_name or "",
            "error": windows_result.get("error") or "Window enumeration failed.",
            "details": windows_result,
        }

    windows = windows_result.get("windows", [])
    matches = [
        item
        for item in windows
        if _match_window(item, title_filter=title_filter, hwnd=hwnd, process_name=process_name)
    ]
    foreground_matches = [item for item in matches if item.get("is_foreground")]

    if state == "appeared":
        condition_met = bool(matches)
    elif state == "missing":
        condition_met = not matches
    elif state == "foreground":
        condition_met = bool(foreground_matches)
    else:
        raise ValueError("wait_for_window state must be appeared, missing, or foreground")

    return {
        "condition_met": condition_met,
        "platform": windows_result.get("platform"),
        "state": state,
        "title_filter": title_filter or "",
        "hwnd": hwnd,
        "process_name": process_name or "",
        "include_invisible": include_invisible,
        "limit": limit,
        "matched_count": len(matches),
        "foreground_match_count": len(foreground_matches),
        "matched_windows": matches[:20],
        "foreground_windows": foreground_matches[:20],
    }


def _lightweight_window(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "hwnd": str(item.get("hwnd", "")),
        "title": item.get("title") or "",
        "pid": item.get("pid"),
        "process_name": item.get("process_name") or "",
        "visible": bool(item.get("visible")),
        "is_foreground": bool(item.get("is_foreground")),
    }


def _capture_desktop_snapshot(*, include_invisible: bool = False, limit: int = 50) -> dict[str, Any]:
    windows_result = list_windows_info(include_invisible=include_invisible, limit=max(limit, 1))
    if not windows_result.get("ok"):
        raise RuntimeError(windows_result.get("error") or "Desktop context is unavailable.")

    windows = [_lightweight_window(item) for item in windows_result.get("windows", [])[:limit]]
    foreground_window = next((item for item in windows if item.get("is_foreground")), None)
    signature_payload = {
        "platform": windows_result.get("platform"),
        "include_invisible": include_invisible,
        "window_count": len(windows),
        "foreground": foreground_window,
        "windows": sorted(
            windows,
            key=lambda item: (
                str(item.get("hwnd", "")),
                item.get("title", ""),
                str(item.get("pid", "")),
            ),
        ),
    }
    return {
        "captured_at": _iso_now(),
        "platform": windows_result.get("platform"),
        "include_invisible": include_invisible,
        "limit": limit,
        "window_count": len(windows),
        "foreground_window": foreground_window,
        "windows": windows,
        "signature": json.dumps(signature_payload, ensure_ascii=False, sort_keys=True),
    }


def _window_key(item: dict[str, Any]) -> tuple[str, str, str]:
    return (
        str(item.get("hwnd", "")),
        item.get("title", "") or "",
        str(item.get("pid", "")),
    )


def _check_desktop_change_condition(condition: dict[str, Any]) -> dict[str, Any]:
    baseline = condition["baseline_snapshot"]
    try:
        current = _capture_desktop_snapshot(
            include_invisible=bool(condition.get("include_invisible")),
            limit=int(condition.get("limit") or 50),
        )
    except Exception as exc:
        return {
            "condition_met": False,
            "fatal_error": True,
            "error": str(exc),
            "baseline_snapshot": baseline,
        }

    baseline_windows = baseline.get("windows", [])
    current_windows = current.get("windows", [])
    baseline_keys = {_window_key(item): item for item in baseline_windows}
    current_keys = {_window_key(item): item for item in current_windows}

    added_keys = [key for key in current_keys if key not in baseline_keys]
    removed_keys = [key for key in baseline_keys if key not in current_keys]
    foreground_changed = baseline.get("foreground_window") != current.get("foreground_window")
    window_count_changed = int(baseline.get("window_count") or 0) != int(current.get("window_count") or 0)
    signature_changed = baseline.get("signature") != current.get("signature")

    return {
        "condition_met": signature_changed,
        "platform": current.get("platform"),
        "signature_changed": signature_changed,
        "foreground_changed": foreground_changed,
        "window_count_changed": window_count_changed,
        "baseline_window_count": baseline.get("window_count"),
        "current_window_count": current.get("window_count"),
        "baseline_foreground_window": baseline.get("foreground_window"),
        "current_foreground_window": current.get("foreground_window"),
        "added_windows": [current_keys[key] for key in added_keys[:20]],
        "removed_windows": [baseline_keys[key] for key in removed_keys[:20]],
        "baseline_snapshot": baseline,
        "current_snapshot": current,
    }


def _evaluate_task_condition(task_type: str, condition: dict[str, Any]) -> dict[str, Any]:
    if task_type == "sleep":
        wake_at = _parse_iso_datetime(condition["wake_at"])
        now = _utc_now()
        condition_met = now >= wake_at
        return {
            "condition_met": condition_met,
            "wake_at": _to_iso(wake_at),
            "remaining_ms": max(int((wake_at - now).total_seconds() * 1000), 0),
        }
    if task_type == "wait_file":
        return _check_file_condition(condition)
    if task_type == "wait_process":
        return _check_process_condition(condition)
    if task_type == "wait_port":
        return _check_port_condition(condition)
    if task_type == "wait_http":
        return _check_http_condition(condition)
    if task_type == "wait_window":
        return _check_window_condition(condition)
    if task_type == "wait_desktop_change":
        return _check_desktop_change_condition(condition)
    raise ValueError(f"Unsupported background task type: {task_type}")


def _current_step(plan_steps: list[dict[str, Any]]) -> dict[str, Any] | None:
    for step in plan_steps:
        if step.get("status") == "in_progress":
            return step
    for step in plan_steps:
        if step.get("status") == "pending":
            return step
    if plan_steps:
        return plan_steps[-1]
    return None


def _infer_task_blocker(task: dict[str, Any], recent_events: list[dict[str, Any]]) -> str:
    if task["status"] == "waiting_for_user":
        if task.get("last_event", {}).get("data", {}).get("question"):
            return str(task["last_event"]["data"]["question"])
        if task.get("last_event", {}).get("message"):
            return str(task["last_event"]["message"])
        return "等待用户决策"
    if task["status"] in {"waiting", "waiting_for_condition"}:
        if task.get("last_error"):
            return f"等待过程中出现错误: {task['last_error']}"
        if task.get("last_event", {}).get("message"):
            return str(task["last_event"]["message"])
        return "等待条件满足"
    if task["status"] == "paused":
        return "任务已暂停，需要恢复后继续"
    if task["status"] == "failed":
        return task.get("last_error") or "任务执行失败"
    if recent_events:
        return recent_events[-1].get("message") or ""
    return ""


def _suggest_next_actions(task: dict[str, Any], current_step: dict[str, Any] | None) -> list[str]:
    suggestions: list[str] = []
    if task["status"] == "waiting_for_user":
        suggestions.append("向用户确认问题后调用 resume_background_task 继续。")
    elif task["status"] == "paused":
        suggestions.append("确认可以继续后调用 resume_background_task。")
    elif task["status"] in {"waiting", "waiting_for_condition"}:
        suggestions.append("继续让调度器值班，必要时稍后用 get_background_task 或 summarize_background_task 查看进展。")
    elif task["status"] == "running":
        suggestions.append("继续观察当前任务状态，必要时补充 append_task_event 或 record_task_artifact。")
    elif task["status"] == "completed":
        suggestions.append("检查任务产物和最近观察结果，确认是否需要继续后续步骤。")
    elif task["status"] == "failed":
        suggestions.append("先查看 last_error 和 recent_events，再决定是否重试或修改条件。")

    if current_step and current_step.get("status") != "completed":
        suggestions.append(f"优先处理当前步骤: {current_step.get('index')}. {current_step.get('title')}")
    if task.get("artifacts"):
        suggestions.append("如需交接或汇报，优先引用 artifacts 中已记录的文件。")
    if not suggestions:
        suggestions.append("先调用 get_background_task 查看最新状态。")
    return suggestions


class BackgroundTaskManager:
    def __init__(
        self,
        *,
        storage_dir: str | Path | None = None,
        scheduler_interval_ms: int = 500,
    ) -> None:
        self.storage_dir = Path(storage_dir or (_repo_root() / "runtime" / "tasks")).expanduser().resolve()
        self.scheduler_interval_ms = max(scheduler_interval_ms, 100)
        self.index_path = self.storage_dir / "index.json"
        self._lock = threading.RLock()
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._tasks: dict[str, dict[str, Any]] = {}
        self._last_scheduler_error = ""
        self._last_scheduler_error_at = ""
        self._load_issues: list[dict[str, Any]] = []
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self._load_tasks()
        self._ensure_scheduler_running()

    def _task_path(self, task_id: str) -> Path:
        return self.storage_dir / f"{task_id}.json"

    def _events_path(self, task_id: str) -> Path:
        return self.storage_dir / f"{task_id}.events.jsonl"

    def _artifacts_path(self, task_id: str) -> Path:
        return self.storage_dir / f"{task_id}.artifacts.json"

    def _corrupted_dir(self) -> Path:
        return self.storage_dir / "corrupted"

    def _load_tasks(self) -> None:
        with self._lock:
            self._tasks.clear()
            self._load_issues.clear()
            for path in sorted(self.storage_dir.glob("*.json")):
                if path.name == "index.json" or path.name.endswith(".artifacts.json"):
                    continue
                try:
                    payload = _read_json(path, default=None)
                except Exception as exc:
                    self._record_load_issue_locked(path, f"Failed to parse task JSON: {exc}")
                    self._quarantine_corrupted_file_locked(path)
                    continue
                if not isinstance(payload, dict) or not payload.get("task_id"):
                    self._record_load_issue_locked(path, "Task JSON is not a valid task object")
                    self._quarantine_corrupted_file_locked(path)
                    continue
                self._tasks[payload["task_id"]] = payload
            self._write_index_locked()

    def _write_index_locked(self) -> None:
        summaries = []
        for task in sorted(self._tasks.values(), key=lambda item: item.get("created_at", "")):
            summaries.append(
                {
                    "task_id": task["task_id"],
                    "title": task["title"],
                    "task_type": task["task_type"],
                    "status": task["status"],
                    "priority": task["priority"],
                    "updated_at": task["updated_at"],
                    "next_check_at": task.get("next_check_at", ""),
                }
            )
        _atomic_write_json(self.index_path, {"count": len(summaries), "tasks": summaries})

    def _save_task_locked(self, task: dict[str, Any]) -> None:
        task["updated_at"] = _iso_now()
        self._tasks[task["task_id"]] = task
        _atomic_write_json(self._task_path(task["task_id"]), task)
        _atomic_write_json(self._artifacts_path(task["task_id"]), {"artifacts": task.get("artifacts", [])})
        self._write_index_locked()

    def _append_event_locked(
        self,
        task: dict[str, Any],
        *,
        event_type: str,
        message: str,
        data: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        event = {
            "event_id": uuid.uuid4().hex,
            "task_id": task["task_id"],
            "timestamp": _iso_now(),
            "type": event_type,
            "message": message,
            "data": data or {},
        }
        with self._events_path(task["task_id"]).open("a", encoding="utf-8") as file:
            file.write(json.dumps(event, ensure_ascii=False) + "\n")
        task["last_event_at"] = event["timestamp"]
        task["last_event"] = event
        return event

    def _transition_status_locked(
        self,
        task: dict[str, Any],
        status: str,
        *,
        message: str,
        event_type: str = "progress",
        data: dict[str, Any] | None = None,
    ) -> None:
        if status not in TASK_STATUSES:
            raise ValueError(f"Unsupported task status: {status}")
        previous_status = task["status"]
        task["status"] = status
        if status == "running" and not task.get("started_at"):
            task["started_at"] = _iso_now()
        if status in FINAL_TASK_STATUSES:
            task["completed_at"] = _iso_now()
        self._append_event_locked(
            task,
            event_type=event_type,
            message=message,
            data={"previous_status": previous_status, "status": status, **(data or {})},
        )
        self._save_task_locked(task)

    def _ensure_scheduler_running(self) -> None:
        with self._lock:
            if self._thread is not None and self._thread.is_alive():
                return
            self._thread = threading.Thread(target=self._scheduler_loop, name="allcanuse-duty-scheduler", daemon=True)
            self._thread.start()

    def shutdown(self) -> None:
        self._stop_event.set()
        thread = self._thread
        if thread is not None:
            thread.join(timeout=5)

    def status_counts(self) -> dict[str, int]:
        with self._lock:
            counter = Counter(task["status"] for task in self._tasks.values())
        return dict(sorted(counter.items()))

    def scheduler_health(self) -> dict[str, Any]:
        with self._lock:
            return {
                "running": bool(self._thread is not None and self._thread.is_alive() and not self._stop_event.is_set()),
                "scheduler_interval_ms": self.scheduler_interval_ms,
                "last_error": self._last_scheduler_error,
                "last_error_at": self._last_scheduler_error_at,
                "load_issue_count": len(self._load_issues),
                "recent_load_issues": self._load_issues[-10:],
            }

    def _record_scheduler_error_locked(self, message: str) -> None:
        self._last_scheduler_error = message
        self._last_scheduler_error_at = _iso_now()

    def _clear_scheduler_error_locked(self) -> None:
        self._last_scheduler_error = ""
        self._last_scheduler_error_at = ""

    def _record_load_issue_locked(self, path: Path, message: str) -> None:
        self._load_issues.append(
            {
                "path": str(path),
                "message": message,
                "timestamp": _iso_now(),
            }
        )

    def _quarantine_corrupted_file_locked(self, path: Path) -> None:
        target_dir = self._corrupted_dir()
        target_dir.mkdir(parents=True, exist_ok=True)
        suffix = f".{datetime.now().strftime('%Y%m%d-%H%M%S')}.{uuid.uuid4().hex[:8]}.corrupt"
        target = target_dir / f"{path.name}{suffix}"
        try:
            path.replace(target)
        except Exception as exc:
            self._record_load_issue_locked(path, f"Failed to quarantine corrupted file: {exc}")

    def create_task(
        self,
        *,
        title: str,
        goal: str,
        task_type: str,
        condition: dict[str, Any],
        poll_interval_ms: int = 5000,
        timeout_ms: int | None = None,
        priority: int = 50,
        owner: str | None = None,
        tags: list[str] | None = None,
        notes: str | None = None,
    ) -> dict[str, Any]:
        normalized_condition = self._normalize_condition(task_type, condition)
        task_id = uuid.uuid4().hex
        now = _utc_now()
        deadline_at = _to_iso(now + timedelta(milliseconds=timeout_ms)) if timeout_ms is not None else None
        task = {
            "task_id": task_id,
            "title": title.strip() or task_type,
            "goal": goal.strip() or title.strip() or task_type,
            "task_type": task_type,
            "condition": normalized_condition,
            "status": "pending",
            "priority": int(priority),
            "owner": owner or "",
            "tags": list(tags or []),
            "notes": notes or "",
            "created_at": _to_iso(now),
            "updated_at": _to_iso(now),
            "started_at": "",
            "completed_at": "",
            "last_checked_at": "",
            "next_check_at": _to_iso(now),
            "deadline_at": deadline_at or "",
            "timeout_ms": timeout_ms,
            "poll_interval_ms": max(int(poll_interval_ms), 100),
            "check_count": 0,
            "last_result": {},
            "last_error": "",
            "plan_steps": [],
            "artifacts": [],
            "last_event_at": "",
            "last_event": {},
        }
        with self._lock:
            self._append_event_locked(task, event_type="info", message="后台任务已创建", data={"task_type": task_type})
            self._save_task_locked(task)
        return self.get_task(task_id)

    def _normalize_condition(self, task_type: str, condition: dict[str, Any]) -> dict[str, Any]:
        if task_type not in WAITABLE_TASK_TYPES:
            raise ValueError(f"Unsupported task_type: {task_type}")
        normalized = dict(condition)
        if task_type == "sleep":
            if "wake_at" not in normalized:
                if "duration_ms" not in normalized:
                    raise ValueError("sleep task requires wake_at or duration_ms")
                wake_at = _utc_now() + timedelta(milliseconds=int(normalized["duration_ms"]))
                normalized["wake_at"] = _to_iso(wake_at)
            else:
                normalized["wake_at"] = _to_iso(_parse_iso_datetime(str(normalized["wake_at"])))
        elif task_type == "wait_file":
            if not normalized.get("path"):
                raise ValueError("wait_file task requires path")
            normalized.setdefault("state", "exists")
            normalized.setdefault("encoding", "utf-8")
        elif task_type == "wait_process":
            if normalized.get("pid") is None and not normalized.get("name"):
                raise ValueError("wait_process task requires pid or name")
            normalized.setdefault("state", "running")
        elif task_type == "wait_port":
            if not normalized.get("host") or normalized.get("port") is None:
                raise ValueError("wait_port task requires host and port")
            normalized["port"] = int(normalized["port"])
            normalized.setdefault("state", "open")
            normalized.setdefault("connect_timeout_ms", 1500)
        elif task_type == "wait_http":
            if not normalized.get("url"):
                raise ValueError("wait_http task requires url")
            normalized.setdefault("expected_statuses", [200])
            normalized.setdefault("method", "GET")
            normalized.setdefault("headers", {})
            normalized.setdefault("request_timeout_ms", 5000)
        elif task_type == "wait_window":
            normalized["hwnd"] = _normalize_hwnd(normalized.get("hwnd"))
            if not normalized.get("title_filter") and not normalized["hwnd"] and not normalized.get("process_name"):
                raise ValueError("wait_window task requires title_filter, hwnd, or process_name")
            normalized.setdefault("state", "appeared")
            normalized.setdefault("include_invisible", False)
            normalized.setdefault("limit", 500)
        elif task_type == "wait_desktop_change":
            normalized.setdefault("include_invisible", False)
            normalized.setdefault("limit", 50)
            normalized["baseline_snapshot"] = normalized.get("baseline_snapshot") or _capture_desktop_snapshot(
                include_invisible=bool(normalized["include_invisible"]),
                limit=int(normalized["limit"]),
            )
        return normalized

    def list_tasks(self, *, statuses: list[str] | None = None, limit: int = 100) -> dict[str, Any]:
        with self._lock:
            tasks = list(self._tasks.values())
        if statuses:
            allowed = {item for item in statuses}
            tasks = [task for task in tasks if task["status"] in allowed]
        tasks.sort(key=lambda item: (item["status"], item.get("updated_at", "")), reverse=True)
        return {
            "count": len(tasks[:limit]),
            "total_count": len(tasks),
            "tasks": [self._copy_task(item) for item in tasks[:limit]],
        }

    def get_task(self, task_id: str) -> dict[str, Any]:
        with self._lock:
            task = self._tasks.get(task_id)
            if task is None:
                raise KeyError(f"Background task not found: {task_id}")
            return self._copy_task(task)

    def cancel_task(self, task_id: str, reason: str | None = None) -> dict[str, Any]:
        with self._lock:
            task = self._require_task_locked(task_id)
            if task["status"] in FINAL_TASK_STATUSES:
                return self._copy_task(task)
            self._transition_status_locked(task, "cancelled", message=reason or "后台任务已取消", event_type="warning")
            return self._copy_task(task)

    def pause_task(self, task_id: str, reason: str | None = None) -> dict[str, Any]:
        with self._lock:
            task = self._require_task_locked(task_id)
            if task["status"] in FINAL_TASK_STATUSES:
                return self._copy_task(task)
            self._transition_status_locked(task, "paused", message=reason or "后台任务已暂停")
            return self._copy_task(task)

    def resume_task(self, task_id: str, reason: str | None = None) -> dict[str, Any]:
        with self._lock:
            task = self._require_task_locked(task_id)
            if task["status"] not in {"paused", "waiting", "waiting_for_user", "waiting_for_condition"}:
                return self._copy_task(task)
            task["next_check_at"] = _iso_now()
            self._transition_status_locked(task, "pending", message=reason or "后台任务已恢复")
            return self._copy_task(task)

    def mark_waiting_for_user(self, task_id: str, question: str) -> dict[str, Any]:
        with self._lock:
            task = self._require_task_locked(task_id)
            self._transition_status_locked(
                task,
                "waiting_for_user",
                message=question,
                event_type="warning",
                data={"question": question},
            )
            return self._copy_task(task)

    def mark_waiting_for_condition(self, task_id: str, note: str) -> dict[str, Any]:
        with self._lock:
            task = self._require_task_locked(task_id)
            self._transition_status_locked(
                task,
                "waiting_for_condition",
                message=note,
                event_type="info",
                data={"note": note},
            )
            return self._copy_task(task)

    def create_plan(self, task_id: str, steps: list[str]) -> dict[str, Any]:
        normalized_steps = []
        for index, step in enumerate(steps, start=1):
            normalized_steps.append(
                {
                    "step_id": uuid.uuid4().hex,
                    "index": index,
                    "title": step,
                    "status": "pending",
                    "note": "",
                    "updated_at": _iso_now(),
                }
            )
        with self._lock:
            task = self._require_task_locked(task_id)
            task["plan_steps"] = normalized_steps
            self._append_event_locked(task, event_type="decision", message="任务步骤计划已创建", data={"step_count": len(steps)})
            self._save_task_locked(task)
            return self._copy_task(task)

    def update_task_step(self, task_id: str, step_index: int, status: str, note: str | None = None) -> dict[str, Any]:
        if status not in {"pending", "in_progress", "completed", "failed", "skipped"}:
            raise ValueError("Unsupported task step status")
        with self._lock:
            task = self._require_task_locked(task_id)
            matched = None
            for step in task.get("plan_steps", []):
                if step["index"] == step_index:
                    matched = step
                    break
            if matched is None:
                raise KeyError(f"Task step not found: {step_index}")
            matched["status"] = status
            matched["note"] = note or matched.get("note", "")
            matched["updated_at"] = _iso_now()
            self._append_event_locked(
                task,
                event_type="progress",
                message=f"任务步骤 {step_index} 已更新为 {status}",
                data={"step_index": step_index, "status": status, "note": matched["note"]},
            )
            self._save_task_locked(task)
            return self._copy_task(task)

    def append_task_event(
        self,
        task_id: str,
        *,
        event_type: str,
        message: str,
        data: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        with self._lock:
            task = self._require_task_locked(task_id)
            event = self._append_event_locked(task, event_type=event_type, message=message, data=data)
            self._save_task_locked(task)
            return event

    def record_artifact(self, task_id: str, *, path: str, description: str | None = None) -> dict[str, Any]:
        artifact_path = Path(path).expanduser().resolve()
        artifact = {
            "artifact_id": uuid.uuid4().hex,
            "path": str(artifact_path),
            "description": description or "",
            "exists": artifact_path.exists(),
            "recorded_at": _iso_now(),
        }
        with self._lock:
            task = self._require_task_locked(task_id)
            task.setdefault("artifacts", []).append(artifact)
            self._append_event_locked(
                task,
                event_type="artifact",
                message="任务产物已记录",
                data={"path": str(artifact_path), "description": artifact["description"]},
            )
            self._save_task_locked(task)
            return artifact

    def read_recent_events(self, task_id: str, limit: int = 20) -> list[dict[str, Any]]:
        path = self._events_path(task_id)
        if not path.exists():
            return []
        lines = path.read_text(encoding="utf-8").splitlines()
        events: list[dict[str, Any]] = []
        for line in reversed(lines):
            if not line.strip():
                continue
            try:
                parsed = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(parsed, dict):
                events.append(parsed)
            if len(events) >= limit:
                break
        events.reverse()
        return events

    def summarize_task(self, task_id: str, *, include_recent_events: int = 10) -> dict[str, Any]:
        task = self.get_task(task_id)
        recent_events = self.read_recent_events(task_id, limit=include_recent_events)
        summary_lines = [
            f"任务ID：{task['task_id']}",
            f"标题：{task['title']}",
            f"目标：{task['goal']}",
            f"类型：{task['task_type']}",
            f"状态：{task['status']}",
            f"优先级：{task['priority']}",
            f"创建时间：{task['created_at']}",
            f"更新时间：{task['updated_at']}",
        ]
        if task.get("deadline_at"):
            summary_lines.append(f"截止时间：{task['deadline_at']}")
        if task.get("last_error"):
            summary_lines.append(f"最后错误：{task['last_error']}")
        if task.get("last_result"):
            summary_lines.append(f"最近观测：{json.dumps(task['last_result'], ensure_ascii=False)}")
        if task.get("plan_steps"):
            summary_lines.append("步骤计划：")
            for step in task["plan_steps"]:
                summary_lines.append(f"- [{step['status']}] {step['index']}. {step['title']}")
        if recent_events:
            summary_lines.append("最近事件：")
            for event in recent_events:
                summary_lines.append(f"- {event['timestamp']} [{event['type']}] {event['message']}")
        return {
            "task": task,
            "recent_events": recent_events,
            "summary": "\n".join(summary_lines),
        }

    def get_task_handoff(self, task_id: str, *, include_recent_events: int = 10) -> dict[str, Any]:
        task = self.get_task(task_id)
        recent_events = self.read_recent_events(task_id, limit=include_recent_events)
        plan_steps = task.get("plan_steps", [])
        current_step = _current_step(plan_steps)
        completed_steps = [step for step in plan_steps if step.get("status") == "completed"]
        pending_steps = [step for step in plan_steps if step.get("status") != "completed"]
        blocker = _infer_task_blocker(task, recent_events)
        suggestions = _suggest_next_actions(task, current_step)

        handoff_lines = [
            f"任务标题：{task['title']}",
            f"任务ID：{task['task_id']}",
            f"当前状态：{task['status']}",
            f"任务目标：{task['goal']}",
        ]
        if current_step is not None:
            handoff_lines.append(
                f"当前步骤：{current_step.get('index')}. {current_step.get('title')} [{current_step.get('status')}]"
            )
        if blocker:
            handoff_lines.append(f"当前阻塞：{blocker}")
        if task.get("last_result"):
            handoff_lines.append(f"最近观测：{json.dumps(task['last_result'], ensure_ascii=False)}")
        if task.get("artifacts"):
            handoff_lines.append("任务产物：")
            for artifact in task["artifacts"][-10:]:
                handoff_lines.append(f"- {artifact['path']} ({artifact.get('description') or '无描述'})")
        if recent_events:
            handoff_lines.append("最近事件：")
            for event in recent_events[-10:]:
                handoff_lines.append(f"- {event['timestamp']} [{event['type']}] {event['message']}")
        if suggestions:
            handoff_lines.append("建议下一步：")
            for item in suggestions:
                handoff_lines.append(f"- {item}")

        return {
            "task_id": task["task_id"],
            "status": task["status"],
            "goal": task["goal"],
            "task_type": task["task_type"],
            "current_step": current_step,
            "completed_steps": completed_steps,
            "pending_steps": pending_steps,
            "recent_events": recent_events,
            "last_result": task.get("last_result", {}),
            "last_error": task.get("last_error", ""),
            "artifacts": task.get("artifacts", []),
            "blocker": blocker,
            "suggested_next_actions": suggestions,
            "handoff": "\n".join(handoff_lines),
            "summary": self.summarize_task(task_id, include_recent_events=include_recent_events)["summary"],
        }

    def _require_task_locked(self, task_id: str) -> dict[str, Any]:
        task = self._tasks.get(task_id)
        if task is None:
            raise KeyError(f"Background task not found: {task_id}")
        return task

    def _copy_task(self, task: dict[str, Any]) -> dict[str, Any]:
        return json.loads(json.dumps(task, ensure_ascii=False))

    def _scheduler_loop(self) -> None:
        while not self._stop_event.is_set():
            try:
                self._run_scheduler_once()
            except Exception as exc:
                with self._lock:
                    self._record_scheduler_error_locked(f"{type(exc).__name__}: {exc}")
            self._stop_event.wait(self.scheduler_interval_ms / 1000)

    def _run_scheduler_once(self) -> None:
        due_task_ids: list[str] = []
        now = _utc_now()
        with self._lock:
            for task in self._tasks.values():
                if task["status"] not in ACTIVE_TASK_STATUSES:
                    continue
                try:
                    if task.get("next_check_at") and _parse_iso_datetime(task["next_check_at"]) > now:
                        continue
                except Exception as exc:
                    task["last_error"] = f"Invalid next_check_at: {exc}"
                    self._transition_status_locked(
                        task,
                        "failed",
                        message=f"后台任务时间字段损坏，无法继续调度: {exc}",
                        event_type="error",
                    )
                    continue
                due_task_ids.append(task["task_id"])
        for task_id in due_task_ids:
            try:
                self._evaluate_task(task_id)
            except Exception as exc:
                with self._lock:
                    self._record_scheduler_error_locked(f"Task {task_id} crashed: {type(exc).__name__}: {exc}")
                    try:
                        task = self._require_task_locked(task_id)
                    except KeyError:
                        continue
                    task["last_error"] = str(exc)
                    self._transition_status_locked(
                        task,
                        "failed",
                        message=f"后台任务执行时出现未捕获异常: {exc}",
                        event_type="error",
                    )

    def _evaluate_task(self, task_id: str) -> None:
        with self._lock:
            task = self._require_task_locked(task_id)
            if task["status"] not in ACTIVE_TASK_STATUSES:
                return
            if task.get("deadline_at"):
                deadline = _parse_iso_datetime(task["deadline_at"])
                if _utc_now() >= deadline:
                    task["last_error"] = "后台任务等待超时"
                    self._transition_status_locked(task, "failed", message="后台任务等待超时", event_type="error")
                    return
            if task["status"] == "pending":
                self._transition_status_locked(task, "running", message="后台任务开始执行")
                task = self._require_task_locked(task_id)

        try:
            result = _evaluate_task_condition(task["task_type"], task["condition"])
        except Exception as exc:
            with self._lock:
                task = self._require_task_locked(task_id)
                task["last_error"] = str(exc)
                self._transition_status_locked(task, "failed", message=f"后台任务执行失败: {exc}", event_type="error")
            return

        with self._lock:
            task = self._require_task_locked(task_id)
            task["check_count"] = int(task.get("check_count", 0)) + 1
            task["last_checked_at"] = _iso_now()
            task["last_result"] = result
            task["last_error"] = ""

            if result.get("fatal_error"):
                task["last_error"] = result.get("error") or "后台任务无法继续执行"
                self._transition_status_locked(
                    task,
                    "failed",
                    message=f"后台任务无法继续执行: {task['last_error']}",
                    event_type="error",
                )
                return

            if result.get("condition_met"):
                self._transition_status_locked(task, "completed", message="后台任务条件已满足")
            else:
                wait_status = "waiting" if task["task_type"] == "sleep" else "waiting_for_condition"
                task["status"] = wait_status
                task["next_check_at"] = _to_iso(_utc_now() + timedelta(milliseconds=task["poll_interval_ms"]))
                self._append_event_locked(
                    task,
                    event_type="wait_started",
                    message="后台任务继续等待条件满足",
                    data={"next_check_at": task["next_check_at"]},
                )
                self._save_task_locked(task)


def get_background_task_manager() -> BackgroundTaskManager:
    global _MANAGER_SINGLETON
    with _MANAGER_LOCK:
        if _MANAGER_SINGLETON is None:
            _MANAGER_SINGLETON = BackgroundTaskManager()
        return _MANAGER_SINGLETON
