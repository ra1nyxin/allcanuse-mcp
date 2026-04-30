from __future__ import annotations

import base64
import hashlib
import ipaddress
import json
import mimetypes
import os
import platform
import random
import re
import socket
import ssl
import struct
import subprocess
import tempfile
from html.parser import HTMLParser
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qsl, urlencode, urljoin, urlparse, urlunparse
from urllib.request import HTTPRedirectHandler, Request, build_opener, urlopen


def _build_default_user_agent() -> str:
    system = platform.system().lower()
    machine = (platform.machine() or "x86_64").lower()
    if system == "windows":
        platform_token = "Windows NT 10.0; Win64; x64"
    elif system == "linux":
        platform_token = f"X11; Linux {machine}"
    elif system == "darwin":
        platform_token = "Macintosh; Intel Mac OS X 10_15_7"
    else:
        platform_token = f"{platform.system()} {machine}".strip()
    return (
        "Mozilla/5.0 "
        f"({platform_token}) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/136.0.0.0 Safari/537.36 "
        "allcanuse-mcp/0.1.0"
    )


DEFAULT_HTTP_USER_AGENT = _build_default_user_agent()
_DEFAULT_HTTP_HEADERS = {
    "User-Agent": DEFAULT_HTTP_USER_AGENT,
}


_DNS_TYPE_TO_CODE = {
    "A": 1,
    "NS": 2,
    "CNAME": 5,
    "PTR": 12,
    "MX": 15,
    "TXT": 16,
    "AAAA": 28,
    "SRV": 33,
}
_DNS_CODE_TO_TYPE = {value: key for key, value in _DNS_TYPE_TO_CODE.items()}
_DNS_RCODE_MESSAGES = {
    0: "NOERROR",
    1: "FORMERR",
    2: "SERVFAIL",
    3: "NXDOMAIN",
    4: "NOTIMP",
    5: "REFUSED",
}


