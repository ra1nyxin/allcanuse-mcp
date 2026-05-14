from __future__ import annotations

from io import BytesIO

from allcanuse_mcp.stdio_compat import HybridStdioReader


def test_hybrid_stdio_reader_reads_json_lines() -> None:
    reader = HybridStdioReader(BytesIO(b'{"jsonrpc":"2.0","id":1}\n'))

    assert reader.read_message() == ("line", '{"jsonrpc":"2.0","id":1}\n')


def test_hybrid_stdio_reader_reads_content_length_frames() -> None:
    body = b'{"jsonrpc":"2.0","id":1}'
    stream = BytesIO(b"Content-Length: " + str(len(body)).encode("ascii") + b"\r\n\r\n" + body)
    reader = HybridStdioReader(stream)

    assert reader.read_message() == ("framed", body.decode("utf-8"))
