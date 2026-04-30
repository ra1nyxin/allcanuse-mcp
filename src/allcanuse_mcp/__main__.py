from __future__ import annotations

import argparse

from allcanuse_mcp.server import create_server


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
    args = parser.parse_args()

    server = create_server(host=args.host, port=args.port)
    server.run(transport=args.transport)


if __name__ == "__main__":
    main()