class _NoRedirectHandler(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # type: ignore[override]
        return None


def _find_header_name(headers: dict[str, str], name: str) -> str | None:
    lowered = name.casefold()
    for existing_name in headers:
        if existing_name.casefold() == lowered:
            return existing_name
    return None


def _set_default_header(headers: dict[str, str], name: str, value: str) -> None:
    if _find_header_name(headers, name) is None:
        headers[name] = value


def _merge_http_headers(headers: dict[str, str] | None = None) -> dict[str, str]:
    merged = dict(_DEFAULT_HTTP_HEADERS)
    for header_name, header_value in (headers or {}).items():
        existing_name = _find_header_name(merged, str(header_name))
        if existing_name is not None:
            del merged[existing_name]
        merged[str(header_name)] = "" if header_value is None else str(header_value)
    return merged


def _fetch_url(
    *,
    url: str,
    method: str = "GET",
    headers: dict[str, str] | None = None,
    body: str | None = None,
    timeout_ms: int = 15_000,
) -> dict[str, Any]:
    data = body.encode("utf-8") if body is not None else None
    request = Request(url=url, method=method.upper(), data=data, headers=_merge_http_headers(headers))
    with urlopen(request, timeout=max(timeout_ms, 1) / 1000) as response:
        raw = response.read()
        content_type = response.headers.get("Content-Type", "")
        charset = response.headers.get_content_charset() or "utf-8"
        text = raw.decode(charset, errors="replace")
        return {
            "status": response.status,
            "reason": response.reason,
            "final_url": response.geturl(),
            "headers": dict(response.headers.items()),
            "content_type": content_type,
            "charset": charset,
            "body_bytes": len(raw),
            "raw": raw,
            "text": text,
        }


def _fetch_response_headers(
    *,
    url: str,
    method: str = "HEAD",
    headers: dict[str, str] | None = None,
    body: bytes | None = None,
    timeout_ms: int = 15_000,
) -> dict[str, Any]:
    request = Request(url=url, method=method.upper(), data=body, headers=_merge_http_headers(headers))
    with urlopen(request, timeout=max(timeout_ms, 1) / 1000) as response:
        return {
            "status": response.status,
            "reason": response.reason,
            "final_url": response.geturl(),
            "headers": dict(response.headers.items()),
            "content_type": response.headers.get("Content-Type", ""),
            "content_length": response.headers.get("Content-Length", ""),
        }


def _truncate_text(text: str, max_chars: int) -> tuple[str, bool]:
    if max_chars > 0 and len(text) > max_chars:
        return text[:max_chars], True
    return text, False


def _encode_payload(data: str, *, input_encoding: str) -> bytes:
    encoding = input_encoding.lower()
    if encoding == "utf-8":
        return data.encode("utf-8")
    if encoding == "hex":
        return bytes.fromhex(data)
    if encoding == "base64":
        return base64.b64decode(data, validate=True)
    raise ValueError(f"Unsupported input_encoding: {input_encoding}")


def _decode_payload(data: bytes, *, output_encoding: str, max_chars: int = 12_000) -> dict[str, Any]:
    encoding = output_encoding.lower()
    if encoding == "utf-8":
        text = data.decode("utf-8", errors="replace")
    elif encoding == "hex":
        text = data.hex()
    elif encoding == "base64":
        text = base64.b64encode(data).decode("ascii")
    else:
        raise ValueError(f"Unsupported output_encoding: {output_encoding}")
    text, truncated = _truncate_text(text, max_chars)
    return {"text": text, "text_truncated": truncated}


def _append_query_params(url: str, params: dict[str, Any]) -> str:
    parsed = urlparse(url)
    existing = parse_qsl(parsed.query, keep_blank_values=True)
    for key, value in params.items():
        existing.append((key, "" if value is None else str(value)))
    new_query = urlencode(existing, doseq=True)
    return urlunparse(parsed._replace(query=new_query))


def _encode_form_payload(
    fields: dict[str, Any],
    *,
    encoding: str,
) -> tuple[bytes, str]:
    normalized = {str(key): "" if value is None else str(value) for key, value in fields.items()}
    lowered = encoding.lower()
    if lowered in {"application/x-www-form-urlencoded", "urlencoded", "form"}:
        return urlencode(normalized, doseq=True).encode("utf-8"), "application/x-www-form-urlencoded"
    if lowered in {"multipart/form-data", "multipart"}:
        boundary = f"----allcanuse{random.getrandbits(64):016x}"
        parts: list[bytes] = []
        for key, value in normalized.items():
            parts.extend(
                [
                    f"--{boundary}\r\n".encode("ascii"),
                    f'Content-Disposition: form-data; name="{key}"\r\n\r\n'.encode("utf-8"),
                    value.encode("utf-8"),
                    b"\r\n",
                ]
            )
        parts.append(f"--{boundary}--\r\n".encode("ascii"))
        return b"".join(parts), f"multipart/form-data; boundary={boundary}"
    raise ValueError(f"Unsupported form encoding: {encoding}")


def _guess_content_type(path: Path, *, fallback: str = "application/octet-stream") -> str:
    guessed, _ = mimetypes.guess_type(path.name)
    return guessed or fallback


def _encode_multipart_file_payload(
    *,
    file_bytes: bytes,
    field_name: str,
    remote_filename: str,
    file_content_type: str,
    form_fields: dict[str, Any] | None = None,
) -> tuple[bytes, str]:
    boundary = f"----allcanuse{random.getrandbits(64):016x}"
    parts: list[bytes] = []
    for key, value in (form_fields or {}).items():
        normalized_value = "" if value is None else str(value)
        parts.extend(
            [
                f"--{boundary}\r\n".encode("ascii"),
                f'Content-Disposition: form-data; name="{key}"\r\n\r\n'.encode("utf-8"),
                normalized_value.encode("utf-8"),
                b"\r\n",
            ]
        )
    parts.extend(
        [
            f"--{boundary}\r\n".encode("ascii"),
            (
                f'Content-Disposition: form-data; name="{field_name}"; filename="{remote_filename}"\r\n'
            ).encode("utf-8"),
            f"Content-Type: {file_content_type}\r\n\r\n".encode("utf-8"),
            file_bytes,
            b"\r\n",
            f"--{boundary}--\r\n".encode("ascii"),
        ]
    )
    return b"".join(parts), f"multipart/form-data; boundary={boundary}"


def _recv_until(sock: socket.socket, marker: bytes, *, max_bytes: int = 65_536) -> tuple[bytes, bytes]:
    buffer = bytearray()
    while marker not in buffer:
        chunk = sock.recv(4096)
        if not chunk:
            raise ConnectionError("Connection closed before expected marker was received")
        buffer.extend(chunk)
        if len(buffer) > max_bytes:
            raise ValueError("Received data exceeded maximum allowed size")
    marker_index = buffer.index(marker) + len(marker)
    return bytes(buffer[:marker_index]), bytes(buffer[marker_index:])


def _recv_exact(sock: socket.socket, buffer: bytearray, size: int) -> bytes:
    while len(buffer) < size:
        chunk = sock.recv(max(4096, size - len(buffer)))
        if not chunk:
            raise ConnectionError("Connection closed before enough data was received")
        buffer.extend(chunk)
    data = bytes(buffer[:size])
    del buffer[:size]
    return data


def _build_websocket_frame(opcode: int, payload: bytes, *, masked: bool) -> bytes:
    first_byte = 0x80 | (opcode & 0x0F)
    payload_length = len(payload)
    header = bytearray([first_byte])
    mask_bit = 0x80 if masked else 0x00
    if payload_length < 126:
        header.append(mask_bit | payload_length)
    elif payload_length <= 0xFFFF:
        header.append(mask_bit | 126)
        header.extend(struct.pack("!H", payload_length))
    else:
        header.append(mask_bit | 127)
        header.extend(struct.pack("!Q", payload_length))
    if not masked:
        return bytes(header) + payload
    masking_key = os.urandom(4)
    masked_payload = bytes(payload[index] ^ masking_key[index % 4] for index in range(payload_length))
    return bytes(header) + masking_key + masked_payload


def _read_websocket_frame(sock: socket.socket, buffer: bytearray) -> dict[str, Any]:
    first_two = _recv_exact(sock, buffer, 2)
    first_byte, second_byte = first_two[0], first_two[1]
    fin = bool(first_byte & 0x80)
    opcode = first_byte & 0x0F
    masked = bool(second_byte & 0x80)
    payload_length = second_byte & 0x7F
    if payload_length == 126:
        payload_length = struct.unpack("!H", _recv_exact(sock, buffer, 2))[0]
    elif payload_length == 127:
        payload_length = struct.unpack("!Q", _recv_exact(sock, buffer, 8))[0]
    masking_key = _recv_exact(sock, buffer, 4) if masked else b""
    payload = _recv_exact(sock, buffer, payload_length)
    if masked:
        payload = bytes(item ^ masking_key[index % 4] for index, item in enumerate(payload))
    return {
        "fin": fin,
        "opcode": opcode,
        "masked": masked,
        "payload": payload,
    }


def _parse_websocket_url(url: str) -> dict[str, Any]:
    parsed = urlparse(url)
    scheme = parsed.scheme.lower()
    if scheme not in {"ws", "wss"}:
        raise ValueError("WebSocket URL scheme must be ws or wss")
    host = parsed.hostname or ""
    if not host:
        raise ValueError("WebSocket URL must include a hostname")
    port = parsed.port or (443 if scheme == "wss" else 80)
    path = parsed.path or "/"
    if parsed.query:
        path = f"{path}?{parsed.query}"
    return {
        "scheme": scheme,
        "secure": scheme == "wss",
        "host": host,
        "port": port,
        "path": path,
    }


def _perform_websocket_handshake(
    sock: socket.socket,
    *,
    host: str,
    port: int,
    path: str,
    headers: dict[str, str] | None,
    origin: str | None,
    subprotocols: list[str] | None,
) -> tuple[dict[str, Any], bytearray]:
    key = base64.b64encode(os.urandom(16)).decode("ascii")
    host_header = host if port in {80, 443} else f"{host}:{port}"
    request_lines = [
        f"GET {path} HTTP/1.1",
        f"Host: {host_header}",
        "Upgrade: websocket",
        "Connection: Upgrade",
        f"Sec-WebSocket-Key: {key}",
        "Sec-WebSocket-Version: 13",
    ]
    if origin:
        request_lines.append(f"Origin: {origin}")
    if subprotocols:
        request_lines.append(f"Sec-WebSocket-Protocol: {', '.join(subprotocols)}")
    for header_name, header_value in _merge_http_headers(headers).items():
        request_lines.append(f"{header_name}: {header_value}")
    sock.sendall(("\r\n".join(request_lines) + "\r\n\r\n").encode("utf-8"))

    raw_headers, leftover = _recv_until(sock, b"\r\n\r\n")
    header_text = raw_headers.decode("iso-8859-1", errors="replace")
    lines = header_text.split("\r\n")
    status_line = lines[0]
    parts = status_line.split(" ", 2)
    if len(parts) < 2:
        raise ValueError("Invalid WebSocket handshake response")
    status_code = int(parts[1])
    header_map: dict[str, str] = {}
    for line in lines[1:]:
        if not line or ":" not in line:
            continue
        key_name, value = line.split(":", 1)
        header_map[key_name.strip()] = value.strip()

    accept = header_map.get("Sec-WebSocket-Accept", "")
    expected_accept = base64.b64encode(
        hashlib.sha1((key + "258EAFA5-E914-47DA-95CA-C5AB0DC85B11").encode("ascii")).digest()
    ).decode("ascii")
    if status_code != 101:
        raise ValueError(f"WebSocket handshake failed with status {status_code}")
    if header_map.get("Upgrade", "").lower() != "websocket":
        raise ValueError("WebSocket handshake response missing Upgrade: websocket")
    if "upgrade" not in header_map.get("Connection", "").lower():
        raise ValueError("WebSocket handshake response missing Connection: Upgrade")
    if accept != expected_accept:
        raise ValueError("WebSocket handshake returned an unexpected Sec-WebSocket-Accept value")

    return (
        {
            "status_code": status_code,
            "status_line": status_line,
            "headers": header_map,
            "accepted_subprotocol": header_map.get("Sec-WebSocket-Protocol", ""),
        },
        bytearray(leftover),
    )


class _HTMLTextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._skip_depth = 0
        self._pieces: list[str] = []
        self.title_parts: list[str] = []
        self._in_title = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        lowered = tag.lower()
        if lowered in {"script", "style", "noscript"}:
            self._skip_depth += 1
            return
        if lowered == "title":
            self._in_title = True
        if lowered in {"p", "div", "section", "article", "main", "aside", "header", "footer", "br", "li"}:
            self._pieces.append("\n")

    def handle_endtag(self, tag: str) -> None:
        lowered = tag.lower()
        if lowered in {"script", "style", "noscript"} and self._skip_depth > 0:
            self._skip_depth -= 1
            return
        if lowered == "title":
            self._in_title = False
        if lowered in {"p", "div", "section", "article", "main", "aside", "header", "footer", "li"}:
            self._pieces.append("\n")

    def handle_data(self, data: str) -> None:
        if self._skip_depth > 0:
            return
        if self._in_title:
            self.title_parts.append(data)
        cleaned = " ".join(data.split())
        if cleaned:
            self._pieces.append(cleaned)
            self._pieces.append(" ")

    def get_text(self) -> str:
        joined = "".join(self._pieces)
        joined = re.sub(r"[ \t]+\n", "\n", joined)
        joined = re.sub(r"\n{3,}", "\n\n", joined)
        joined = re.sub(r"[ \t]{2,}", " ", joined)
        return joined.strip()

    def get_title(self) -> str:
        return " ".join(" ".join(self.title_parts).split()).strip()


class _LinkExtractor(HTMLParser):
    def __init__(self, *, base_url: str, link_text_max_chars: int = 300) -> None:
        super().__init__(convert_charrefs=True)
        self.base_url = base_url
        self.link_text_max_chars = link_text_max_chars
        self.links: list[dict[str, Any]] = []
        self._current_link: dict[str, Any] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() != "a":
            return
        attr_map = {key.lower(): value or "" for key, value in attrs}
        href = attr_map.get("href", "").strip()
        self._current_link = {
            "href": href,
            "absolute_url": urljoin(self.base_url, href) if href else "",
            "title": attr_map.get("title", ""),
            "target": attr_map.get("target", ""),
            "rel": attr_map.get("rel", ""),
            "text_parts": [],
        }

    def handle_data(self, data: str) -> None:
        if self._current_link is None:
            return
        cleaned = " ".join(data.split())
        if cleaned:
            self._current_link["text_parts"].append(cleaned)

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() != "a" or self._current_link is None:
            return
        text = " ".join(self._current_link.pop("text_parts"))
        text, truncated = _truncate_text(text.strip(), self.link_text_max_chars)
        item = {
            "href": self._current_link["href"],
            "absolute_url": self._current_link["absolute_url"],
            "text": text,
            "text_truncated": truncated,
            "title": self._current_link["title"],
            "target": self._current_link["target"],
            "rel": self._current_link["rel"],
        }
        self.links.append(item)
        self._current_link = None


class _ElementCollector(HTMLParser):
    def __init__(
        self,
        *,
        base_url: str,
        tag: str,
        attr_filters: dict[str, str] | None = None,
        text_max_chars: int = 1000,
    ) -> None:
        super().__init__(convert_charrefs=True)
        self.base_url = base_url
        self.target_tag = tag.lower()
        self.attr_filters = {key.lower(): value for key, value in (attr_filters or {}).items()}
        self.text_max_chars = text_max_chars
        self.matches: list[dict[str, Any]] = []
        self._stack: list[dict[str, Any]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        lowered = tag.lower()
        attr_map = {key.lower(): value or "" for key, value in attrs}
        matched = lowered == self.target_tag and all(attr_map.get(key) == value for key, value in self.attr_filters.items())
        self._stack.append(
            {
                "tag": lowered,
                "attrs": attr_map,
                "matched": matched,
                "text_parts": [],
            }
        )

    def handle_data(self, data: str) -> None:
        cleaned = " ".join(data.split())
        if not cleaned:
            return
        for entry in reversed(self._stack):
            entry["text_parts"].append(cleaned)
            if entry["matched"]:
                break

    def handle_endtag(self, tag: str) -> None:
        lowered = tag.lower()
        if not self._stack:
            return
        entry = self._stack.pop()
        if entry["tag"] != lowered:
            return
        if not entry["matched"]:
            return
        text = " ".join(entry["text_parts"]).strip()
        text, truncated = _truncate_text(text, self.text_max_chars)
        attrs = dict(entry["attrs"])
        href = attrs.get("href", "")
        src = attrs.get("src", "")
        self.matches.append(
            {
                "tag": entry["tag"],
                "attributes": attrs,
                "text": text,
                "text_truncated": truncated,
                "href": href,
                "absolute_href": urljoin(self.base_url, href) if href else "",
                "src": src,
                "absolute_src": urljoin(self.base_url, src) if src else "",
            }
        )


class _TableExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.tables: list[dict[str, Any]] = []
        self._table_stack: list[dict[str, Any]] = []
        self._current_row: list[dict[str, Any]] | None = None
        self._current_cell: dict[str, Any] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        lowered = tag.lower()
        attr_map = {key.lower(): value or "" for key, value in attrs}
        if lowered == "table":
            self._table_stack.append({"attributes": attr_map, "rows": []})
            return
        if not self._table_stack:
            return
        if lowered == "tr":
            self._current_row = []
            return
        if lowered in {"th", "td"} and self._current_row is not None:
            self._current_cell = {
                "tag": lowered,
                "attributes": attr_map,
                "text_parts": [],
            }

    def handle_data(self, data: str) -> None:
        if self._current_cell is None:
            return
        cleaned = " ".join(data.split())
        if cleaned:
            self._current_cell["text_parts"].append(cleaned)

    def handle_endtag(self, tag: str) -> None:
        lowered = tag.lower()
        if lowered in {"th", "td"} and self._current_cell is not None and self._current_row is not None:
            self._current_cell["text"] = " ".join(self._current_cell.pop("text_parts")).strip()
            self._current_row.append(self._current_cell)
            self._current_cell = None
            return
        if lowered == "tr" and self._current_row is not None and self._table_stack:
            self._table_stack[-1]["rows"].append(self._current_row)
            self._current_row = None
            return
        if lowered == "table" and self._table_stack:
            table = self._table_stack.pop()
            headers: list[str] = []
            data_rows: list[list[str]] = []
            for index, row in enumerate(table["rows"]):
                text_row = [cell["text"] for cell in row]
                if not headers and row and all(cell["tag"] == "th" for cell in row):
                    headers = text_row
                else:
                    data_rows.append(text_row)
            if not headers and data_rows:
                headers = [f"column_{idx + 1}" for idx in range(len(data_rows[0]))]
            self.tables.append(
                {
                    "attributes": table["attributes"],
                    "headers": headers,
                    "rows": data_rows,
                }
            )


class _MarkdownExtractor(HTMLParser):
    def __init__(self, *, base_url: str) -> None:
        super().__init__(convert_charrefs=True)
        self.base_url = base_url
        self._skip_depth = 0
        self._pieces: list[str] = []
        self._current_link: dict[str, Any] | None = None
        self._list_stack: list[str] = []
        self._cell_text: list[str] | None = None
        self._table_row: list[str] | None = None
        self._table_rows: list[list[str]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        lowered = tag.lower()
        if lowered in {"script", "style", "noscript"}:
            self._skip_depth += 1
            return
        attr_map = {key.lower(): value or "" for key, value in attrs}
        if lowered in {"h1", "h2", "h3", "h4", "h5", "h6"}:
            level = int(lowered[1])
            self._pieces.append("\n" + ("#" * level) + " ")
        elif lowered in {"p", "div", "section", "article", "main"}:
            self._pieces.append("\n\n")
        elif lowered == "br":
            self._pieces.append("\n")
        elif lowered in {"ul", "ol"}:
            self._list_stack.append(lowered)
            self._pieces.append("\n")
        elif lowered == "li":
            indent = "  " * max(len(self._list_stack) - 1, 0)
            marker = "- " if not self._list_stack or self._list_stack[-1] == "ul" else "1. "
            self._pieces.append(f"\n{indent}{marker}")
        elif lowered in {"strong", "b"}:
            self._pieces.append("**")
        elif lowered in {"em", "i"}:
            self._pieces.append("*")
        elif lowered == "code":
            self._pieces.append("`")
        elif lowered == "a":
            href = attr_map.get("href", "").strip()
            self._current_link = {"href": href, "absolute_url": urljoin(self.base_url, href) if href else "", "text_parts": []}
        elif lowered == "table":
            self._table_rows = []
            self._pieces.append("\n\n")
        elif lowered == "tr":
            self._table_row = []
        elif lowered in {"th", "td"} and self._table_row is not None:
            self._cell_text = []

    def handle_data(self, data: str) -> None:
        if self._skip_depth > 0:
            return
        cleaned = " ".join(data.split())
        if not cleaned:
            return
        if self._current_link is not None:
            self._current_link["text_parts"].append(cleaned)
            return
        if self._cell_text is not None:
            self._cell_text.append(cleaned)
            return
        self._pieces.append(cleaned + " ")

    def handle_endtag(self, tag: str) -> None:
        lowered = tag.lower()
        if lowered in {"script", "style", "noscript"} and self._skip_depth > 0:
            self._skip_depth -= 1
            return
        if lowered in {"strong", "b"}:
            self._pieces.append("**")
        elif lowered in {"em", "i"}:
            self._pieces.append("*")
        elif lowered == "code":
            self._pieces.append("`")
        elif lowered in {"ul", "ol"} and self._list_stack:
            self._list_stack.pop()
            self._pieces.append("\n")
        elif lowered == "a" and self._current_link is not None:
            link_text = " ".join(self._current_link["text_parts"]).strip() or self._current_link["absolute_url"]
            href = self._current_link["absolute_url"] or self._current_link["href"]
            if href:
                self._pieces.append(f"[{link_text}]({href}) ")
            else:
                self._pieces.append(link_text + " ")
            self._current_link = None
        elif lowered in {"th", "td"} and self._cell_text is not None and self._table_row is not None:
            self._table_row.append(" ".join(self._cell_text).strip())
            self._cell_text = None
        elif lowered == "tr" and self._table_row is not None:
            self._table_rows.append(self._table_row)
            self._table_row = None
        elif lowered == "table" and self._table_rows:
            header = self._table_rows[0]
            self._pieces.append("| " + " | ".join(header) + " |\n")
            self._pieces.append("| " + " | ".join("---" for _ in header) + " |\n")
            for row in self._table_rows[1:]:
                padded = row + [""] * max(0, len(header) - len(row))
                self._pieces.append("| " + " | ".join(padded[: len(header)]) + " |\n")
            self._pieces.append("\n")
            self._table_rows = []
        elif lowered in {"p", "div", "section", "article", "main"}:
            self._pieces.append("\n")

    def to_markdown(self) -> str:
        text = "".join(self._pieces)
        text = re.sub(r"[ \t]+\n", "\n", text)
        text = re.sub(r"\n{3,}", "\n\n", text)
        text = re.sub(r"[ \t]{2,}", " ", text)
        return text.strip()


def _normalize_rr_name(name: str, fallback: str) -> str:
    return name.rstrip(".") or fallback


def _encode_dns_name(hostname: str) -> bytes:
    labels = hostname.rstrip(".").split(".")
    encoded = bytearray()
    for label in labels:
        data = label.encode("idna")
        if len(data) > 63:
            raise ValueError(f"DNS label too long: {label}")
        encoded.append(len(data))
        encoded.extend(data)
    encoded.append(0)
    return bytes(encoded)


def _parse_dns_name(message: bytes, offset: int) -> tuple[str, int]:
    labels: list[str] = []
    jumped = False
    next_offset = offset
    seen_offsets: set[int] = set()
    while True:
        if offset >= len(message):
            raise ValueError("DNS name parse exceeded message length")
        length = message[offset]
        if length & 0xC0 == 0xC0:
            if offset + 1 >= len(message):
                raise ValueError("DNS pointer is truncated")
            pointer = ((length & 0x3F) << 8) | message[offset + 1]
            if pointer in seen_offsets:
                raise ValueError("DNS name pointer loop detected")
            seen_offsets.add(pointer)
            if not jumped:
                next_offset = offset + 2
            offset = pointer
            jumped = True
            continue
        if length == 0:
            if not jumped:
                next_offset = offset + 1
            break
        offset += 1
        label = message[offset : offset + length]
        labels.append(label.decode("ascii", errors="replace"))
        offset += length
        if not jumped:
            next_offset = offset
    return ".".join(labels), next_offset


def _decode_dns_rdata(message: bytes, rr_type: int, rdata_offset: int, rdlength: int) -> Any:
    rdata = message[rdata_offset : rdata_offset + rdlength]
    if rr_type == _DNS_TYPE_TO_CODE["A"] and rdlength == 4:
        return socket.inet_ntoa(rdata)
    if rr_type == _DNS_TYPE_TO_CODE["AAAA"] and rdlength == 16:
        return socket.inet_ntop(socket.AF_INET6, rdata)
    if rr_type in {_DNS_TYPE_TO_CODE["CNAME"], _DNS_TYPE_TO_CODE["NS"], _DNS_TYPE_TO_CODE["PTR"]}:
        value, _ = _parse_dns_name(message, rdata_offset)
        return value.rstrip(".")
    if rr_type == _DNS_TYPE_TO_CODE["MX"]:
        preference = struct.unpack("!H", rdata[:2])[0]
        exchange, _ = _parse_dns_name(message, rdata_offset + 2)
        return {"preference": preference, "exchange": exchange.rstrip(".")}
    if rr_type == _DNS_TYPE_TO_CODE["TXT"]:
        parts = []
        cursor = 0
        while cursor < len(rdata):
            length = rdata[cursor]
            cursor += 1
            parts.append(rdata[cursor : cursor + length].decode("utf-8", errors="replace"))
            cursor += length
        return parts
    if rr_type == _DNS_TYPE_TO_CODE["SRV"]:
        priority, weight, port = struct.unpack("!HHH", rdata[:6])
        target, _ = _parse_dns_name(message, rdata_offset + 6)
        return {
            "priority": priority,
            "weight": weight,
            "port": port,
            "target": target.rstrip("."),
        }
    return rdata.hex()


def _build_dns_query(hostname: str, rr_type: int) -> tuple[int, bytes]:
    transaction_id = random.randint(0, 0xFFFF)
    header = struct.pack("!HHHHHH", transaction_id, 0x0100, 1, 0, 0, 0)
    question = _encode_dns_name(hostname) + struct.pack("!HH", rr_type, 1)
    return transaction_id, header + question


def _parse_dns_response(message: bytes, expected_id: int) -> dict[str, Any]:
    if len(message) < 12:
        raise ValueError("DNS response is too short")
    transaction_id, flags, qdcount, ancount, nscount, arcount = struct.unpack("!HHHHHH", message[:12])
    if transaction_id != expected_id:
        raise ValueError("DNS transaction id mismatch")
    rcode = flags & 0x000F
    offset = 12
    questions = []
    for _ in range(qdcount):
        qname, offset = _parse_dns_name(message, offset)
        qtype, qclass = struct.unpack("!HH", message[offset : offset + 4])
        offset += 4
        questions.append({"name": qname.rstrip("."), "type": _DNS_CODE_TO_TYPE.get(qtype, str(qtype)), "class": qclass})

    def read_rr(count: int) -> list[dict[str, Any]]:
        nonlocal offset
        records = []
        for _ in range(count):
            name, offset = _parse_dns_name(message, offset)
            rr_type, rr_class, ttl, rdlength = struct.unpack("!HHIH", message[offset : offset + 10])
            offset += 10
            rdata_offset = offset
            data = _decode_dns_rdata(message, rr_type, rdata_offset, rdlength)
            offset += rdlength
            records.append(
                {
                    "name": name.rstrip("."),
                    "type": _DNS_CODE_TO_TYPE.get(rr_type, str(rr_type)),
                    "class": rr_class,
                    "ttl": ttl,
                    "data": data,
                }
            )
        return records

    answers = read_rr(ancount)
    authorities = read_rr(nscount)
    additionals = read_rr(arcount)
    return {
        "rcode": rcode,
        "rcode_name": _DNS_RCODE_MESSAGES.get(rcode, f"RCODE_{rcode}"),
        "questions": questions,
        "answers": answers,
        "authorities": authorities,
        "additionals": additionals,
    }


def _get_default_dns_servers() -> list[str]:
    candidates: list[str] = []
    resolv_conf = Path("/etc/resolv.conf")
    if resolv_conf.exists():
        for line in resolv_conf.read_text(encoding="utf-8", errors="replace").splitlines():
            stripped = line.strip()
            if stripped.startswith("nameserver "):
                candidates.append(stripped.split(None, 1)[1].strip())

    if platform.system() == "Windows":
        shell = "powershell"
        command = [
            shell,
            "-NoProfile",
            "-Command",
            "Get-DnsClientServerAddress -AddressFamily IPv4,IPv6 | Select-Object -ExpandProperty ServerAddresses",
        ]
        try:
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                check=False,
                timeout=10,
            )
            if result.returncode == 0:
                candidates.extend(line.strip() for line in result.stdout.splitlines() if line.strip())
        except (OSError, subprocess.SubprocessError):
            pass

    servers: list[str] = []
    for candidate in candidates:
        try:
            ipaddress.ip_address(candidate)
        except ValueError:
            continue
        if candidate not in servers:
            servers.append(candidate)

    if servers:
        return servers
    return ["8.8.8.8", "1.1.1.1"]


def _parse_dns_endpoint(value: str) -> tuple[str, int]:
    if value.startswith("[") and "]:" in value:
        host, port = value[1:].split("]:", 1)
        return host, int(port)
    if value.count(":") == 1 and "." in value.split(":", 1)[0]:
        host, port = value.split(":", 1)
        return host, int(port)
    return value, 53


def _query_dns_server(hostname: str, rr_type_name: str, dns_server: str, timeout_ms: int) -> dict[str, Any]:
    rr_type_code = _DNS_TYPE_TO_CODE[rr_type_name]
    transaction_id, query = _build_dns_query(hostname, rr_type_code)
    dns_host, dns_port = _parse_dns_endpoint(dns_server)
    family = socket.AF_INET6 if ":" in dns_host else socket.AF_INET
    server_address = (dns_host, dns_port, 0, 0) if family == socket.AF_INET6 else (dns_host, dns_port)
    with socket.socket(family, socket.SOCK_DGRAM) as sock:
        sock.settimeout(max(timeout_ms, 1) / 1000)
        sock.sendto(query, server_address)
        response, _ = sock.recvfrom(4096)
    parsed = _parse_dns_response(response, transaction_id)
    parsed["dns_server"] = dns_server
    parsed["query_type"] = rr_type_name
    return parsed


def http_request(
    *,
    url: str,
    method: str = "GET",
    headers: dict[str, str] | None = None,
    body: str | None = None,
    timeout_ms: int = 15_000,
    max_body_chars: int = 12_000,
    save_to: str | None = None,
) -> dict[str, Any]:
    try:
        fetched = _fetch_url(url=url, method=method, headers=headers, body=body, timeout_ms=timeout_ms)
        text, truncated = _truncate_text(fetched["text"], max_body_chars)
        result: dict[str, Any] = {
            "ok": True,
            "status": fetched["status"],
            "reason": fetched["reason"],
            "final_url": fetched["final_url"],
            "headers": fetched["headers"],
            "content_type": fetched["content_type"],
            "body": text,
            "body_truncated": truncated,
            "body_bytes": fetched["body_bytes"],
        }
        if save_to:
            target = Path(save_to).expanduser().resolve()
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(fetched["raw"])
            result["saved_to"] = str(target)
        return result
    except HTTPError as exc:
        payload = exc.read().decode("utf-8", errors="replace")
        return {
            "ok": False,
            "status": exc.code,
            "reason": exc.reason,
            "headers": dict(exc.headers.items()),
            "body": payload[:max_body_chars] if max_body_chars > 0 else payload,
        }
    except URLError as exc:
        return {"ok": False, "error": str(exc.reason)}


def http_head(
    *,
    url: str,
    headers: dict[str, str] | None = None,
    timeout_ms: int = 15_000,
) -> dict[str, Any]:
    try:
        fetched = _fetch_response_headers(url=url, method="HEAD", headers=headers, timeout_ms=timeout_ms)
        return {"ok": True, **fetched}
    except HTTPError as exc:
        return {
            "ok": False,
            "status": exc.code,
            "reason": exc.reason,
            "headers": dict(exc.headers.items()),
            "content_type": exc.headers.get("Content-Type", ""),
            "content_length": exc.headers.get("Content-Length", ""),
            "final_url": exc.geturl(),
        }
    except URLError as exc:
        return {"ok": False, "url": url, "error": str(exc.reason)}


def fetch_response_headers(
    *,
    url: str,
    method: str = "GET",
    headers: dict[str, str] | None = None,
    body: str | None = None,
    timeout_ms: int = 15_000,
) -> dict[str, Any]:
    try:
        fetched = _fetch_response_headers(
            url=url,
            method=method,
            headers=headers,
            body=body.encode("utf-8") if body is not None else None,
            timeout_ms=timeout_ms,
        )
        return {"ok": True, **fetched}
    except HTTPError as exc:
        return {
            "ok": False,
            "status": exc.code,
            "reason": exc.reason,
            "headers": dict(exc.headers.items()),
            "content_type": exc.headers.get("Content-Type", ""),
            "content_length": exc.headers.get("Content-Length", ""),
            "final_url": exc.geturl(),
        }
    except URLError as exc:
        return {"ok": False, "url": url, "error": str(exc.reason)}


def submit_web_form(
    *,
    url: str,
    form_fields: dict[str, Any],
    method: str = "POST",
    encoding: str = "application/x-www-form-urlencoded",
    headers: dict[str, str] | None = None,
    timeout_ms: int = 15_000,
    max_body_chars: int = 12_000,
    save_to: str | None = None,
) -> dict[str, Any]:
    method_name = method.upper()
    request_headers = _merge_http_headers(headers)
    request_url = url
    body: bytes | None = None
    content_type = ""

    if method_name == "GET":
        request_url = _append_query_params(url, form_fields)
    elif method_name == "POST":
        body, content_type = _encode_form_payload(form_fields, encoding=encoding)
        _set_default_header(request_headers, "Content-Type", content_type)
    else:
        raise ValueError("submit_web_form only supports GET or POST")

    try:
        request = Request(url=request_url, method=method_name, data=body, headers=request_headers)
        with urlopen(request, timeout=max(timeout_ms, 1) / 1000) as response:
            raw = response.read()
            charset = response.headers.get_content_charset() or "utf-8"
            text = raw.decode(charset, errors="replace")
            body_text, truncated = _truncate_text(text, max_body_chars)
            result: dict[str, Any] = {
                "ok": True,
                "url": url,
                "submitted_url": request_url,
                "method": method_name,
                "encoding": content_type or "query-string",
                "submitted_fields": {str(key): "" if value is None else str(value) for key, value in form_fields.items()},
                "status": response.status,
                "reason": response.reason,
                "final_url": response.geturl(),
                "headers": dict(response.headers.items()),
                "content_type": response.headers.get("Content-Type", ""),
                "body": body_text,
                "body_truncated": truncated,
                "body_bytes": len(raw),
            }
            if save_to:
                target = Path(save_to).expanduser().resolve()
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(raw)
                result["saved_to"] = str(target)
            return result
    except HTTPError as exc:
        payload = exc.read().decode("utf-8", errors="replace")
        return {
            "ok": False,
            "url": url,
            "submitted_url": request_url,
            "method": method_name,
            "encoding": content_type or "query-string",
            "status": exc.code,
            "reason": exc.reason,
            "headers": dict(exc.headers.items()),
            "body": payload[:max_body_chars] if max_body_chars > 0 else payload,
        }
    except URLError as exc:
        return {
            "ok": False,
            "url": url,
            "submitted_url": request_url,
            "method": method_name,
            "encoding": content_type or "query-string",
            "error": str(exc.reason),
        }


def upload_file(
    *,
    url: str,
    file_path: str,
    method: str = "POST",
    upload_mode: str = "multipart",
    field_name: str = "file",
    remote_filename: str | None = None,
    content_type: str | None = None,
    form_fields: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
    timeout_ms: int = 60_000,
    max_body_chars: int = 12_000,
    save_to: str | None = None,
) -> dict[str, Any]:
    source_path = Path(file_path).expanduser().resolve()
    if not source_path.exists():
        raise FileNotFoundError(f"File not found: {source_path}")
    if not source_path.is_file():
        raise ValueError(f"Path is not a file: {source_path}")

    file_bytes = source_path.read_bytes()
    request_headers = _merge_http_headers(headers)
    method_name = method.upper()
    mode = upload_mode.lower()
    resolved_filename = remote_filename or source_path.name
    resolved_content_type = content_type or _guess_content_type(source_path)

    if mode == "multipart":
        body, request_content_type = _encode_multipart_file_payload(
            file_bytes=file_bytes,
            field_name=field_name,
            remote_filename=resolved_filename,
            file_content_type=resolved_content_type,
            form_fields=form_fields,
        )
        _set_default_header(request_headers, "Content-Type", request_content_type)
    elif mode == "raw":
        if form_fields:
            raise ValueError("form_fields are only supported when upload_mode is multipart")
        body = file_bytes
        _set_default_header(request_headers, "Content-Type", resolved_content_type)
    else:
        raise ValueError("upload_mode must be multipart or raw")

    sha256 = hashlib.sha256(file_bytes).hexdigest()
    _set_default_header(request_headers, "Content-Length", str(len(body)))

    try:
        request = Request(url=url, method=method_name, data=body, headers=request_headers)
        with urlopen(request, timeout=max(timeout_ms, 1) / 1000) as response:
            raw = response.read()
            charset = response.headers.get_content_charset() or "utf-8"
            text = raw.decode(charset, errors="replace")
            body_text, truncated = _truncate_text(text, max_body_chars)
            result: dict[str, Any] = {
                "ok": True,
                "url": url,
                "method": method_name,
                "upload_mode": mode,
                "file_path": str(source_path),
                "filename": resolved_filename,
                "field_name": field_name if mode == "multipart" else "",
                "file_bytes": len(file_bytes),
                "request_bytes": len(body),
                "sha256": sha256,
                "content_type": resolved_content_type,
                "status": response.status,
                "reason": response.reason,
                "final_url": response.geturl(),
                "headers": dict(response.headers.items()),
                "response_body": body_text,
                "response_body_truncated": truncated,
                "response_body_bytes": len(raw),
            }
            if form_fields:
                result["form_fields"] = {str(key): "" if value is None else str(value) for key, value in form_fields.items()}
            if save_to:
                target = Path(save_to).expanduser().resolve()
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(raw)
                result["saved_to"] = str(target)
            return result
    except HTTPError as exc:
        payload = exc.read().decode("utf-8", errors="replace")
        result = {
            "ok": False,
            "url": url,
            "method": method_name,
            "upload_mode": mode,
            "file_path": str(source_path),
            "filename": resolved_filename,
            "field_name": field_name if mode == "multipart" else "",
            "file_bytes": len(file_bytes),
            "request_bytes": len(body),
            "sha256": sha256,
            "content_type": resolved_content_type,
            "status": exc.code,
            "reason": exc.reason,
            "headers": dict(exc.headers.items()),
            "response_body": payload[:max_body_chars] if max_body_chars > 0 else payload,
        }
        if form_fields:
            result["form_fields"] = {str(key): "" if value is None else str(value) for key, value in form_fields.items()}
        return result
    except URLError as exc:
        return {
            "ok": False,
            "url": url,
            "method": method_name,
            "upload_mode": mode,
            "file_path": str(source_path),
            "filename": resolved_filename,
            "field_name": field_name if mode == "multipart" else "",
            "file_bytes": len(file_bytes),
            "request_bytes": len(body),
            "sha256": sha256,
            "content_type": resolved_content_type,
            "error": str(exc.reason),
        }


def download_file(
    *,
    url: str,
    destination: str,
    headers: dict[str, str] | None = None,
    timeout_ms: int = 60_000,
    overwrite: bool = False,
) -> dict[str, Any]:
    destination_path = Path(destination).expanduser().resolve()
    if destination_path.exists() and not overwrite:
        raise FileExistsError(f"Destination already exists: {destination_path}")
    destination_path.parent.mkdir(parents=True, exist_ok=True)

    request = Request(url=url, method="GET", headers=_merge_http_headers(headers))
    try:
        with urlopen(request, timeout=max(timeout_ms, 1) / 1000) as response:
            data = response.read()
            destination_path.write_bytes(data)
            return {
                "ok": True,
                "url": url,
                "destination": str(destination_path),
                "status": getattr(response, "status", 200),
                "reason": getattr(response, "reason", "OK"),
                "content_type": response.headers.get("Content-Type", ""),
                "bytes_written": len(data),
                "final_url": response.geturl(),
            }
    except HTTPError as exc:
        payload = exc.read().decode("utf-8", errors="replace")
        return {
            "ok": False,
            "url": url,
            "destination": str(destination_path),
            "status": exc.code,
            "reason": exc.reason,
            "body": payload[:4000],
        }
    except URLError as exc:
        return {
            "ok": False,
            "url": url,
            "destination": str(destination_path),
            "error": str(exc.reason),
        }


def trace_http_redirects(
    *,
    url: str,
    headers: dict[str, str] | None = None,
    timeout_ms: int = 15_000,
    max_hops: int = 10,
) -> dict[str, Any]:
    opener = build_opener(_NoRedirectHandler)
    chain: list[dict[str, Any]] = []
    current_url = url
    for hop in range(max_hops + 1):
        request = Request(url=current_url, method="GET", headers=_merge_http_headers(headers))
        try:
            with opener.open(request, timeout=max(timeout_ms, 1) / 1000) as response:
                chain.append(
                    {
                        "hop": hop,
                        "url": current_url,
                        "status": response.status,
                        "reason": response.reason,
                        "location": response.headers.get("Location", ""),
                        "next_url": "",
                    }
                )
                return {
                    "ok": True,
                    "initial_url": url,
                    "final_url": response.geturl(),
                    "redirect_count": len(chain) - 1,
                    "max_hops_reached": False,
                    "chain": chain,
                }
        except HTTPError as exc:
            status = exc.code
            location = exc.headers.get("Location", "")
            next_url = urljoin(current_url, location) if location else ""
            chain.append(
                {
                    "hop": hop,
                    "url": current_url,
                    "status": status,
                    "reason": exc.reason,
                    "location": location,
                    "next_url": next_url,
                }
            )
            if status in {301, 302, 303, 307, 308} and next_url and hop < max_hops:
                current_url = next_url
                continue
            return {
                "ok": 200 <= status < 400,
                "initial_url": url,
                "final_url": current_url,
                "redirect_count": len(chain) - 1,
                "max_hops_reached": hop >= max_hops and bool(next_url),
                "chain": chain,
            }
        except URLError as exc:
            return {"ok": False, "initial_url": url, "final_url": current_url, "error": str(exc.reason), "chain": chain}
    return {
        "ok": False,
        "initial_url": url,
        "final_url": current_url,
        "redirect_count": len(chain),
        "max_hops_reached": True,
        "chain": chain,
    }


def websocket_connect(
    *,
    url: str,
    messages: list[str] | None = None,
    headers: dict[str, str] | None = None,
    subprotocols: list[str] | None = None,
    origin: str | None = None,
    timeout_ms: int = 5000,
    receive_limit: int = 5,
    receive_max_bytes: int = 65_536,
) -> dict[str, Any]:
    try:
        endpoint = _parse_websocket_url(url)
        timeout_seconds = max(timeout_ms, 1) / 1000
        sent_messages = list(messages or [])
        received_messages: list[dict[str, Any]] = []
        ping_count = 0
        pong_count = 0

        with socket.create_connection((endpoint["host"], endpoint["port"]), timeout=timeout_seconds) as tcp_sock:
            tcp_sock.settimeout(timeout_seconds)
            transport: socket.socket = tcp_sock
            try:
                if endpoint["secure"]:
                    context = ssl.create_default_context()
                    transport = context.wrap_socket(tcp_sock, server_hostname=endpoint["host"])
                    transport.settimeout(timeout_seconds)

                handshake, buffer = _perform_websocket_handshake(
                    transport,
                    host=endpoint["host"],
                    port=endpoint["port"],
                    path=endpoint["path"],
                    headers=headers,
                    origin=origin,
                    subprotocols=subprotocols,
                )

                for message in sent_messages:
                    payload = message.encode("utf-8")
                    transport.sendall(_build_websocket_frame(0x1, payload, masked=True))

                fragmented_opcode: int | None = None
                fragmented_parts: list[bytes] = []
                timed_out = False
                close_frame: dict[str, Any] | None = None

                while len(received_messages) < max(receive_limit, 0):
                    try:
                        frame = _read_websocket_frame(transport, buffer)
                    except socket.timeout:
                        timed_out = True
                        break

                    payload = frame["payload"]
                    if len(payload) > receive_max_bytes:
                        payload = payload[:receive_max_bytes]
                        payload_truncated = True
                    else:
                        payload_truncated = False

                    opcode = frame["opcode"]
                    fin = frame["fin"]
                    if opcode == 0x8:
                        close_code = struct.unpack("!H", payload[:2])[0] if len(payload) >= 2 else None
                        close_reason = payload[2:].decode("utf-8", errors="replace") if len(payload) > 2 else ""
                        close_frame = {"code": close_code, "reason": close_reason}
                        try:
                            transport.sendall(_build_websocket_frame(0x8, payload[:125], masked=True))
                        except OSError:
                            pass
                        break
                    if opcode == 0x9:
                        ping_count += 1
                        transport.sendall(_build_websocket_frame(0xA, payload, masked=True))
                        continue
                    if opcode == 0xA:
                        pong_count += 1
                        continue

                    if opcode in {0x1, 0x2} and not fin:
                        fragmented_opcode = opcode
                        fragmented_parts = [payload]
                        continue
                    if opcode == 0x0 and fragmented_opcode is not None:
                        fragmented_parts.append(payload)
                        if not fin:
                            continue
                        opcode = fragmented_opcode
                        payload = b"".join(fragmented_parts)
                        fragmented_opcode = None
                        fragmented_parts = []
                        payload_truncated = len(payload) > receive_max_bytes
                        if payload_truncated:
                            payload = payload[:receive_max_bytes]
                    elif opcode == 0x0:
                        continue

                    item: dict[str, Any] = {
                        "opcode": opcode,
                        "opcode_name": "text" if opcode == 0x1 else "binary" if opcode == 0x2 else f"opcode_{opcode}",
                        "payload_bytes": len(payload),
                        "payload_truncated": payload_truncated,
                    }
                    if opcode == 0x1:
                        item["text"] = payload.decode("utf-8", errors="replace")
                    else:
                        encoded = _decode_payload(
                            payload,
                            output_encoding="base64",
                            max_chars=max(receive_max_bytes * 2, 1),
                        )
                        item["base64"] = encoded["text"]
                        item["base64_truncated"] = encoded["text_truncated"]
                    received_messages.append(item)

                try:
                    transport.sendall(_build_websocket_frame(0x8, struct.pack("!H", 1000), masked=True))
                except OSError:
                    pass
            finally:
                if transport is not tcp_sock:
                    transport.close()

        return {
            "ok": True,
            "url": url,
            "host": endpoint["host"],
            "port": endpoint["port"],
            "secure": endpoint["secure"],
            "path": endpoint["path"],
            "handshake": handshake,
            "sent_count": len(sent_messages),
            "sent_messages": sent_messages,
            "received_count": len(received_messages),
            "received_messages": received_messages,
            "timed_out": timed_out,
            "ping_count": ping_count,
            "pong_count": pong_count,
            "close_frame": close_frame,
        }
    except (OSError, ssl.SSLError, ValueError, ConnectionError) as exc:
        return {"ok": False, "url": url, "error": str(exc)}


def webpage_to_markdown(
    *,
    url: str,
    headers: dict[str, str] | None = None,
    timeout_ms: int = 20_000,
    max_markdown_chars: int = 30_000,
) -> dict[str, Any]:
    try:
        fetched = _fetch_url(url=url, headers=headers, timeout_ms=timeout_ms)
        parser = _MarkdownExtractor(base_url=fetched["final_url"])
        parser.feed(fetched["text"])
        parser.close()
        markdown, truncated = _truncate_text(parser.to_markdown(), max_markdown_chars)
        return {
            "ok": True,
            "url": url,
            "final_url": fetched["final_url"],
            "status": fetched["status"],
            "content_type": fetched["content_type"],
            "markdown": markdown,
            "markdown_truncated": truncated,
            "body_bytes": fetched["body_bytes"],
        }
    except HTTPError as exc:
        return {"ok": False, "url": url, "status": exc.code, "reason": exc.reason}
    except URLError as exc:
        return {"ok": False, "url": url, "error": str(exc.reason)}


def fetch_webpage_text(
    *,
    url: str,
    headers: dict[str, str] | None = None,
    timeout_ms: int = 20_000,
    max_text_chars: int = 20_000,
    include_title: bool = True,
) -> dict[str, Any]:
    try:
        fetched = _fetch_url(url=url, headers=headers, timeout_ms=timeout_ms)
        parser = _HTMLTextExtractor()
        parser.feed(fetched["text"])
        parser.close()
        page_text, truncated = _truncate_text(parser.get_text(), max_text_chars)
        return {
            "ok": True,
            "url": url,
            "final_url": fetched["final_url"],
            "status": fetched["status"],
            "reason": fetched["reason"],
            "content_type": fetched["content_type"],
            "title": parser.get_title() if include_title else "",
            "text": page_text,
            "text_truncated": truncated,
            "body_bytes": fetched["body_bytes"],
        }
    except HTTPError as exc:
        return {
            "ok": False,
            "url": url,
            "status": exc.code,
            "reason": exc.reason,
        }
    except URLError as exc:
        return {"ok": False, "url": url, "error": str(exc.reason)}


def extract_links_from_webpage(
    *,
    url: str,
    headers: dict[str, str] | None = None,
    timeout_ms: int = 20_000,
    text_filter: str | None = None,
    href_filter: str | None = None,
    max_links: int = 200,
    link_text_max_chars: int = 300,
) -> dict[str, Any]:
    try:
        fetched = _fetch_url(url=url, headers=headers, timeout_ms=timeout_ms)
        parser = _LinkExtractor(base_url=fetched["final_url"], link_text_max_chars=link_text_max_chars)
        parser.feed(fetched["text"])
        parser.close()

        links = parser.links
        if text_filter:
            needle = text_filter.casefold()
            links = [item for item in links if needle in item["text"].casefold()]
        if href_filter:
            needle = href_filter.casefold()
            links = [
                item
                for item in links
                if needle in item["href"].casefold() or needle in item["absolute_url"].casefold()
            ]
        truncated = len(links) > max_links > 0
        if truncated:
            links = links[:max_links]
        return {
            "ok": True,
            "url": url,
            "final_url": fetched["final_url"],
            "status": fetched["status"],
            "content_type": fetched["content_type"],
            "count": len(links),
            "links_truncated": truncated,
            "links": links,
        }
    except HTTPError as exc:
        return {
            "ok": False,
            "url": url,
            "status": exc.code,
            "reason": exc.reason,
        }
    except URLError as exc:
        return {"ok": False, "url": url, "error": str(exc.reason)}


def extract_webpage_elements(
    *,
    url: str,
    tag: str,
    attr_filters: dict[str, str] | None = None,
    headers: dict[str, str] | None = None,
    timeout_ms: int = 20_000,
    max_elements: int = 100,
    text_max_chars: int = 1000,
) -> dict[str, Any]:
    if not tag.strip():
        raise ValueError("tag must not be empty")
    try:
        fetched = _fetch_url(url=url, headers=headers, timeout_ms=timeout_ms)
        parser = _ElementCollector(
            base_url=fetched["final_url"],
            tag=tag,
            attr_filters=attr_filters,
            text_max_chars=text_max_chars,
        )
        parser.feed(fetched["text"])
        parser.close()
        elements = parser.matches
        truncated = len(elements) > max_elements > 0
        if truncated:
            elements = elements[:max_elements]
        return {
            "ok": True,
            "url": url,
            "final_url": fetched["final_url"],
            "status": fetched["status"],
            "content_type": fetched["content_type"],
            "count": len(elements),
            "elements_truncated": truncated,
            "elements": elements,
        }
    except HTTPError as exc:
        return {
            "ok": False,
            "url": url,
            "status": exc.code,
            "reason": exc.reason,
        }
    except URLError as exc:
        return {"ok": False, "url": url, "error": str(exc.reason)}


def extract_tables_from_webpage(
    *,
    url: str,
    headers: dict[str, str] | None = None,
    timeout_ms: int = 20_000,
    max_tables: int = 20,
    max_rows_per_table: int = 200,
) -> dict[str, Any]:
    try:
        fetched = _fetch_url(url=url, headers=headers, timeout_ms=timeout_ms)
        parser = _TableExtractor()
        parser.feed(fetched["text"])
        parser.close()
        tables = parser.tables
        tables_truncated = len(tables) > max_tables > 0
        if tables_truncated:
            tables = tables[:max_tables]
        normalized_tables = []
        for table in tables:
            rows = table["rows"]
            rows_truncated = len(rows) > max_rows_per_table > 0
            if rows_truncated:
                rows = rows[:max_rows_per_table]
            normalized_tables.append(
                {
                    "attributes": table["attributes"],
                    "headers": table["headers"],
                    "row_count": len(rows),
                    "rows_truncated": rows_truncated,
                    "rows": rows,
                }
            )
        return {
            "ok": True,
            "url": url,
            "final_url": fetched["final_url"],
            "status": fetched["status"],
            "content_type": fetched["content_type"],
            "count": len(normalized_tables),
            "tables_truncated": tables_truncated,
            "tables": normalized_tables,
        }
    except HTTPError as exc:
        return {"ok": False, "url": url, "status": exc.code, "reason": exc.reason}
    except URLError as exc:
        return {"ok": False, "url": url, "error": str(exc.reason)}


def resolve_dns_records(
    hostname: str,
    *,
    record_types: list[str] | None = None,
    dns_server: str | None = None,
    timeout_ms: int = 3000,
) -> dict[str, Any]:
    requested_types = [item.upper() for item in (record_types or ["A", "AAAA", "CNAME", "MX", "TXT", "NS", "SRV"])]
    unsupported = [item for item in requested_types if item not in _DNS_TYPE_TO_CODE]
    if unsupported:
        raise ValueError(f"Unsupported record types: {', '.join(unsupported)}")

    servers = [dns_server] if dns_server else _get_default_dns_servers()
    results: dict[str, Any] = {}
    for rr_type in requested_types:
        last_error = ""
        for server in servers:
            try:
                parsed = _query_dns_server(hostname, rr_type, server, timeout_ms)
                results[rr_type] = {
                    "ok": parsed["rcode"] == 0,
                    "dns_server": server,
                    "rcode": parsed["rcode"],
                    "rcode_name": parsed["rcode_name"],
                    "answers": parsed["answers"],
                    "authorities": parsed["authorities"],
                    "additionals": parsed["additionals"],
                }
                break
            except (OSError, ValueError) as exc:
                last_error = str(exc)
        else:
            results[rr_type] = {
                "ok": False,
                "dns_server": servers[0] if servers else "",
                "error": last_error or "No DNS server available",
                "answers": [],
            }

    return {
        "hostname": hostname,
        "record_types": requested_types,
        "dns_servers": servers,
        "results": results,
    }


def reverse_dns_lookup(ip_address: str) -> dict[str, Any]:
    host, aliases, addresses = socket.gethostbyaddr(ip_address)
    return {
        "ip_address": ip_address,
        "host": host,
        "aliases": aliases,
        "addresses": addresses,
    }


def dns_lookup(hostname: str) -> dict[str, Any]:
    results = socket.getaddrinfo(hostname, None)
    addresses: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for family, _, _, _, sockaddr in results:
        address = sockaddr[0]
        family_name = "IPv6" if family == socket.AF_INET6 else "IPv4"
        key = (family_name, address)
        if key in seen:
            continue
        seen.add(key)
        addresses.append({"family": family_name, "address": address})
    return {"hostname": hostname, "addresses": addresses}


def _flatten_name_tuples(values: tuple[tuple[tuple[str, str], ...], ...] | tuple[Any, ...]) -> dict[str, str]:
    flattened: dict[str, str] = {}
    for item in values:
        if isinstance(item, tuple):
            for key, value in item:
                flattened[key] = value
    return flattened


def get_tls_certificate(
    host: str,
    *,
    port: int = 443,
    server_hostname: str | None = None,
    timeout_ms: int = 5000,
    verify: bool = False,
) -> dict[str, Any]:
    context = ssl.create_default_context()
    if not verify:
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE

    timeout = max(timeout_ms, 1) / 1000
    with socket.create_connection((host, port), timeout=timeout) as tcp_socket:
        with context.wrap_socket(tcp_socket, server_hostname=server_hostname or host) as tls_socket:
            der_cert = tls_socket.getpeercert(binary_form=True)
            pem_cert = ssl.DER_cert_to_PEM_cert(der_cert)
            with tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".pem", delete=False) as handle:
                handle.write(pem_cert)
                temp_path = handle.name
            try:
                certificate = ssl._ssl._test_decode_cert(temp_path)
            finally:
                try:
                    os.unlink(temp_path)
                except OSError:
                    pass

            subject = _flatten_name_tuples(certificate.get("subject", ()))
            issuer = _flatten_name_tuples(certificate.get("issuer", ()))
            subject_alt_names = [
                {"type": kind, "value": value}
                for kind, value in certificate.get("subjectAltName", ())
            ]
            return {
                "host": host,
                "port": port,
                "server_hostname": server_hostname or host,
                "verify": verify,
                "tls_version": tls_socket.version(),
                "cipher": tls_socket.cipher(),
                "alpn_protocol": tls_socket.selected_alpn_protocol(),
                "subject": subject,
                "issuer": issuer,
                "subject_alt_names": subject_alt_names,
                "serial_number": certificate.get("serialNumber", ""),
                "not_before": certificate.get("notBefore", ""),
                "not_after": certificate.get("notAfter", ""),
                "sha256_fingerprint": hashlib.sha256(der_cert).hexdigest(),
                "sha1_fingerprint": hashlib.sha1(der_cert).hexdigest(),
            }


def trace_route(
    host: str,
    *,
    max_hops: int = 30,
    timeout_ms: int = 5000,
) -> dict[str, Any]:
    system = platform.system()
    if system == "Windows":
        command = ["tracert", "-d", "-h", str(max_hops), "-w", str(timeout_ms), host]
    else:
        per_probe_seconds = max(1, int(timeout_ms / 1000))
        command = ["traceroute", "-n", "-m", str(max_hops), "-w", str(per_probe_seconds), host]
    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    return {
        "ok": result.returncode == 0,
        "host": host,
        "command": command,
        "returncode": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr,
    }


def adapters_to_json(data: dict[str, Any]) -> str:
    return json.dumps(data, ensure_ascii=False, indent=2)


def ping_host(hostname: str, *, count: int = 4, timeout_ms: int = 4000) -> dict[str, Any]:
    system = platform.system()
    if system == "Windows":
        command = ["ping", "-n", str(count), "-w", str(timeout_ms), hostname]
    else:
        per_probe_seconds = max(1, int(timeout_ms / 1000))
        command = ["ping", "-c", str(count), "-W", str(per_probe_seconds), hostname]

    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    return {
        "ok": result.returncode == 0,
        "hostname": hostname,
        "command": command,
        "returncode": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr,
    }


def tcp_connect(host: str, port: int, *, timeout_ms: int = 3000) -> dict[str, Any]:
    try:
        with socket.create_connection((host, port), timeout=max(timeout_ms, 1) / 1000) as conn:
            local_host, local_port = conn.getsockname()[:2]
            remote_host, remote_port = conn.getpeername()[:2]
            return {
                "ok": True,
                "host": host,
                "port": port,
                "local_address": local_host,
                "local_port": local_port,
                "remote_address": remote_host,
                "remote_port": remote_port,
            }
    except OSError as exc:
        return {
            "ok": False,
            "host": host,
            "port": port,
            "error": str(exc),
        }


def raw_tcp_exchange(
    host: str,
    port: int,
    *,
    data: str,
    timeout_ms: int = 5000,
    recv_max_bytes: int = 4096,
    input_encoding: str = "utf-8",
    output_encoding: str = "utf-8",
) -> dict[str, Any]:
    payload = _encode_payload(data, input_encoding=input_encoding)
    received = bytearray()
    with socket.create_connection((host, port), timeout=max(timeout_ms, 1) / 1000) as conn:
        conn.settimeout(max(timeout_ms, 1) / 1000)
        conn.sendall(payload)
        try:
            conn.shutdown(socket.SHUT_WR)
        except OSError:
            pass
        truncated = False
        while len(received) < recv_max_bytes:
            chunk = conn.recv(min(4096, recv_max_bytes - len(received)))
            if not chunk:
                break
            received.extend(chunk)
        else:
            truncated = True
    decoded = _decode_payload(bytes(received), output_encoding=output_encoding)
    return {
        "ok": True,
        "host": host,
        "port": port,
        "bytes_sent": len(payload),
        "bytes_received": len(received),
        "response": decoded["text"],
        "response_truncated": truncated or decoded["text_truncated"],
        "response_hex": bytes(received).hex(),
    }


def udp_send_receive(
    host: str,
    port: int,
    *,
    data: str,
    timeout_ms: int = 3000,
    recv_max_bytes: int = 4096,
    input_encoding: str = "utf-8",
    output_encoding: str = "utf-8",
) -> dict[str, Any]:
    payload = _encode_payload(data, input_encoding=input_encoding)
    family = socket.AF_INET6 if ":" in host else socket.AF_INET
    with socket.socket(family, socket.SOCK_DGRAM) as sock:
        sock.settimeout(max(timeout_ms, 1) / 1000)
        sock.sendto(payload, (host, port))
        received, remote = sock.recvfrom(recv_max_bytes)
    decoded = _decode_payload(received, output_encoding=output_encoding)
    return {
        "ok": True,
        "host": host,
        "port": port,
        "bytes_sent": len(payload),
        "bytes_received": len(received),
        "remote_address": remote[0],
        "remote_port": remote[1],
        "response": decoded["text"],
        "response_truncated": decoded["text_truncated"],
        "response_hex": received.hex(),
    }


def scan_ports(
    host: str,
    *,
    ports: list[int] | None = None,
    start_port: int | None = None,
    end_port: int | None = None,
    timeout_ms: int = 500,
    open_only: bool = True,
    max_results: int = 200,
) -> dict[str, Any]:
    if ports:
        candidates = sorted({int(port) for port in ports})
    elif start_port is not None and end_port is not None:
        if start_port > end_port:
            raise ValueError("start_port must be <= end_port")
        candidates = list(range(start_port, end_port + 1))
    else:
        raise ValueError("Provide either ports or start_port and end_port")

    results = []
    truncated = False
    timeout = max(timeout_ms, 1) / 1000
    for port in candidates:
        family = socket.AF_INET6 if ":" in host else socket.AF_INET
        with socket.socket(family, socket.SOCK_STREAM) as sock:
            sock.settimeout(timeout)
            status = sock.connect_ex((host, port))
        is_open = status == 0
        if open_only and not is_open:
            continue
        results.append(
            {
                "port": port,
                "open": is_open,
                "status_code": status,
            }
        )
        if len(results) >= max_results > 0:
            truncated = True
            break
    return {
        "host": host,
        "scanned_count": len(candidates),
        "result_count": len(results),
        "open_only": open_only,
        "truncated": truncated,
        "results": results,
    }


def list_established_connections(limit: int = 200) -> dict[str, Any]:
    import psutil

    connections = []
    for conn in psutil.net_connections(kind="inet"):
        if conn.status != psutil.CONN_ESTABLISHED or not conn.laddr or not conn.raddr:
            continue
        process_name = ""
        if conn.pid:
            try:
                process_name = psutil.Process(conn.pid).name()
            except (psutil.AccessDenied, psutil.NoSuchProcess):
                process_name = ""
        connections.append(
            {
                "family": str(conn.family),
                "type": str(conn.type),
                "local_ip": conn.laddr.ip,
                "local_port": conn.laddr.port,
                "remote_ip": conn.raddr.ip,
                "remote_port": conn.raddr.port,
                "pid": conn.pid,
                "process_name": process_name,
                "status": conn.status,
            }
        )
    connections.sort(key=lambda item: (item["local_ip"], item["local_port"], item["remote_ip"], item["remote_port"]))
    truncated = len(connections) > limit > 0
    if truncated:
        connections = connections[:limit]
    return {"count": len(connections), "truncated": truncated, "connections": connections}


def list_listening_ports() -> dict[str, Any]:
    import psutil

    listeners = []
    for conn in psutil.net_connections(kind="inet"):
        if conn.status != psutil.CONN_LISTEN or not conn.laddr:
            continue
        listeners.append(
            {
                "family": str(conn.family),
                "type": str(conn.type),
                "ip": conn.laddr.ip,
                "port": conn.laddr.port,
                "pid": conn.pid,
            }
        )
    listeners.sort(key=lambda item: (item["ip"], item["port"]))
    return {"count": len(listeners), "listeners": listeners}
