from __future__ import annotations

import json
import os
import platform
import subprocess
import threading
import uuid
from dataclasses import dataclass
from dataclasses import field
from datetime import datetime
from pathlib import Path
from typing import Any

try:
    import psutil
except ImportError:
    psutil = None


def _runtime_dir() -> Path:
    root = Path(__file__).resolve().parents[3]
    runtime_dir = root / "runtime" / "managed_processes"
    runtime_dir.mkdir(parents=True, exist_ok=True)
    return runtime_dir


def _logs_dir() -> Path:
    logs_dir = _runtime_dir() / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    return logs_dir


def _index_path() -> Path:
    return _runtime_dir() / "index.json"


def _now_iso() -> str:
    return datetime.now().astimezone().isoformat()


def _load_index() -> dict[str, Any]:
    path = _index_path()
    if not path.exists():
        return {"processes": {}}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"processes": {}}
    processes = data.get("processes")
    if not isinstance(processes, dict):
        return {"processes": {}}
    return {"processes": processes}


def _save_index(data: dict[str, Any]) -> None:
    path = _index_path()
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def prepare_managed_process_record_id() -> str:
    return f"mp-{uuid.uuid4().hex[:12]}"


def default_managed_process_log_paths(record_id: str) -> tuple[Path, Path]:
    logs_dir = _logs_dir()
    return logs_dir / f"{record_id}.stdout.log", logs_dir / f"{record_id}.stderr.log"


def _tail_text(path_value: str | None, max_chars: int) -> str:
    if not path_value or max_chars <= 0:
        return ""
    path = Path(path_value)
    if not path.exists() or not path.is_file():
        return ""
    read_size = min(max(max_chars * 4, 4096), 1_048_576)
    try:
        with path.open("rb") as handle:
            handle.seek(0, os.SEEK_END)
            size = handle.tell()
            handle.seek(max(0, size - read_size), os.SEEK_SET)
            data = handle.read()
        text = data.decode("utf-8", errors="replace")
    except OSError:
        return ""
    if len(text) > max_chars:
        return text[-max_chars:]
    return text


def _is_pid_running(pid: int) -> bool:
    if pid <= 0:
        return False
    if psutil is not None:
        try:
            return psutil.pid_exists(pid)
        except Exception:
            return False
    try:
        if platform.system() == "Windows":
            result = subprocess.run(
                ["cmd.exe", "/d", "/c", f"tasklist /FI \"PID eq {pid}\""],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=10,
            )
            return str(pid) in result.stdout
        os.kill(pid, 0)
        return True
    except Exception:
        return False


def _terminate_pid(pid: int, *, force: bool = True) -> bool:
    if psutil is not None:
        try:
            process = psutil.Process(pid)
            if force:
                process.kill()
            else:
                process.terminate()
            return True
        except Exception:
            return False
    try:
        if platform.system() == "Windows":
            flag = "/F" if force else ""
            command = ["taskkill", "/PID", str(pid)]
            if flag:
                command.append(flag)
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=15,
            )
            return result.returncode == 0
        sig = 9 if force else 15
        os.kill(pid, sig)
        return True
    except Exception:
        return False


