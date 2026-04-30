from __future__ import annotations

import http.server
import os
import socket
import struct
import tempfile
import threading
import time
import unittest
from pathlib import Path
from typing import Callable
from unittest import mock
from urllib.parse import parse_qs, urlparse

from allcanuse_mcp.core.networking import DEFAULT_HTTP_USER_AGENT
from allcanuse_mcp.core.networking import download_file
from allcanuse_mcp.core.networking import extract_links_from_webpage
from allcanuse_mcp.core.networking import extract_webpage_elements
from allcanuse_mcp.core.networking import fetch_response_headers
from allcanuse_mcp.core.networking import fetch_webpage_text
from allcanuse_mcp.core.networking import get_tls_certificate
from allcanuse_mcp.core.networking import http_head
from allcanuse_mcp.core.networking import http_request
from allcanuse_mcp.core.networking import list_established_connections
from allcanuse_mcp.core.networking import raw_tcp_exchange
from allcanuse_mcp.core.networking import scan_ports
from allcanuse_mcp.core.networking import resolve_dns_records
from allcanuse_mcp.core.networking import submit_web_form
from allcanuse_mcp.core.networking import tcp_connect
from allcanuse_mcp.core.networking import trace_http_redirects
from allcanuse_mcp.core.networking import trace_route
from allcanuse_mcp.core.networking import udp_send_receive
from allcanuse_mcp.core.networking import upload_file
from allcanuse_mcp.core.networking import webpage_to_markdown
from allcanuse_mcp.core.networking import extract_tables_from_webpage
from allcanuse_mcp.core.networking import websocket_connect


HTML_SAMPLE = """<!doctype html>
<html>
<head>
  <title>Example Test Page</title>
  <meta name="description" content="test page description">
  <style>.hidden { display:none; }</style>
  <script>console.log("ignore");</script>
</head>
<body>
  <main id="main-content">
    <h1>Welcome Title</h1>
    <p>This is a test page for webpage parsing.</p>
    <a href="/docs/start" class="nav-link">Getting Started</a>
    <a href="https://example.org/files/manual.pdf">Manual PDF</a>
    <article class="post">
      <p>Nested article text block.</p>
    </article>
  </main>
</body>
</html>
"""

HTML_WITH_TABLE = """<!doctype html>
<html>
<body>
  <h1>Price Table</h1>
  <table id="pricing">
    <tr><th>Plan</th><th>Price</th></tr>
    <tr><td>Basic</td><td>$10</td></tr>
    <tr><td>Pro</td><td>$20</td></tr>
  </table>
</body>
</html>
"""


