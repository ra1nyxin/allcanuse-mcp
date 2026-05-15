from __future__ import annotations

import json
import os
import subprocess
import sys
from io import BytesIO
from pathlib import Path

from allcanuse_mcp.stdio_compat import HybridStdioReader


def test_hybrid_stdio_reader_reads_json_lines() -> None:
    reader = HybridStdioReader(BytesIO(b'{"jsonrpc":"2.0","id":1}\n'))

    assert reader.read_message() == ("line", '{"jsonrpc":"2.0","id":1}\n')


def test_hybrid_stdio_reader_reads_content_length_frames() -> None:
    body = b'{"jsonrpc":"2.0","id":1}'
    stream = BytesIO(b"Content-Length: " + str(len(body)).encode("ascii") + b"\r\n\r\n" + body)
    reader = HybridStdioReader(stream)

    assert reader.read_message() == ("framed", body.decode("utf-8"))


def test_stdio_compat_script_starts_server_from_package_directory() -> None:
    script = Path(__file__).resolve().parents[1] / "src" / "allcanuse_mcp" / "stdio_compat.py"
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "stdio-compat-test", "version": "0"},
        },
    }

    result = subprocess.run(
        [sys.executable, "stdio_compat.py", "--transport", "stdio"],
        cwd=script.parent,
        input=json.dumps(payload) + "\n",
        text=True,
        encoding="utf-8",
        capture_output=True,
        timeout=10,
        check=False,
    )

    assert result.returncode == 0
    response = json.loads(result.stdout.splitlines()[0])
    assert response["id"] == 1
    assert response["result"]["serverInfo"]["name"] == "allcanuse-mcp"


def test_stdio_compat_auto_uses_codex_profile_when_codex_env_present() -> None:
    script = Path(__file__).resolve().parents[1] / "src" / "allcanuse_mcp" / "stdio_compat.py"
    initialize = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "codex", "version": "0"},
        },
    }
    list_tools = {
        "jsonrpc": "2.0",
        "id": 2,
        "method": "tools/list",
        "params": {},
    }
    initialized = {"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}}
    env = {"CODEX_THREAD_ID": "test-thread"}

    result = subprocess.run(
        [sys.executable, "stdio_compat.py", "--transport", "stdio"],
        cwd=script.parent,
        input=json.dumps(initialize) + "\n" + json.dumps(initialized) + "\n" + json.dumps(list_tools) + "\n",
        text=True,
        encoding="utf-8",
        capture_output=True,
        timeout=10,
        check=False,
        env={**os.environ, **env},
    )

    assert result.returncode == 0
    response = json.loads(result.stdout.splitlines()[1])
    assert response["id"] == 2
    names = {tool["name"] for tool in response["result"]["tools"]}
    assert "get_desktop_context" in names
    assert "run_shell" not in names
    assert "read_file" not in names
