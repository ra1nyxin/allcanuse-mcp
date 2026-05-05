from __future__ import annotations

import os
import subprocess

try:
    import psutil
except ImportError:
    psutil = None

from allcanuse_mcp.core.command_runner import run_cmd as run_cmd_impl
from allcanuse_mcp.core.command_runner import run_powershell as run_powershell_impl
from allcanuse_mcp.core.command_runner import run_shell as run_shell_impl
from allcanuse_mcp.core import linux_fallbacks
from allcanuse_mcp.core.managed_processes import get_managed_process_registry
from allcanuse_mcp.descriptions import TOOL_DESCRIPTIONS


def register(mcp) -> None:
    registry = get_managed_process_registry()

    @mcp.tool(description=TOOL_DESCRIPTIONS["run_shell"])
    def run_shell(
        command: str,
        cwd: str | None = None,
        timeout_ms: int = 30_000,
        encoding: str = "utf-8",
        max_output_chars: int = 20_000,
    ) -> dict:
        return run_shell_impl(
            command,
            cwd=cwd,
            timeout_ms=timeout_ms,
            encoding=encoding,
            max_output_chars=max_output_chars,
        )

    @mcp.tool(description=TOOL_DESCRIPTIONS["run_cmd"])
    def run_cmd(
        command: str,
        cwd: str | None = None,
        timeout_ms: int = 30_000,
        encoding: str = "utf-8",
        max_output_chars: int = 20_000,
    ) -> dict:
        return run_cmd_impl(
            command,
            cwd=cwd,
            timeout_ms=timeout_ms,
            encoding=encoding,
            max_output_chars=max_output_chars,
        )

    @mcp.tool(description=TOOL_DESCRIPTIONS["run_powershell"])
    def run_powershell(
        script: str,
        cwd: str | None = None,
        timeout_ms: int = 30_000,
        encoding: str = "utf-8",
        max_output_chars: int = 20_000,
    ) -> dict:
        return run_powershell_impl(
            script,
            cwd=cwd,
            timeout_ms=timeout_ms,
            encoding=encoding,
            max_output_chars=max_output_chars,
        )

    @mcp.tool(description=TOOL_DESCRIPTIONS["start_process"])
    def start_process(command: str, cwd: str | None = None, detach: bool = True) -> dict:
        popen_kwargs = {
            "cwd": cwd or None,
            "shell": True,
            "stdout": subprocess.DEVNULL,
            "stderr": subprocess.DEVNULL,
            "stdin": subprocess.DEVNULL,
        }
        if os.name == "nt":
            creationflags = 0
            if detach:
                creationflags = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS
            popen_kwargs["creationflags"] = creationflags
        else:
            popen_kwargs["start_new_session"] = detach

        process = subprocess.Popen(command, **popen_kwargs)
        return {
            "ok": True,
            "pid": process.pid,
            "cwd": os.path.abspath(cwd) if cwd else os.getcwd(),
            "command": command,
            "detached": detach,
            "platform": os.name,
        }

    @mcp.tool(description=TOOL_DESCRIPTIONS["start_managed_process"])
    def start_managed_process(
        command: str,
        purpose: str,
        cwd: str | None = None,
        owner: str | None = None,
        tags: list[str] | None = None,
        protect_from_accidental_kill: bool = True,
        notes: str | None = None,
    ) -> dict:
        popen_kwargs = {
            "cwd": cwd or None,
            "shell": True,
            "stdout": subprocess.DEVNULL,
            "stderr": subprocess.DEVNULL,
            "stdin": subprocess.DEVNULL,
        }
        if os.name == "nt":
            popen_kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS
        else:
            popen_kwargs["start_new_session"] = True

        process = subprocess.Popen(command, **popen_kwargs)
        entry = registry.register_process(
            pid=process.pid,
            command=command,
            cwd=cwd,
            name=None,
            purpose=purpose,
            owner=owner,
            tags=tags,
            protect_from_accidental_kill=protect_from_accidental_kill,
            notes=notes,
        )
        return {
            "ok": True,
            "managed_process": entry,
            "message": "Long-running process started and registered for monitoring. Do not stop it unless the user explicitly asks to stop it.",
        }

    @mcp.tool(description=TOOL_DESCRIPTIONS["list_managed_processes"])
    def list_managed_processes(include_exited: bool = True) -> dict:
        return registry.list_processes(include_exited=include_exited)

    @mcp.tool(description=TOOL_DESCRIPTIONS["get_managed_process"])
    def get_managed_process(process_id: str) -> dict:
        return registry.get_process(process_id)

    @mcp.tool(description=TOOL_DESCRIPTIONS["note_managed_process"])
    def note_managed_process(process_id: str, note: str) -> dict:
        return registry.note_process(process_id, note)

    @mcp.tool(description=TOOL_DESCRIPTIONS["stop_managed_process"])
    def stop_managed_process(process_id: str, reason: str | None = None, force: bool = True) -> dict:
        return registry.stop_process(process_id, reason=reason, force=force)

    @mcp.tool(description=TOOL_DESCRIPTIONS["kill_process"])
    def kill_process(pid: int | None = None, name: str | None = None, force: bool = True) -> dict:
        if pid is None and not name:
            raise ValueError("Either pid or name must be provided.")

        if pid is not None:
            managed = registry.find_by_pid(pid)
            if managed and managed.get("protect_from_accidental_kill"):
                return {
                    "ok": False,
                    "blocked": True,
                    "error": "This PID is registered as a protected long-running managed process. Use `stop_managed_process` only after the user explicitly asks to stop it.",
                    "managed_process": managed,
                }

        if psutil is None and linux_fallbacks.linux_procfs_available():
            killed = linux_fallbacks.kill_processes(pid=pid, name=name, force=force)
            return {"requested_pid": pid, "requested_name": name, "killed": killed, "count": len(killed)}

        killed: list[dict] = []
        candidates = []
        if pid is not None:
            candidates.append(psutil.Process(pid))
        else:
            target_name = name.lower()
            for process in psutil.process_iter(["pid", "name"]):
                proc_name = (process.info.get("name") or "").lower()
                if proc_name == target_name:
                    candidates.append(process)

        for process in candidates:
            try:
                if force:
                    process.kill()
                else:
                    process.terminate()
                killed.append({"pid": process.pid, "name": process.name()})
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        return {"requested_pid": pid, "requested_name": name, "killed": killed, "count": len(killed)}

    @mcp.tool(description=TOOL_DESCRIPTIONS["list_processes"])
    def list_processes(name_filter: str | None = None, limit: int = 200) -> dict:
        if psutil is None and linux_fallbacks.linux_procfs_available():
            matched = linux_fallbacks.list_processes(limit=limit, name_filter=name_filter)
            return {"count": len(matched), "processes": matched}

        matched = []
        lowered = name_filter.lower() if name_filter else None
        for process in psutil.process_iter(["pid", "name", "status", "cpu_percent", "memory_info", "exe"]):
            info = process.info
            name = info.get("name") or ""
            if lowered and lowered not in name.lower():
                continue
            matched.append(
                {
                    "pid": info.get("pid"),
                    "name": name,
                    "status": info.get("status"),
                    "cpu_percent": info.get("cpu_percent"),
                    "memory_rss": getattr(info.get("memory_info"), "rss", None),
                    "exe": info.get("exe"),
                }
            )
            if len(matched) >= limit:
                break
        return {"count": len(matched), "processes": matched}

    @mcp.tool(description=TOOL_DESCRIPTIONS["get_process_tree"])
    def get_process_tree(pid: int | None = None, max_depth: int = 5) -> dict:
        if psutil is None and linux_fallbacks.linux_procfs_available():
            target_pid = pid if pid is not None else os.getpid()
            return linux_fallbacks.get_process_tree(target_pid, max_depth=max_depth)

        target = psutil.Process(pid) if pid is not None else psutil.Process()
        return {
            "root": _process_to_dict(target),
            "children": _collect_children(target, depth=1, max_depth=max_depth),
        }

    @mcp.tool(description=TOOL_DESCRIPTIONS["find_port_process"])
    def find_port_process(port: int) -> dict:
        if psutil is None and linux_fallbacks.linux_procfs_available():
            result = linux_fallbacks.find_port_process(port)
            return result or {"found": False, "port": port}

        for conn in psutil.net_connections(kind="inet"):
            if not conn.laddr or conn.laddr.port != port:
                continue
            proc_info = None
            if conn.pid:
                try:
                    proc = psutil.Process(conn.pid)
                    proc_info = _process_to_dict(proc)
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    proc_info = {"pid": conn.pid}
            return {
                "found": True,
                "port": port,
                "status": conn.status,
                "local_address": f"{conn.laddr.ip}:{conn.laddr.port}",
                "remote_address": (
                    f"{conn.raddr.ip}:{conn.raddr.port}" if conn.raddr else None
                ),
                "pid": conn.pid,
                "process": proc_info,
            }
        return {"found": False, "port": port}


def _collect_children(process: psutil.Process, *, depth: int, max_depth: int) -> list[dict]:
    if depth > max_depth:
        return []
    nodes = []
    try:
        children = process.children()
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        return nodes
    for child in children:
        node = _process_to_dict(child)
        node["children"] = _collect_children(child, depth=depth + 1, max_depth=max_depth)
        nodes.append(node)
    return nodes


def _process_to_dict(process: psutil.Process) -> dict:
    try:
        return {
            "pid": process.pid,
            "name": process.name(),
            "status": process.status(),
            "exe": process.exe(),
            "cmdline": process.cmdline(),
        }
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        return {"pid": process.pid}