class NetworkingTests(unittest.TestCase):
    def test_tcp_connect_success(self) -> None:
        listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        listener.bind(("127.0.0.1", 0))
        listener.listen(1)
        port = listener.getsockname()[1]

        def accept_once() -> None:
            conn, _ = listener.accept()
            conn.close()
            listener.close()

        thread = threading.Thread(target=accept_once, daemon=True)
        thread.start()
        result = tcp_connect("127.0.0.1", port, timeout_ms=1000)
        thread.join(timeout=1)
        self.assertTrue(result["ok"])
        self.assertEqual(result["port"], port)

    def test_tcp_connect_failure(self) -> None:
        result = tcp_connect("127.0.0.1", 1, timeout_ms=200)
        self.assertFalse(result["ok"])

    def test_download_file_success(self) -> None:
        base = Path(tempfile.gettempdir(), "allcanuse-download-test")
        base.mkdir(parents=True, exist_ok=True)
        source = base / "hello.txt"
        source.write_text("hello download", encoding="utf-8")

        previous = os.getcwd()
        os.chdir(base)
        handler = http.server.SimpleHTTPRequestHandler
        server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
        port = server.server_address[1]

        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            target = base / "copied.txt"
            result = download_file(
                url=f"http://127.0.0.1:{port}/hello.txt",
                destination=str(target),
                timeout_ms=5000,
                overwrite=True,
            )
            self.assertTrue(result["ok"])
            self.assertEqual(target.read_text(encoding="utf-8"), "hello download")
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=1)
            os.chdir(previous)
            for item in base.iterdir():
                item.unlink()
            base.rmdir()

    def test_http_head_returns_headers_without_body(self) -> None:
        with _local_http_site(
            {
                "headers": (
                    200,
                    {
                        "Content-Type": "text/plain; charset=utf-8",
                        "ETag": '"demo-etag"',
                    },
                    "hello headers",
                )
            }
        ) as base_url:
            result = http_head(url=f"{base_url}/headers")
        self.assertTrue(result["ok"])
        self.assertEqual(result["status"], 200)
        self.assertEqual(result["headers"].get("ETag") or result["headers"].get("Etag"), '"demo-etag"')
        self.assertEqual(result["content_type"], "text/plain; charset=utf-8")

    def test_http_request_sends_default_user_agent(self) -> None:
        def handler(request: http.server.BaseHTTPRequestHandler) -> tuple[int, dict[str, str], str]:
            return (
                200,
                {"Content-Type": "text/plain; charset=utf-8"},
                request.headers.get("User-Agent", ""),
            )

        with _local_http_site({"ua": handler}) as base_url:
            result = http_request(url=f"{base_url}/ua")
        self.assertTrue(result["ok"])
        self.assertEqual(result["body"], DEFAULT_HTTP_USER_AGENT)

    def test_fetch_response_headers_supports_get_probe(self) -> None:
        with _local_http_site(
            {
                "headers": (
                    200,
                    {
                        "Content-Type": "application/json; charset=utf-8",
                        "X-Test": "headers-only",
                    },
                    '{"ok": true}',
                )
            }
        ) as base_url:
            result = fetch_response_headers(url=f"{base_url}/headers", method="GET")
        self.assertTrue(result["ok"])
        self.assertEqual(result["headers"]["X-Test"], "headers-only")
        self.assertEqual(result["content_type"], "application/json; charset=utf-8")

    def test_submit_web_form_allows_custom_user_agent_override(self) -> None:
        def handler(request: http.server.BaseHTTPRequestHandler) -> tuple[int, dict[str, str], str]:
            return (
                200,
                {"Content-Type": "text/plain; charset=utf-8"},
                request.headers.get("User-Agent", ""),
            )

        with _local_http_site({"submit": handler}) as base_url:
            result = submit_web_form(
                url=f"{base_url}/submit",
                method="GET",
                form_fields={"q": "ua"},
                headers={"user-agent": "MyCustomAgent/1.0"},
                timeout_ms=5000,
            )
        self.assertTrue(result["ok"])
        self.assertEqual(result["body"], "MyCustomAgent/1.0")

    def test_submit_web_form_posts_urlencoded_fields(self) -> None:
        def handler(request: http.server.BaseHTTPRequestHandler) -> tuple[int, dict[str, str], str]:
            length = int(request.headers.get("Content-Length", "0"))
            raw = request.rfile.read(length).decode("utf-8")
            parsed = parse_qs(raw)
            return (
                200,
                {"Content-Type": "application/json; charset=utf-8"},
                f'{{"query":"{parsed["q"][0]}","page":"{parsed["page"][0]}"}}',
            )

        with _local_http_site({"submit": handler}) as base_url:
            result = submit_web_form(
                url=f"{base_url}/submit",
                method="POST",
                form_fields={"q": "mcp tools", "page": "2"},
                timeout_ms=5000,
            )
        self.assertTrue(result["ok"])
        self.assertIn('"query":"mcp tools"', result["body"])
        self.assertIn('"page":"2"', result["body"])

    def test_upload_file_sends_multipart_form_data(self) -> None:
        file_path = Path(os.getcwd(), "tests", "_tmp_upload_sample.txt")
        try:
            file_path.write_text("hello upload", encoding="utf-8")

            def handler(request: http.server.BaseHTTPRequestHandler) -> tuple[int, dict[str, str], str]:
                length = int(request.headers.get("Content-Length", "0"))
                raw = request.rfile.read(length)
                content_type = request.headers.get("Content-Type", "")
                boundary = content_type.split("boundary=", 1)[1].encode("ascii")
                parts = raw.split(b"--" + boundary)
                payload_text = ""
                meta_text = ""
                for part in parts:
                    if f'filename="{file_path.name}"'.encode("utf-8") in part:
                        payload_text = part.split(b"\r\n\r\n", 1)[1].rsplit(b"\r\n", 1)[0].decode("utf-8")
                    if b'name="project"' in part:
                        meta_text = part.split(b"\r\n\r\n", 1)[1].rsplit(b"\r\n", 1)[0].decode("utf-8")
                return (
                    200,
                    {"Content-Type": "application/json; charset=utf-8"},
                    f'{{"payload":"{payload_text}","project":"{meta_text}"}}',
                )

            with _local_http_site({"upload": handler}) as base_url:
                result = upload_file(
                    url=f"{base_url}/upload",
                    file_path=str(file_path),
                    form_fields={"project": "allcanuse"},
                    timeout_ms=5000,
                )
        finally:
            file_path.unlink(missing_ok=True)
        self.assertTrue(result["ok"])
        self.assertEqual(result["upload_mode"], "multipart")
        self.assertIn('"payload":"hello upload"', result["response_body"])
        self.assertIn('"project":"allcanuse"', result["response_body"])

    def test_upload_file_supports_raw_put_mode(self) -> None:
        file_path = Path(os.getcwd(), "tests", "_tmp_upload_binary.bin")
        try:
            file_path.write_bytes(b"\x00\x01raw-upload")

            def handler(request: http.server.BaseHTTPRequestHandler) -> tuple[int, dict[str, str], str]:
                length = int(request.headers.get("Content-Length", "0"))
                raw = request.rfile.read(length)
                return (
                    200,
                    {"Content-Type": "text/plain; charset=utf-8"},
                    raw.hex(),
                )

            with _local_http_site({"raw": handler}) as base_url:
                result = upload_file(
                    url=f"{base_url}/raw",
                    file_path=str(file_path),
                    method="PUT",
                    upload_mode="raw",
                    content_type="application/octet-stream",
                    timeout_ms=5000,
                )
        finally:
            file_path.unlink(missing_ok=True)
        self.assertTrue(result["ok"])
        self.assertEqual(result["method"], "PUT")
        self.assertEqual(result["upload_mode"], "raw")
        self.assertIn("00017261772d75706c6f6164", result["response_body"])

    def test_fetch_webpage_text_extracts_visible_text(self) -> None:
        with _local_http_site({"index.html": HTML_SAMPLE}) as base_url:
            result = fetch_webpage_text(url=f"{base_url}/index.html", max_text_chars=5000)
        self.assertTrue(result["ok"])
        self.assertEqual(result["title"], "Example Test Page")
        self.assertIn("Welcome Title", result["text"])
        self.assertIn("Nested article text block.", result["text"])
        self.assertNotIn("console.log", result["text"])

    def test_webpage_to_markdown_converts_basic_structure(self) -> None:
        with _local_http_site({"index.html": HTML_SAMPLE}) as base_url:
            result = webpage_to_markdown(url=f"{base_url}/index.html", max_markdown_chars=5000)
        self.assertTrue(result["ok"])
        self.assertIn("# Welcome Title", result["markdown"])
        self.assertIn("[Getting Started](", result["markdown"])

    def test_extract_links_from_webpage_supports_filter(self) -> None:
        with _local_http_site({"index.html": HTML_SAMPLE}) as base_url:
            result = extract_links_from_webpage(
                url=f"{base_url}/index.html",
                href_filter=".pdf",
                max_links=20,
            )
        self.assertTrue(result["ok"])
        self.assertEqual(result["count"], 1)
        self.assertEqual(result["links"][0]["text"], "Manual PDF")
        self.assertIn(".pdf", result["links"][0]["absolute_url"])

    def test_extract_webpage_elements_by_tag_and_attr(self) -> None:
        with _local_http_site({"index.html": HTML_SAMPLE}) as base_url:
            result = extract_webpage_elements(
                url=f"{base_url}/index.html",
                tag="main",
                attr_filters={"id": "main-content"},
                max_elements=10,
            )
        self.assertTrue(result["ok"])
        self.assertEqual(result["count"], 1)
        self.assertIn("Welcome Title", result["elements"][0]["text"])

    def test_extract_tables_from_webpage_returns_rows(self) -> None:
        with _local_http_site({"table.html": HTML_WITH_TABLE}) as base_url:
            result = extract_tables_from_webpage(url=f"{base_url}/table.html")
        self.assertTrue(result["ok"])
        self.assertEqual(result["count"], 1)
        self.assertEqual(result["tables"][0]["headers"], ["Plan", "Price"])
        self.assertEqual(result["tables"][0]["rows"][1], ["Pro", "$20"])

    def test_trace_http_redirects_returns_chain(self) -> None:
        routes = {
            "/start": (302, {"Location": "/middle"}, ""),
            "/middle": (301, {"Location": "/end"}, ""),
            "/end": (200, {"Content-Type": "text/plain; charset=utf-8"}, "done"),
        }
        with _local_http_site(routes) as base_url:
            result = trace_http_redirects(url=f"{base_url}/start", max_hops=10)
        self.assertTrue(result["ok"])
        self.assertEqual(result["redirect_count"], 2)
        self.assertTrue(result["final_url"].endswith("/end"))
        self.assertEqual(result["chain"][0]["status"], 302)
        self.assertEqual(result["chain"][1]["status"], 301)
        self.assertEqual(result["chain"][2]["status"], 200)

    def test_trace_route_uses_subprocess(self) -> None:
        completed = mock.Mock(returncode=0, stdout="hop1\nhop2\n", stderr="")
        with mock.patch("allcanuse_mcp.core.networking.subprocess.run", return_value=completed) as mocked_run:
            result = trace_route("example.com", max_hops=5, timeout_ms=2000)
        self.assertTrue(result["ok"])
        self.assertIn("example.com", result["command"])
        mocked_run.assert_called_once()

    def test_resolve_dns_records_against_local_dns_server(self) -> None:
        with _fake_dns_server() as server:
            result = resolve_dns_records(
                "example.test",
                record_types=["A", "TXT"],
                dns_server=f"{server.host}:{server.port}",
                timeout_ms=3000,
            )
        self.assertEqual(result["results"]["A"]["answers"][0]["data"], "127.0.0.42")
        self.assertEqual(result["results"]["TXT"]["answers"][0]["data"], ["hello-dns"])

    def test_get_tls_certificate_uses_decoded_cert(self) -> None:
        fake_der = b"\x01\x02\x03\x04"

        class FakeTLSSocket:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def getpeercert(self, binary_form: bool = False):
                if binary_form:
                    return fake_der
                return {}

            def version(self):
                return "TLSv1.3"

            def cipher(self):
                return ("TLS_AES_256_GCM_SHA384", "TLSv1.3", 256)

            def selected_alpn_protocol(self):
                return "h2"

        class FakeContext:
            check_hostname = False
            verify_mode = None

            def wrap_socket(self, sock, server_hostname=None):
                return FakeTLSSocket()

        class FakeTCPContext:
            def __enter__(self):
                return object()

            def __exit__(self, exc_type, exc, tb):
                return False

        with mock.patch("allcanuse_mcp.core.networking.socket.create_connection", return_value=FakeTCPContext()):
            with mock.patch("allcanuse_mcp.core.networking.ssl.create_default_context", return_value=FakeContext()):
                with mock.patch("allcanuse_mcp.core.networking.ssl.DER_cert_to_PEM_cert", return_value="PEM"):
                    with mock.patch(
                        "allcanuse_mcp.core.networking.ssl._ssl._test_decode_cert",
                        return_value={
                            "subject": ((("commonName", "example.test"),),),
                            "issuer": ((("commonName", "Example CA"),),),
                            "subjectAltName": (("DNS", "example.test"), ("DNS", "www.example.test")),
                            "serialNumber": "1234",
                            "notBefore": "Jan  1 00:00:00 2026 GMT",
                            "notAfter": "Jan  1 00:00:00 2027 GMT",
                        },
                    ):
                        result = get_tls_certificate("example.test", verify=False)
        self.assertEqual(result["subject"]["commonName"], "example.test")
        self.assertEqual(result["issuer"]["commonName"], "Example CA")
        self.assertEqual(result["tls_version"], "TLSv1.3")
        self.assertEqual(len(result["sha256_fingerprint"]), 64)

    def test_raw_tcp_exchange_round_trip(self) -> None:
        with _tcp_server(lambda payload: payload.upper()) as server:
            result = raw_tcp_exchange(server.host, server.port, data="ping", timeout_ms=2000)
        self.assertTrue(result["ok"])
        self.assertEqual(result["response"], "PING")

    def test_udp_send_receive_round_trip(self) -> None:
        with _udp_server(lambda payload: payload[::-1]) as server:
            result = udp_send_receive(server.host, server.port, data="stressed", timeout_ms=2000)
        self.assertTrue(result["ok"])
        self.assertEqual(result["response"], "desserts")

    def test_websocket_connect_sends_and_receives_text_message(self) -> None:
        with _websocket_server(lambda message: message.upper()) as server:
            result = websocket_connect(
                url=server.url,
                messages=["hello websocket"],
                timeout_ms=2000,
                receive_limit=2,
            )
        self.assertTrue(result["ok"])
        self.assertEqual(result["handshake"]["status_code"], 101)
        self.assertEqual(result["received_messages"][0]["text"], "HELLO WEBSOCKET")

    def test_scan_ports_finds_open_port(self) -> None:
        listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        listener.bind(("127.0.0.1", 0))
        listener.listen(1)
        port = listener.getsockname()[1]
        try:
            result = scan_ports("127.0.0.1", start_port=port, end_port=port + 1, timeout_ms=200, open_only=False)
            open_ports = [item["port"] for item in result["results"] if item["open"]]
            self.assertIn(port, open_ports)
        finally:
            listener.close()

    def test_list_established_connections_contains_open_socket(self) -> None:
        listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        listener.bind(("127.0.0.1", 0))
        listener.listen(1)
        port = listener.getsockname()[1]
        accepted: dict[str, socket.socket] = {}

        def accept_once() -> None:
            conn, _ = listener.accept()
            accepted["conn"] = conn
            time.sleep(0.5)
            conn.close()
            listener.close()

        server_thread = threading.Thread(target=accept_once, daemon=True)
        server_thread.start()
        client = socket.create_connection(("127.0.0.1", port), timeout=1)
        try:
            time.sleep(0.1)
            result = list_established_connections(limit=500)
            self.assertTrue(
                any(
                    item["local_port"] == client.getsockname()[1] or item["remote_port"] == client.getsockname()[1]
                    for item in result["connections"]
                )
            )
        finally:
            client.close()
            server_thread.join(timeout=1)


