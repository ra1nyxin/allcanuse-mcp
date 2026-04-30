from __future__ import annotations

import http.server
import json
import shutil
import socket
import threading
import unittest
import uuid
from datetime import datetime, timedelta, timezone as dt_timezone
from pathlib import Path
from unittest.mock import patch

from allcanuse_mcp.core.duty import BackgroundTaskManager
from allcanuse_mcp.core.duty import get_scheduler_time
from allcanuse_mcp.core.duty import wait
from allcanuse_mcp.core.duty import wait_for_background_task
from allcanuse_mcp.core.duty import wait_for_desktop_change
from allcanuse_mcp.core.duty import wait_for_file
from allcanuse_mcp.core.duty import wait_for_http
from allcanuse_mcp.core.duty import wait_for_port
from allcanuse_mcp.core.duty import wait_for_window
from allcanuse_mcp.core.duty import wait_until


class DutyTests(unittest.TestCase):
    def test_wait_and_wait_until(self) -> None:
        result = wait(duration_ms=20, reason="test")
        self.assertTrue(result["ok"])
        self.assertGreaterEqual(result["waited_ms"], 10)

        past = (datetime.now(dt_timezone.utc) - timedelta(seconds=1)).isoformat()
        until = wait_until(timestamp=past, reason="past")
        self.assertTrue(until["ok"])
        self.assertEqual(until["remaining_ms_when_started"], 0)

    def test_wait_for_file_existing(self) -> None:
        target = _workspace_test_file("duty_file.txt")
        try:
            target.write_text("ready", encoding="utf-8")
            result = wait_for_file(path=str(target), text_contains="ready", timeout_ms=2000, poll_interval_ms=50)
            self.assertTrue(result["ok"])
            self.assertTrue(result["last_result"]["condition_met"])
        finally:
            target.unlink(missing_ok=True)

    def test_wait_for_port_open(self) -> None:
        listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        listener.bind(("127.0.0.1", 0))
        listener.listen(1)
        port = listener.getsockname()[1]
        try:
            result = wait_for_port("127.0.0.1", port, timeout_ms=2000, poll_interval_ms=50)
            self.assertTrue(result["ok"])
            self.assertTrue(result["last_result"]["is_open"])
        finally:
            listener.close()

    def test_wait_for_http_200(self) -> None:
        with _local_http_site({"probe": (200, {"Content-Type": "text/plain; charset=utf-8"}, "ready ok")}) as base_url:
            result = wait_for_http(
                url=f"{base_url}/probe",
                expected_statuses=[200],
                text_contains="ready",
                timeout_ms=2000,
                poll_interval_ms=50,
                request_timeout_ms=1000,
            )
        self.assertTrue(result["ok"])
        self.assertEqual(result["last_result"]["status"], 200)

    def test_wait_for_window_foreground(self) -> None:
        with patch(
            "allcanuse_mcp.core.duty.list_windows_info",
            return_value={
                "ok": True,
                "platform": "Windows",
                "windows": [
                    {"hwnd": 100, "title": "Chrome - Test", "process_name": "chrome.exe", "visible": True, "is_foreground": True},
                    {"hwnd": 101, "title": "Other", "process_name": "other.exe", "visible": True, "is_foreground": False},
                ],
            },
        ):
            result = wait_for_window(title_filter="chrome", state="foreground", timeout_ms=2000, poll_interval_ms=50)
        self.assertTrue(result["ok"])
        self.assertEqual(result["last_result"]["foreground_match_count"], 1)

    def test_wait_for_desktop_change_detects_change(self) -> None:
        snapshots = [
            {
                "ok": True,
                "platform": "Windows",
                "windows": [
                    {"hwnd": 1, "title": "A", "pid": 11, "process_name": "app.exe", "visible": True, "is_foreground": True},
                ],
            },
            {
                "ok": True,
                "platform": "Windows",
                "windows": [
                    {"hwnd": 2, "title": "B", "pid": 12, "process_name": "setup.exe", "visible": True, "is_foreground": True},
                ],
            },
        ]
        with patch("allcanuse_mcp.core.duty.list_windows_info", side_effect=snapshots):
            result = wait_for_desktop_change(timeout_ms=2000, poll_interval_ms=50)
        self.assertTrue(result["ok"])
        self.assertTrue(result["last_result"]["signature_changed"])
        self.assertTrue(result["last_result"]["foreground_changed"])

    def test_wait_for_desktop_change_returns_fatal_result_when_desktop_unavailable(self) -> None:
        with patch(
            "allcanuse_mcp.core.duty.list_windows_info",
            return_value={"ok": False, "platform": "Linux", "error": "No graphical desktop session was detected."},
        ):
            result = wait_for_desktop_change(timeout_ms=2000, poll_interval_ms=50)
        self.assertFalse(result["ok"])
        self.assertTrue(result["fatal_error"])
        self.assertIn("graphical", result["last_result"]["error"])

    def test_background_sleep_task_completes_and_persists(self) -> None:
        manager = _test_manager()
        try:
            task = manager.create_task(
                title="sleep once",
                goal="wait a little",
                task_type="sleep",
                condition={"duration_ms": 150},
                poll_interval_ms=50,
                timeout_ms=3000,
            )
            waited = wait_for_background_task(manager, task["task_id"], timeout_ms=4000, poll_interval_ms=50)
            self.assertTrue(waited["ok"])
            final_task = manager.get_task(task["task_id"])
            self.assertEqual(final_task["status"], "completed")
            self.assertTrue(manager._task_path(task["task_id"]).exists())
            self.assertTrue(manager._events_path(task["task_id"]).exists())
        finally:
            manager.shutdown()
            _cleanup_manager_dir(manager)

    def test_background_wait_window_task_completes(self) -> None:
        manager = _test_manager()
        try:
            with patch(
                "allcanuse_mcp.core.duty.list_windows_info",
                return_value={
                    "ok": True,
                    "platform": "Windows",
                    "windows": [
                        {"hwnd": 99, "title": "Installer Setup", "pid": 88, "process_name": "setup.exe", "visible": True, "is_foreground": False},
                    ],
                },
            ):
                task = manager.create_task(
                    title="wait setup window",
                    goal="observe installer",
                    task_type="wait_window",
                    condition={"title_filter": "Setup", "state": "appeared"},
                    poll_interval_ms=50,
                    timeout_ms=2000,
                )
                waited = wait_for_background_task(manager, task["task_id"], timeout_ms=3000, poll_interval_ms=50)
            self.assertTrue(waited["ok"])
            self.assertEqual(manager.get_task(task["task_id"])["status"], "completed")
        finally:
            manager.shutdown()
            _cleanup_manager_dir(manager)

    def test_resume_task_supports_waiting_for_condition(self) -> None:
        manager = _test_manager()
        artifact = _workspace_test_file("duty_resume.txt")
        try:
            task = manager.create_task(
                title="wait for missing file",
                goal="observe file creation",
                task_type="wait_file",
                condition={"path": str(artifact), "state": "exists"},
                poll_interval_ms=5000,
                timeout_ms=10000,
            )
            manager.mark_waiting_for_condition(task["task_id"], "等待外部文件生成")
            resumed = manager.resume_task(task["task_id"], reason="立即重试")
            self.assertEqual(resumed["status"], "pending")
        finally:
            artifact.unlink(missing_ok=True)
            manager.shutdown()
            _cleanup_manager_dir(manager)

    def test_scheduler_survives_invalid_next_check_at(self) -> None:
        manager = _test_manager()
        try:
            task = manager.create_task(
                title="broken schedule",
                goal="simulate corrupted task time",
                task_type="sleep",
                condition={"duration_ms": 1000},
                poll_interval_ms=100,
                timeout_ms=3000,
            )
            with manager._lock:
                stored = manager._require_task_locked(task["task_id"])
                stored["next_check_at"] = "not-a-timestamp"
                manager._save_task_locked(stored)
            manager._run_scheduler_once()
            broken = manager.get_task(task["task_id"])
            self.assertEqual(broken["status"], "failed")
            self.assertIn("Invalid next_check_at", broken["last_error"])
        finally:
            manager.shutdown()
            _cleanup_manager_dir(manager)

    def test_load_tasks_quarantines_corrupted_json(self) -> None:
        runtime_dir = Path.cwd() / ".test-temp" / f"duty-load-{uuid.uuid4().hex}"
        runtime_dir.mkdir(parents=True, exist_ok=True)
        broken_path = runtime_dir / "broken.json"
        broken_path.write_text("{not valid json", encoding="utf-8")
        manager = BackgroundTaskManager(storage_dir=runtime_dir, scheduler_interval_ms=50)
        try:
            health = manager.scheduler_health()
            self.assertEqual(health["load_issue_count"], 1)
            self.assertFalse(broken_path.exists())
            corrupted_files = list((runtime_dir / "corrupted").glob("broken.json.*.corrupt"))
            self.assertTrue(corrupted_files)
        finally:
            manager.shutdown()
            shutil.rmtree(runtime_dir, ignore_errors=True)

    def test_read_recent_events_skips_bad_lines(self) -> None:
        manager = _test_manager()
        try:
            task = manager.create_task(
                title="events",
                goal="read recent events safely",
                task_type="sleep",
                condition={"duration_ms": 1000},
                poll_interval_ms=100,
                timeout_ms=3000,
            )
            manager.append_task_event(task["task_id"], event_type="info", message="good one")
            path = manager._events_path(task["task_id"])
            with path.open("a", encoding="utf-8") as file:
                file.write("not-json-line\n")
            manager.append_task_event(task["task_id"], event_type="info", message="good two")
            events = manager.read_recent_events(task["task_id"], limit=10)
            messages = [event["message"] for event in events]
            self.assertIn("good one", messages)
            self.assertIn("good two", messages)
        finally:
            manager.shutdown()
            _cleanup_manager_dir(manager)

    def test_background_task_plan_event_artifact_summary_and_handoff(self) -> None:
        manager = _test_manager()
        artifact = _workspace_test_file("duty_artifact.txt")
        try:
            artifact.write_text("artifact", encoding="utf-8")
            task = manager.create_task(
                title="wait for file",
                goal="observe file state",
                task_type="wait_file",
                condition={"path": str(artifact), "state": "exists"},
                poll_interval_ms=100,
                timeout_ms=2000,
            )
            manager.create_plan(task["task_id"], ["检查文件", "记录结果"])
            manager.update_task_step(task["task_id"], 1, "completed", note="文件已存在")
            manager.mark_waiting_for_user(task["task_id"], "是否继续执行第二步？")
            manager.append_task_event(task["task_id"], event_type="decision", message="进入交接阶段")
            manager.record_artifact(task["task_id"], path=str(artifact), description="测试产物")

            summary = manager.summarize_task(task["task_id"], include_recent_events=10)
            handoff = manager.get_task_handoff(task["task_id"], include_recent_events=10)

            self.assertIn("wait_file", summary["summary"])
            self.assertIn("进入交接阶段", summary["summary"])
            self.assertEqual(summary["task"]["plan_steps"][0]["status"], "completed")
            self.assertIn("当前阻塞", handoff["handoff"])
            self.assertIn("是否继续执行第二步", handoff["handoff"])
            self.assertTrue(handoff["suggested_next_actions"])

            artifacts_payload = json.loads(manager._artifacts_path(task["task_id"]).read_text(encoding="utf-8"))
            self.assertEqual(artifacts_payload["artifacts"][0]["description"], "测试产物")
        finally:
            artifact.unlink(missing_ok=True)
            manager.shutdown()
            _cleanup_manager_dir(manager)

    def test_scheduler_time_reports_counts(self) -> None:
        manager = _test_manager()
        try:
            manager.create_task(
                title="long sleep",
                goal="count task status",
                task_type="sleep",
                condition={"duration_ms": 500},
                poll_interval_ms=100,
                timeout_ms=2000,
            )
            info = get_scheduler_time(manager)
            self.assertIn("task_status_counts", info)
        finally:
            manager.shutdown()
            _cleanup_manager_dir(manager)


