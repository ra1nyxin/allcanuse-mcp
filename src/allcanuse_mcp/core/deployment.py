from __future__ import annotations

import fnmatch
import os
import shlex
import shutil
import subprocess
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any

from allcanuse_mcp.core.command_runner import run_shell


DEFAULT_EXCLUDE_PATTERNS = [
    ".git",
    ".hg",
    ".svn",
    ".venv",
    "venv",
    ".env",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".idea",
    ".vscode",
    "node_modules",
    "dist",
    "build",
    "runtime",
    "*.pyc",
    "*.pyo",
    "*.pyd",
]


def _run_command_capture(command: list[str], *, timeout_ms: int = 300_000) -> dict[str, Any]:
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


def _resolve_executable(name: str) -> str | None:
    return shutil.which(name)


def _should_exclude(name: str, patterns: list[str]) -> bool:
    for pattern in patterns:
        if fnmatch.fnmatch(name, pattern):
            return True
    return False


def _copy_source_tree(source: Path, stage_dir: Path, patterns: list[str]) -> None:
    def ignore(_current_dir: str, names: list[str]) -> set[str]:
        ignored: set[str] = set()
        for name in names:
            if _should_exclude(name, patterns):
                ignored.add(name)
        return ignored

    shutil.copytree(source, stage_dir, ignore=ignore)


def _make_archive(stage_dir: Path, archive_base: Path) -> Path:
    archive_path = Path(shutil.make_archive(str(archive_base), "gztar", root_dir=stage_dir))
    return archive_path


def _remote_spec(user: str | None, host: str, path: str) -> str:
    target = f"{user}@{host}" if user else host
    return f"{target}:{path}"


def _remote_quote(path: str) -> str:
    return shlex.quote(path)


def _ssh_base_args(
    ssh_executable: str,
    *,
    remote_user: str | None,
    remote_host: str,
    ssh_port: int,
    identity_file: str | None,
) -> list[str]:
    args = [ssh_executable, "-p", str(int(ssh_port))]
    if identity_file:
        args.extend(["-i", identity_file])
    args.extend([f"{remote_user}@{remote_host}" if remote_user else remote_host])
    return args


def _scp_base_args(
    scp_executable: str,
    *,
    remote_user: str | None,
    remote_host: str,
    ssh_port: int,
    identity_file: str | None,
) -> list[str]:
    args = [scp_executable, "-P", str(int(ssh_port))]
    if identity_file:
        args.extend(["-i", identity_file])
    return args


def _run_remote_command(
    ssh_executable: str,
    *,
    remote_user: str | None,
    remote_host: str,
    ssh_port: int,
    identity_file: str | None,
    remote_command: str,
    timeout_ms: int,
) -> dict[str, Any]:
    command = _ssh_base_args(
        ssh_executable,
        remote_user=remote_user,
        remote_host=remote_host,
        ssh_port=ssh_port,
        identity_file=identity_file,
    )
    command.extend(["sh", "-lc", remote_command])
    return _run_command_capture(command, timeout_ms=timeout_ms)


def _upload_archive(
    scp_executable: str,
    *,
    local_archive: Path,
    remote_user: str | None,
    remote_host: str,
    ssh_port: int,
    identity_file: str | None,
    remote_archive_path: str,
    timeout_ms: int,
) -> dict[str, Any]:
    command = _scp_base_args(
        scp_executable,
        remote_user=remote_user,
        remote_host=remote_host,
        ssh_port=ssh_port,
        identity_file=identity_file,
    )
    command.extend([str(local_archive), _remote_spec(remote_user, remote_host, remote_archive_path)])
    return _run_command_capture(command, timeout_ms=timeout_ms)