RouteValue = str | tuple[int, dict[str, str], str] | Callable[[http.server.BaseHTTPRequestHandler], tuple[int, dict[str, str], str]]


class _SiteContext:
    def __init__(self, routes: dict[str, RouteValue]) -> None:
        self.routes = routes
        self.server: http.server.ThreadingHTTPServer | None = None
        self.thread: threading.Thread | None = None
        self.base_url = ""

    def __enter__(self) -> str:
        routes = {f"/{key.lstrip('/')}": value for key, value in self.routes.items()}

        class InMemoryHandler(http.server.BaseHTTPRequestHandler):
            def _resolve_route(self) -> tuple[int, dict[str, str], str]:
                path = urlparse(self.path).path
                route = routes.get(path)
                if route is None:
                    return 404, {"Content-Type": "text/plain; charset=utf-8"}, "not found"

                if callable(route):
                    return route(self)
                if isinstance(route, tuple):
                    status, headers, body = route
                else:
                    status = 200
                    headers = {"Content-Type": "text/html; charset=utf-8"}
                    body = route
                return status, headers, body

            def _send_route(self, *, include_body: bool) -> None:
                status, headers, body = self._resolve_route()
                payload = body.encode("utf-8")
                self.send_response(status)
                for key, value in headers.items():
                    self.send_header(key, value)
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                if include_body:
                    self.wfile.write(payload)

            def do_GET(self) -> None:  # noqa: N802
                self._send_route(include_body=True)

            def do_HEAD(self) -> None:  # noqa: N802
                self._send_route(include_body=False)

            def do_POST(self) -> None:  # noqa: N802
                self._send_route(include_body=True)

            def do_PUT(self) -> None:  # noqa: N802
                self._send_route(include_body=True)

            def log_message(self, format: str, *args) -> None:  # noqa: A003
                return

        self.server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), InMemoryHandler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base_url = f"http://127.0.0.1:{self.server.server_address[1]}"
        return self.base_url

    def __exit__(self, exc_type, exc, tb) -> None:
        assert self.server is not None
        assert self.thread is not None
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=1)


