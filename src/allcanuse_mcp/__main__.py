from __future__ import annotations

import argparse

import anyio

from allcanuse_mcp.server import create_server
from allcanuse_mcp.stdio_compat import run_stdio_compatible


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the allcanuse Windows/Linux MCP server.")
    parser.add_argument(
        "--transport",
        choices=["stdio", "sse", "streamable-http"],
        default="stdio",
        help="MCP transport to use. Default: stdio",
    )
    parser.add_argument("--host", default="127.0.0.1", help="HTTP host for non-stdio transports.")
    parser.add_argument("--port", default=8000, type=int, help="HTTP port for non-stdio transports.")
    parser.add_argument(
        "--profile",
        choices=["auto", "full", "codex"],
        default="auto",
        help="Tool exposure profile. auto uses the compact Codex profile when Codex environment variables are present.",
    )
    args = parser.parse_args()

    server = create_server(host=args.host, port=args.port, profile=args.profile)
    if args.transport == "stdio":
        anyio.run(run_stdio_compatible, server)
    else:
        server.run(transport=args.transport)


if __name__ == "__main__":
    main()
