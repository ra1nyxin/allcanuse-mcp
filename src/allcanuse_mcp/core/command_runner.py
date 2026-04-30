from __future__ import annotations

import os
import platform
import shutil
import subprocess
from typing import Any


def truncate_text(text: str, max_chars: int) -> tuple[str, bool]:
    if max_chars <= 0:
        return text, False
    if len(text) <= max_chars:
        return text, False
    return text[:max_chars], True


def run_command(
    command: list[str],
    *,
    cwd: str | None = None,
    timeout_ms: int = 30_000,
    encoding: str = "utf-8",
    max_output_chars: int = 20_000,
) -> dict[str, Any]:
    completed = subprocess.run(
        command,
        cwd=cwd or None,
        capture_output=True,
        text=False,
        timeout=max(timeout_ms, 1) / 1000,
        shell=False,
    )
    stdout = completed.stdout.decode(encoding, errors="replace")
    stderr = completed.stderr.decode(encoding, errors="replace")
    truncated_stdout, stdout_cut = truncate_text(stdout, max_output_chars)
    truncated_stderr, stderr_cut = truncate_text(stderr, max_output_chars)
    return {
        "ok": completed.returncode == 0,
        "returncode": completed.returncode,
        "cwd": os.path.abspath(cwd) if cwd else os.getcwd(),
        "stdout": truncated_stdout,
        "stderr": truncated_stderr,
        "stdout_truncated": stdout_cut,
        "stderr_truncated": stderr_cut,
    }


def command_exists(command: str) -> bool:
    return shutil.which(command) is not None


def run_shell(
    command: str,
    *,
    cwd: str | None = None,
    timeout_ms: int = 30_000,
    encoding: str = "utf-8",
    max_output_chars: int = 20_000,
) -> dict[str, Any]:
    if platform.system() == "Windows":
        argv = ["cmd.exe", "/d", "/c", command]
        shell_name = "cmd.exe"
    else:
        shell_path = os.environ.get("SHELL") or "/bin/sh"
        argv = [shell_path, "-lc", command]
        shell_name = shell_path

    result = run_command(
        argv,
        cwd=cwd,
        timeout_ms=timeout_ms,
        encoding=encoding,
        max_output_chars=max_output_chars,
    )
    result["shell"] = shell_name
    return result


def run_cmd(
    command: str,
    *,
    cwd: str | None = None,
    timeout_ms: int = 30_000,
    encoding: str = "utf-8",
    max_output_chars: int = 20_000,
) -> dict[str, Any]:
    return run_shell(
        command,
        cwd=cwd,
        timeout_ms=timeout_ms,
        encoding=encoding,
        max_output_chars=max_output_chars,
    )


def run_powershell(
    script: str,
    *,
    cwd: str | None = None,
    timeout_ms: int = 30_000,
    encoding: str = "utf-8",
    max_output_chars: int = 20_000,
) -> dict[str, Any]:
    pwsh = shutil.which("pwsh")
    powershell = shutil.which("powershell.exe")
    executable = pwsh or powershell
    if executable is None:
        return {
            "ok": False,
            "error": "PowerShell executable was not found on this host.",
            "suggestion": "Install PowerShell (`pwsh`) if the current task requires PowerShell-specific commands.",
        }

    argv = [executable]
    if platform.system() == "Windows" and executable.lower().endswith("powershell.exe"):
        argv.extend(["-NoProfile", "-ExecutionPolicy", "Bypass"])
    else:
        argv.append("-NoProfile")
    argv.extend(["-Command", script])
    result = run_command(
        argv,
        cwd=cwd,
        timeout_ms=timeout_ms,
        encoding=encoding,
        max_output_chars=max_output_chars,
    )
    result["executable"] = executable
    return result