class _TCPServerContext:
    def __init__(self, handler) -> None:
        self.handler = handler
        self.listener: socket.socket | None = None
        self.thread: threading.Thread | None = None
        self.host = "127.0.0.1"
        self.port = 0

    def __enter__(self) -> _TCPServerContext:
        self.listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.listener.bind((self.host, 0))
        self.listener.listen(1)
        self.port = self.listener.getsockname()[1]

        def serve() -> None:
            assert self.listener is not None
            conn, _ = self.listener.accept()
            data = conn.recv(4096)
            conn.sendall(self.handler(data))
            conn.close()
            self.listener.close()

        self.thread = threading.Thread(target=serve, daemon=True)
        self.thread.start()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        assert self.thread is not None
        self.thread.join(timeout=1)


class _UDPServerContext:
    def __init__(self, handler) -> None:
        self.handler = handler
        self.sock: socket.socket | None = None
        self.thread: threading.Thread | None = None
        self.host = "127.0.0.1"
        self.port = 0

    def __enter__(self) -> _UDPServerContext:
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind((self.host, 0))
        self.port = self.sock.getsockname()[1]

        def serve() -> None:
            assert self.sock is not None
            data, addr = self.sock.recvfrom(4096)
            self.sock.sendto(self.handler(data), addr)
            self.sock.close()

        self.thread = threading.Thread(target=serve, daemon=True)
        self.thread.start()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        assert self.thread is not None
        self.thread.join(timeout=1)