def deploy_and_update_service(
    *,
    source_path: str,
    remote_host: str,
    remote_path: str,
    remote_user: str | None = None,
    ssh_port: int = 22,
    identity_file: str | None = None,
    build_command: str | None = None,
    restart_command: str | None = None,
    health_check_command: str | None = None,
    exclude_patterns: list[str] | None = None,
    release_name: str | None = None,
    timeout_ms: int = 300_000,
) -> dict[str, Any]:
    source = Path(source_path).expanduser().resolve()
    if not source.exists() or not source.is_dir():
        return {"ok": False, "error": f"Source path is not a directory: {source}"}

    ssh_executable = _resolve_executable("ssh")
    scp_executable = _resolve_executable("scp")
    if ssh_executable is None or scp_executable is None:
        return {
            "ok": False,
            "error": "ssh/scp executable was not found.",
            "missing": [name for name, exe in (("ssh", ssh_executable), ("scp", scp_executable)) if exe is None],
        }

    release_name = release_name or datetime.now().astimezone().strftime("%Y%m%d-%H%M%S")
    patterns = list(DEFAULT_EXCLUDE_PATTERNS)
    if exclude_patterns:
        patterns.extend(exclude_patterns)

    build_result = None
    if build_command:
        build_result = run_shell(
            build_command,
            cwd=str(source),
            timeout_ms=timeout_ms,
            max_output_chars=20_000,
        )
        if not build_result.get("ok"):
            return {
                "ok": False,
                "stage": "build",
                "source_path": str(source),
                "release_name": release_name,
                "build_result": build_result,
            }

    stage_root = Path(tempfile.mkdtemp(prefix="allcanuse-deploy-"))
    archive_path: Path | None = None
    try:
        stage_dir = stage_root / "source"
        _copy_source_tree(source, stage_dir, patterns)
        archive_base = stage_root / release_name
        archive_path = _make_archive(stage_dir, archive_base)
        archive_size = archive_path.stat().st_size

        remote_base = remote_path.rstrip("/\\")
        remote_deploy_dir = f"{remote_base}/.deploy"
        remote_release_dir = f"{remote_base}/releases/{release_name}"
        remote_current_link = f"{remote_base}/current"
        remote_archive_path = f"{remote_deploy_dir}/{release_name}.tar.gz"

        mkdir_result = _run_remote_command(
            ssh_executable,
            remote_user=remote_user,
            remote_host=remote_host,
            ssh_port=ssh_port,
            identity_file=identity_file,
            remote_command=(
                f"mkdir -p {_remote_quote(remote_deploy_dir)} "
                f"{_remote_quote(f'{remote_base}/releases')} "
                f"{_remote_quote(remote_release_dir)}"
            ),
            timeout_ms=timeout_ms,
        )
        if not mkdir_result.get("ok"):
            return {
                "ok": False,
                "stage": "prepare_remote",
                "source_path": str(source),
                "release_name": release_name,
                "build_result": build_result,
                "mkdir_result": mkdir_result,
            }

        upload_result = _upload_archive(
            scp_executable,
            local_archive=archive_path,
            remote_user=remote_user,
            remote_host=remote_host,
            ssh_port=ssh_port,
            identity_file=identity_file,
            remote_archive_path=remote_archive_path,
            timeout_ms=timeout_ms,
        )
        if not upload_result.get("ok"):
            return {
                "ok": False,
                "stage": "upload",
                "source_path": str(source),
                "release_name": release_name,
                "build_result": build_result,
                "mkdir_result": mkdir_result,
                "upload_result": upload_result,
            }

        deploy_script = (
            "set -e\n"
            f"mkdir -p {_remote_quote(remote_release_dir)}\n"
            f"tar -xzf {_remote_quote(remote_archive_path)} -C {_remote_quote(remote_release_dir)} --strip-components=1\n"
            f"ln -sfn {_remote_quote(remote_release_dir)} {_remote_quote(remote_current_link)}\n"
            f"rm -f {_remote_quote(remote_archive_path)}\n"
        )
        extract_result = _run_remote_command(
            ssh_executable,
            remote_user=remote_user,
            remote_host=remote_host,
            ssh_port=ssh_port,
            identity_file=identity_file,
            remote_command=deploy_script,
            timeout_ms=timeout_ms,
        )
        if not extract_result.get("ok"):
            return {
                "ok": False,
                "stage": "extract",
                "source_path": str(source),
                "release_name": release_name,
                "build_result": build_result,
                "mkdir_result": mkdir_result,
                "upload_result": upload_result,
                "extract_result": extract_result,
            }

        restart_result = None
        if restart_command:
            restart_result = _run_remote_command(
                ssh_executable,
                remote_user=remote_user,
                remote_host=remote_host,
                ssh_port=ssh_port,
                identity_file=identity_file,
                remote_command=f"cd {_remote_quote(remote_current_link)} && {restart_command}",
                timeout_ms=timeout_ms,
            )
            if not restart_result.get("ok"):
                return {
                    "ok": False,
                    "stage": "restart",
                    "source_path": str(source),
                    "release_name": release_name,
                    "build_result": build_result,
                    "mkdir_result": mkdir_result,
                    "upload_result": upload_result,
                    "extract_result": extract_result,
                    "restart_result": restart_result,
                }

        health_result = None
        if health_check_command:
            health_result = _run_remote_command(
                ssh_executable,
                remote_user=remote_user,
                remote_host=remote_host,
                ssh_port=ssh_port,
                identity_file=identity_file,
                remote_command=f"cd {_remote_quote(remote_current_link)} && {health_check_command}",
                timeout_ms=timeout_ms,
            )
            if not health_result.get("ok"):
                return {
                    "ok": False,
                    "stage": "health_check",
                    "source_path": str(source),
                    "release_name": release_name,
                    "build_result": build_result,
                    "mkdir_result": mkdir_result,
                    "upload_result": upload_result,
                    "extract_result": extract_result,
                    "restart_result": restart_result,
                    "health_result": health_result,
                }

        return {
            "ok": True,
            "platform": os.name,
            "source_path": str(source),
            "remote_host": remote_host,
            "remote_user": remote_user,
            "remote_path": remote_path,
            "release_name": release_name,
            "archive_name": archive_path.name,
            "archive_size": archive_size,
            "remote_archive_path": remote_archive_path,
            "remote_release_dir": remote_release_dir,
            "remote_current_link": remote_current_link,
            "build_result": build_result,
            "mkdir_result": mkdir_result,
            "upload_result": upload_result,
            "extract_result": extract_result,
            "restart_result": restart_result,
            "health_result": health_result,
        }
    finally:
        shutil.rmtree(stage_root, ignore_errors=True)