class _SiteContext:
    def __init__(self, routes: dict[str, tuple[int, dict[str, str], str]]) -> None:
        self.routes = routes
        self.server: http.server.ThreadingHTTPServer | None = None
        self.thread: threading.Thread | None = None
        self.base_url = ""

    def __enter__(self) -> str:
        routes = {f"/{key.lstrip('/')}": value for key, value in self.routes.items()}

        class Handler(http.server.BaseHTTPRequestHandler):
            def do_GET(self) -> None:  # noqa: N802
                path = self.path.split("?", 1)[0]
                route = routes.get(path)
                if route is None:
                    self.send_response(404)
                    self.end_headers()
                    return
                status, headers, body = route
                payload = body.encode("utf-8")
                self.send_response(status)
                for key, value in headers.items():
                    self.send_header(key, value)
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)

            def log_message(self, format: str, *args) -> None:  # noqa: A003
                return

        self.server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base_url = f"http://127.0.0.1:{self.server.server_address[1]}"
        return self.base_url

    def __exit__(self, exc_type, exc, tb) -> None:
        assert self.server is not None
        assert self.thread is not None
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=1)


def _local_http_site(routes: dict[str, tuple[int, dict[str, str], str]]) -> _SiteContext:
    return _SiteContext(routes)


def _workspace_test_file(name: str) -> Path:
    path = Path.cwd() / "tests" / name
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _test_manager() -> BackgroundTaskManager:
    runtime_dir = Path.cwd() / ".test-temp" / f"duty-{uuid.uuid4().hex}"
    runtime_dir.mkdir(parents=True, exist_ok=True)
    return BackgroundTaskManager(storage_dir=runtime_dir, scheduler_interval_ms=50)


def _cleanup_manager_dir(manager: BackgroundTaskManager) -> None:
    shutil.rmtree(manager.storage_dir, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