class _FakeDNSServerContext:
    def __init__(self) -> None:
        self.sock: socket.socket | None = None
        self.thread: threading.Thread | None = None
        self.host = "127.0.0.1"
        self.port = 0

    def __enter__(self) -> _FakeDNSServerContext:
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind((self.host, 0))
        self.host = self.sock.getsockname()[0]
        self.port = self.sock.getsockname()[1]

        def serve() -> None:
            assert self.sock is not None
            for _ in range(2):
                packet, addr = self.sock.recvfrom(1024)
                response = _build_fake_dns_response(packet)
                self.sock.sendto(response, addr)
            self.sock.close()

        self.thread = threading.Thread(target=serve, daemon=True)
        self.thread.start()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        assert self.thread is not None
        self.thread.join(timeout=1)


class _WebSocketServerContext:
    def __init__(self, handler: Callable[[str], str]) -> None:
        self.handler = handler
        self.listener: socket.socket | None = None
        self.thread: threading.Thread | None = None
        self.host = "127.0.0.1"
        self.port = 0
        self.url = ""

    def __enter__(self) -> _WebSocketServerContext:
        self.listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.listener.bind((self.host, 0))
        self.listener.listen(1)
        self.port = self.listener.getsockname()[1]
        self.url = f"ws://{self.host}:{self.port}/echo"

        def serve() -> None:
            assert self.listener is not None
            conn, _ = self.listener.accept()
            try:
                headers = _recv_ws_until(conn, b"\r\n\r\n").decode("iso-8859-1")
                key = ""
                for line in headers.split("\r\n"):
                    if line.lower().startswith("sec-websocket-key:"):
                        key = line.split(":", 1)[1].strip()
                        break
                accept = _ws_accept_value(key)
                response = (
                    "HTTP/1.1 101 Switching Protocols\r\n"
                    "Upgrade: websocket\r\n"
                    "Connection: Upgrade\r\n"
                    f"Sec-WebSocket-Accept: {accept}\r\n\r\n"
                ).encode("ascii")
                conn.sendall(response)
                opcode, payload = _read_ws_frame(conn)
                if opcode == 0x1:
                    message = payload.decode("utf-8")
                    conn.sendall(_build_ws_frame(0x1, self.handler(message).encode("utf-8")))
                conn.sendall(_build_ws_frame(0x8, struct.pack("!H", 1000)))
            finally:
                conn.close()
                self.listener.close()

        self.thread = threading.Thread(target=serve, daemon=True)
        self.thread.start()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        assert self.thread is not None
        self.thread.join(timeout=1)


