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
        owner: str | None = None,
        tags: list[str] | None = None,
        protect_from_accidental_kill: bool = True,
        notes: str | None = None,
    ) -> dict[str, Any]:
        record_id = f"mp-{uuid.uuid4().hex[:12]}"
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

    def get_process(self, record_id: str) -> dict[str, Any]:
        with self.lock:
            data = _load_index()
            entry = data["processes"].get(record_id)
            if not entry:
                return {"ok": False, "error": f"Managed process `{record_id}` was not found."}
            refreshed = self._refresh_entry(dict(entry))
            data["processes"][record_id] = refreshed
            _save_index(data)
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