@dataclass
class ManagedProcessRegistry:
    lock: threading.Lock = field(default_factory=threading.Lock)

    def _refresh_entry(self, entry: dict[str, Any]) -> dict[str, Any]:
        pid = int(entry.get("pid") or 0)
        running = _is_pid_running(pid)
        entry["running"] = running
        entry["last_checked_at"] = _now_iso()
        if not running and entry.get("status") not in {"stopped", "exited"}:
            entry["status"] = "exited"
        return entry

    def register_process(
        self,
        *,
        pid: int,
        command: str,
        cwd: str | None,
        name: str | None,
        purpose: str,
        record_id: str | None = None,
        owner: str | None = None,
        tags: list[str] | None = None,
        protect_from_accidental_kill: bool = True,
        notes: str | None = None,
        stdout_path: str | None = None,
        stderr_path: str | None = None,
    ) -> dict[str, Any]:
        record_id = record_id or prepare_managed_process_record_id()
        entry = {
            "id": record_id,
            "pid": pid,
            "command": command,
            "cwd": os.path.abspath(cwd) if cwd else os.getcwd(),
            "name": name,
            "purpose": purpose,
            "owner": owner,
            "tags": tags or [],
            "notes": notes,
            "stdout_path": stdout_path,
            "stderr_path": stderr_path,
            "protect_from_accidental_kill": protect_from_accidental_kill,
            "created_at": _now_iso(),
            "status": "running" if _is_pid_running(pid) else "exited",
            "running": _is_pid_running(pid),
            "last_checked_at": _now_iso(),
        }
        with self.lock:
            data = _load_index()
            data["processes"][record_id] = entry
            _save_index(data)
        return entry

    def list_processes(self, *, include_exited: bool = True) -> dict[str, Any]:
        with self.lock:
            data = _load_index()
            entries = [self._refresh_entry(dict(item)) for item in data["processes"].values()]
            data["processes"] = {item["id"]: item for item in entries}
            _save_index(data)
        if not include_exited:
            entries = [item for item in entries if item.get("running")]
        entries.sort(key=lambda item: item.get("created_at", ""), reverse=True)
        return {"count": len(entries), "processes": entries}

    def get_process(self, record_id: str, *, tail_chars: int = 4000) -> dict[str, Any]:
        with self.lock:
            data = _load_index()
            entry = data["processes"].get(record_id)
            if not entry:
                return {"ok": False, "error": f"Managed process `{record_id}` was not found."}
            refreshed = self._refresh_entry(dict(entry))
            data["processes"][record_id] = refreshed
            _save_index(data)
        if tail_chars > 0:
            refreshed["stdout_tail"] = _tail_text(refreshed.get("stdout_path"), tail_chars)
            refreshed["stderr_tail"] = _tail_text(refreshed.get("stderr_path"), tail_chars)
        return {"ok": True, "process": refreshed}

    def find_by_pid(self, pid: int) -> dict[str, Any] | None:
        with self.lock:
            data = _load_index()
            for entry in data["processes"].values():
                if int(entry.get("pid") or 0) == pid:
                    refreshed = self._refresh_entry(dict(entry))
                    data["processes"][refreshed["id"]] = refreshed
                    _save_index(data)
                    return refreshed
        return None

    def stop_process(self, record_id: str, *, force: bool = True, reason: str | None = None) -> dict[str, Any]:
        with self.lock:
            data = _load_index()
            entry = data["processes"].get(record_id)
            if not entry:
                return {"ok": False, "error": f"Managed process `{record_id}` was not found."}
            entry = self._refresh_entry(dict(entry))
            pid = int(entry.get("pid") or 0)
            if entry.get("running"):
                stopped = _terminate_pid(pid, force=force)
                if not stopped:
                    return {
                        "ok": False,
                        "error": f"Failed to stop managed process `{record_id}` (pid={pid}).",
                        "process": entry,
                    }
            entry["running"] = False
            entry["status"] = "stopped"
            entry["stopped_at"] = _now_iso()
            entry["stop_reason"] = reason
            data["processes"][record_id] = entry
            _save_index(data)
        return {"ok": True, "process": entry}

    def note_process(self, record_id: str, note: str) -> dict[str, Any]:
        with self.lock:
            data = _load_index()
            entry = data["processes"].get(record_id)
            if not entry:
                return {"ok": False, "error": f"Managed process `{record_id}` was not found."}
            entry = self._refresh_entry(dict(entry))
            entry["notes"] = note
            entry["updated_at"] = _now_iso()
            data["processes"][record_id] = entry
            _save_index(data)
        return {"ok": True, "process": entry}


_REGISTRY: ManagedProcessRegistry | None = None


def get_managed_process_registry() -> ManagedProcessRegistry:
    global _REGISTRY
    if _REGISTRY is None:
        _REGISTRY = ManagedProcessRegistry()
    return _REGISTRY