def _local_http_site(routes: dict[str, RouteValue]) -> _SiteContext:
    return _SiteContext(routes)


def _tcp_server(handler) -> _TCPServerContext:
    return _TCPServerContext(handler)


def _udp_server(handler) -> _UDPServerContext:
    return _UDPServerContext(handler)


def _fake_dns_server() -> _FakeDNSServerContext:
    return _FakeDNSServerContext()


def _websocket_server(handler: Callable[[str], str]) -> _WebSocketServerContext:
    return _WebSocketServerContext(handler)


def _recv_ws_until(sock: socket.socket, marker: bytes) -> bytes:
    buffer = bytearray()
    while marker not in buffer:
        chunk = sock.recv(4096)
        if not chunk:
            raise ConnectionError("socket closed before marker")
        buffer.extend(chunk)
    return bytes(buffer[: buffer.index(marker) + len(marker)])


def _recv_ws_exact(sock: socket.socket, size: int) -> bytes:
    chunks = bytearray()
    while len(chunks) < size:
        chunk = sock.recv(size - len(chunks))
        if not chunk:
            raise ConnectionError("socket closed before frame completed")
        chunks.extend(chunk)
    return bytes(chunks)


def _read_ws_frame(sock: socket.socket) -> tuple[int, bytes]:
    first_two = _recv_ws_exact(sock, 2)
    first_byte, second_byte = first_two[0], first_two[1]
    opcode = first_byte & 0x0F
    payload_length = second_byte & 0x7F
    masked = bool(second_byte & 0x80)
    if payload_length == 126:
        payload_length = struct.unpack("!H", _recv_ws_exact(sock, 2))[0]
    elif payload_length == 127:
        payload_length = struct.unpack("!Q", _recv_ws_exact(sock, 8))[0]
    masking_key = _recv_ws_exact(sock, 4) if masked else b""
    payload = _recv_ws_exact(sock, payload_length)
    if masked:
        payload = bytes(item ^ masking_key[index % 4] for index, item in enumerate(payload))
    return opcode, payload


