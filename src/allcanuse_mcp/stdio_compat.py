from __future__ import annotations

import argparse
import sys
from contextlib import asynccontextmanager
from io import TextIOWrapper
from pathlib import Path
from typing import BinaryIO, Literal

import anyio
import anyio.lowlevel
from anyio.streams.memory import MemoryObjectReceiveStream, MemoryObjectSendStream

import mcp.types as types
from mcp.server.fastmcp import FastMCP
from mcp.shared.message import SessionMessage


TransportMode = Literal["line", "framed"]


class HybridStdioReader:
    """Read both newline-delimited JSON and Content-Length framed JSON-RPC."""

    def __init__(self, stream: BinaryIO) -> None:
        self.stream = stream

    def read_message(self) -> tuple[TransportMode, str] | None:
        while True:
            first_line = self.stream.readline()
            if first_line == b"":
                return None
            if first_line.strip():
                break

        if self._looks_like_header(first_line):
            headers = [first_line]
            while True:
                line = self.stream.readline()
                if line == b"":
                    return None
                headers.append(line)
                if line in {b"\r\n", b"\n"}:
                    break

            content_length = self._content_length(headers)
            if content_length is None:
                raise ValueError("stdio frame is missing Content-Length header")

            body = self.stream.read(content_length)
            if len(body) != content_length:
                raise EOFError(
                    f"stdio frame ended early: expected {content_length} bytes, got {len(body)}"
                )
            return "framed", body.decode("utf-8", errors="replace")

        return "line", first_line.decode("utf-8", errors="replace")

    @staticmethod
    def _looks_like_header(line: bytes) -> bool:
        stripped = line.strip()
        if stripped.startswith((b"{", b"[")):
            return False
        return b":" in stripped

    @staticmethod
    def _content_length(headers: list[bytes]) -> int | None:
        for raw_line in headers:
            line = raw_line.decode("ascii", errors="replace")
            name, sep, value = line.partition(":")
            if sep and name.strip().lower() == "content-length":
                return int(value.strip())
        return None


@asynccontextmanager
async def stdio_server_compatible():
    stdin = sys.stdin.buffer
    stdout = anyio.wrap_file(TextIOWrapper(sys.stdout.buffer, encoding="utf-8"))
    reader = HybridStdioReader(stdin)
    mode: dict[str, TransportMode] = {"current": "line"}

    read_stream: MemoryObjectReceiveStream[SessionMessage | Exception]
    read_stream_writer: MemoryObjectSendStream[SessionMessage | Exception]

    write_stream: MemoryObjectSendStream[SessionMessage]
    write_stream_reader: MemoryObjectReceiveStream[SessionMessage]

    read_stream_writer, read_stream = anyio.create_memory_object_stream(0)
    write_stream, write_stream_reader = anyio.create_memory_object_stream(0)

    async def stdin_reader() -> None:
        try:
            async with read_stream_writer:
                while True:
                    try:
                        item = await anyio.to_thread.run_sync(reader.read_message)
                    except Exception as exc:
                        await read_stream_writer.send(exc)
                        continue
                    if item is None:
                        break

                    mode["current"], raw_json = item
                    try:
                        message = types.JSONRPCMessage.model_validate_json(raw_json)
                    except Exception as exc:
                        await read_stream_writer.send(exc)
                        continue

                    await read_stream_writer.send(SessionMessage(message))
        except anyio.ClosedResourceError:  # pragma: no cover
            await anyio.lowlevel.checkpoint()

    async def stdout_writer() -> None:
        try:
            async with write_stream_reader:
                async for session_message in write_stream_reader:
                    json_text = session_message.message.model_dump_json(
                        by_alias=True,
                        exclude_none=True,
                    )
                    if mode["current"] == "framed":
                        byte_length = len(json_text.encode("utf-8"))
                        await stdout.write(f"Content-Length: {byte_length}\r\n\r\n{json_text}")
                    else:
                        await stdout.write(json_text + "\n")
                    await stdout.flush()
        except anyio.ClosedResourceError:  # pragma: no cover
            await anyio.lowlevel.checkpoint()

    async with anyio.create_task_group() as tg:
        tg.start_soon(stdin_reader)
        tg.start_soon(stdout_writer)
        yield read_stream, write_stream


async def run_stdio_compatible(server: FastMCP) -> None:
    async with stdio_server_compatible() as (read_stream, write_stream):
        await server._mcp_server.run(
            read_stream,
            write_stream,
            server._mcp_server.create_initialization_options(),
        )


def _ensure_src_on_path() -> None:
    src_dir = Path(__file__).resolve().parents[1]
    if str(src_dir) not in sys.path:
        sys.path.insert(0, str(src_dir))


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run allcanuse-mcp with a stdio transport compatible with line JSON and Content-Length frames."
    )
    parser.add_argument(
        "--transport",
        choices=["stdio", "sse", "streamable-http"],
        default="stdio",
        help="MCP transport to use. Default: stdio",
    )
    parser.add_argument("--host", default="127.0.0.1", help="HTTP host for non-stdio transports.")
    parser.add_argument("--port", default=8000, type=int, help="HTTP port for non-stdio transports.")
    args = parser.parse_args()

    _ensure_src_on_path()
    from allcanuse_mcp.server import create_server

    server = create_server(host=args.host, port=args.port)
    if args.transport == "stdio":
        anyio.run(run_stdio_compatible, server)
    else:
        server.run(transport=args.transport)


if __name__ == "__main__":
    main()