def _build_ws_frame(opcode: int, payload: bytes) -> bytes:
    header = bytearray([0x80 | (opcode & 0x0F)])
    payload_length = len(payload)
    if payload_length < 126:
        header.append(payload_length)
    elif payload_length <= 0xFFFF:
        header.append(126)
        header.extend(struct.pack("!H", payload_length))
    else:
        header.append(127)
        header.extend(struct.pack("!Q", payload_length))
    return bytes(header) + payload


def _ws_accept_value(key: str) -> str:
    seed = (key + "258EAFA5-E914-47DA-95CA-C5AB0DC85B11").encode("ascii")
    import base64
    import hashlib

    return base64.b64encode(hashlib.sha1(seed).digest()).decode("ascii")


def _build_fake_dns_response(packet: bytes) -> bytes:
    transaction_id = packet[:2]
    flags = b"\x81\x80"
    qdcount = packet[4:6]
    ancount = b"\x00\x01"
    nscount = b"\x00\x00"
    arcount = b"\x00\x00"
    question = packet[12:]
    qtype = struct.unpack("!H", question[-4:-2])[0]
    answer_name = b"\xc0\x0c"
    answer_class = b"\x00\x01"
    ttl = struct.pack("!I", 60)
    if qtype == 1:
        rdata = socket.inet_aton("127.0.0.42")
    elif qtype == 16:
        txt = b"hello-dns"
        rdata = bytes([len(txt)]) + txt
    else:
        rdata = b"\x00"
    answer = answer_name + struct.pack("!H", qtype) + answer_class + ttl + struct.pack("!H", len(rdata)) + rdata
    return transaction_id + flags + qdcount + ancount + nscount + arcount + question + answer


if __name__ == "__main__":
    unittest.main()
