from __future__ import annotations

from allcanuse_mcp.core.networking import dns_lookup as dns_lookup_impl
from allcanuse_mcp.core.networking import download_file as download_file_impl
from allcanuse_mcp.core.networking import extract_links_from_webpage as extract_links_from_webpage_impl
from allcanuse_mcp.core.networking import extract_webpage_elements as extract_webpage_elements_impl
from allcanuse_mcp.core.networking import extract_tables_from_webpage as extract_tables_from_webpage_impl
from allcanuse_mcp.core.networking import fetch_response_headers as fetch_response_headers_impl
from allcanuse_mcp.core.networking import fetch_webpage_text as fetch_webpage_text_impl
from allcanuse_mcp.core.networking import get_tls_certificate as get_tls_certificate_impl
from allcanuse_mcp.core.networking import http_head as http_head_impl
from allcanuse_mcp.core.networking import http_request as http_request_impl
from allcanuse_mcp.core.networking import list_established_connections as list_established_connections_impl
from allcanuse_mcp.core.networking import list_listening_ports as list_listening_ports_impl
from allcanuse_mcp.core.networking import ping_host as ping_host_impl
from allcanuse_mcp.core.networking import raw_tcp_exchange as raw_tcp_exchange_impl
from allcanuse_mcp.core.networking import scan_ports as scan_ports_impl
from allcanuse_mcp.core.networking import resolve_dns_records as resolve_dns_records_impl
from allcanuse_mcp.core.networking import reverse_dns_lookup as reverse_dns_lookup_impl
from allcanuse_mcp.core.networking import submit_web_form as submit_web_form_impl
from allcanuse_mcp.core.networking import tcp_connect as tcp_connect_impl
from allcanuse_mcp.core.networking import trace_http_redirects as trace_http_redirects_impl
from allcanuse_mcp.core.networking import trace_route as trace_route_impl
from allcanuse_mcp.core.networking import udp_send_receive as udp_send_receive_impl
from allcanuse_mcp.core.networking import upload_file as upload_file_impl
from allcanuse_mcp.core.networking import webpage_to_markdown as webpage_to_markdown_impl
from allcanuse_mcp.core.networking import websocket_connect as websocket_connect_impl
from allcanuse_mcp.descriptions import TOOL_DESCRIPTIONS


def register(mcp) -> None:
    @mcp.tool(description=TOOL_DESCRIPTIONS["download_file"])
    def download_file(
        url: str,
        destination: str,
        headers: dict[str, str] | None = None,
        timeout_ms: int = 60_000,
        overwrite: bool = False,
    ) -> dict:
        return download_file_impl(
            url=url,
            destination=destination,
            headers=headers,
            timeout_ms=timeout_ms,
            overwrite=overwrite,
        )

    @mcp.tool(description=TOOL_DESCRIPTIONS["http_request"])
    def http_request(
        url: str,
        method: str = "GET",
        headers: dict[str, str] | None = None,
        body: str | None = None,
        timeout_ms: int = 15_000,
        max_body_chars: int = 12_000,
        save_to: str | None = None,
    ) -> dict:
        return http_request_impl(
            url=url,
            method=method,
            headers=headers,
            body=body,
            timeout_ms=timeout_ms,
            max_body_chars=max_body_chars,
            save_to=save_to,
        )

    @mcp.tool(description=TOOL_DESCRIPTIONS["http_head"])
    def http_head(
        url: str,
        headers: dict[str, str] | None = None,
        timeout_ms: int = 15_000,
    ) -> dict:
        return http_head_impl(
            url=url,
            headers=headers,
            timeout_ms=timeout_ms,
        )

    @mcp.tool(description=TOOL_DESCRIPTIONS["fetch_response_headers"])
    def fetch_response_headers(
        url: str,
        method: str = "GET",
        headers: dict[str, str] | None = None,
        body: str | None = None,
        timeout_ms: int = 15_000,
    ) -> dict:
        return fetch_response_headers_impl(
            url=url,
            method=method,
            headers=headers,
            body=body,
            timeout_ms=timeout_ms,
        )

    @mcp.tool(description=TOOL_DESCRIPTIONS["submit_web_form"])
    def submit_web_form(
        url: str,
        form_fields: dict[str, str],
        method: str = "POST",
        encoding: str = "application/x-www-form-urlencoded",
        headers: dict[str, str] | None = None,
        timeout_ms: int = 15_000,
        max_body_chars: int = 12_000,
        save_to: str | None = None,
    ) -> dict:
        return submit_web_form_impl(
            url=url,
            form_fields=form_fields,
            method=method,
            encoding=encoding,
            headers=headers,
            timeout_ms=timeout_ms,
            max_body_chars=max_body_chars,
            save_to=save_to,
        )

    @mcp.tool(description=TOOL_DESCRIPTIONS["upload_file"])
    def upload_file(
        url: str,
        file_path: str,
        method: str = "POST",
        upload_mode: str = "multipart",
        field_name: str = "file",
        remote_filename: str | None = None,
        content_type: str | None = None,
        form_fields: dict[str, str] | None = None,
        headers: dict[str, str] | None = None,
        timeout_ms: int = 60_000,
        max_body_chars: int = 12_000,
        save_to: str | None = None,
    ) -> dict:
        return upload_file_impl(
            url=url,
            file_path=file_path,
            method=method,
            upload_mode=upload_mode,
            field_name=field_name,
            remote_filename=remote_filename,
            content_type=content_type,
            form_fields=form_fields,
            headers=headers,
            timeout_ms=timeout_ms,
            max_body_chars=max_body_chars,
            save_to=save_to,
        )

    @mcp.tool(description=TOOL_DESCRIPTIONS["fetch_webpage_text"])
    def fetch_webpage_text(
        url: str,
        headers: dict[str, str] | None = None,
        timeout_ms: int = 20_000,
        max_text_chars: int = 20_000,
        include_title: bool = True,
    ) -> dict:
        return fetch_webpage_text_impl(
            url=url,
            headers=headers,
            timeout_ms=timeout_ms,
            max_text_chars=max_text_chars,
            include_title=include_title,
        )

    @mcp.tool(description=TOOL_DESCRIPTIONS["webpage_to_markdown"])
    def webpage_to_markdown(
        url: str,
        headers: dict[str, str] | None = None,
        timeout_ms: int = 20_000,
        max_markdown_chars: int = 30_000,
    ) -> dict:
        return webpage_to_markdown_impl(
            url=url,
            headers=headers,
            timeout_ms=timeout_ms,
            max_markdown_chars=max_markdown_chars,
        )

    @mcp.tool(description=TOOL_DESCRIPTIONS["extract_links_from_webpage"])
    def extract_links_from_webpage(
        url: str,
        headers: dict[str, str] | None = None,
        timeout_ms: int = 20_000,
        text_filter: str | None = None,
        href_filter: str | None = None,
        max_links: int = 200,
        link_text_max_chars: int = 300,
    ) -> dict:
        return extract_links_from_webpage_impl(
            url=url,
            headers=headers,
            timeout_ms=timeout_ms,
            text_filter=text_filter,
            href_filter=href_filter,
            max_links=max_links,
            link_text_max_chars=link_text_max_chars,
        )

    @mcp.tool(description=TOOL_DESCRIPTIONS["extract_tables_from_webpage"])
    def extract_tables_from_webpage(
        url: str,
        headers: dict[str, str] | None = None,
        timeout_ms: int = 20_000,
        max_tables: int = 20,
        max_rows_per_table: int = 200,
    ) -> dict:
        return extract_tables_from_webpage_impl(
            url=url,
            headers=headers,
            timeout_ms=timeout_ms,
            max_tables=max_tables,
            max_rows_per_table=max_rows_per_table,
        )

    @mcp.tool(description=TOOL_DESCRIPTIONS["extract_webpage_elements"])
    def extract_webpage_elements(
        url: str,
        tag: str,
        attr_filters: dict[str, str] | None = None,
        headers: dict[str, str] | None = None,
        timeout_ms: int = 20_000,
        max_elements: int = 100,
        text_max_chars: int = 1000,
    ) -> dict:
        return extract_webpage_elements_impl(
            url=url,
            tag=tag,
            attr_filters=attr_filters,
            headers=headers,
            timeout_ms=timeout_ms,
            max_elements=max_elements,
            text_max_chars=text_max_chars,
        )

    @mcp.tool(description=TOOL_DESCRIPTIONS["trace_http_redirects"])
    def trace_http_redirects(
        url: str,
        headers: dict[str, str] | None = None,
        timeout_ms: int = 15_000,
        max_hops: int = 10,
    ) -> dict:
        return trace_http_redirects_impl(
            url=url,
            headers=headers,
            timeout_ms=timeout_ms,
            max_hops=max_hops,
        )

    @mcp.tool(description=TOOL_DESCRIPTIONS["websocket_connect"])
    def websocket_connect(
        url: str,
        messages: list[str] | None = None,
        headers: dict[str, str] | None = None,
        subprotocols: list[str] | None = None,
        origin: str | None = None,
        timeout_ms: int = 5000,
        receive_limit: int = 5,
        receive_max_bytes: int = 65536,
    ) -> dict:
        return websocket_connect_impl(
            url=url,
            messages=messages,
            headers=headers,
            subprotocols=subprotocols,
            origin=origin,
            timeout_ms=timeout_ms,
            receive_limit=receive_limit,
            receive_max_bytes=receive_max_bytes,
        )

    @mcp.tool(description=TOOL_DESCRIPTIONS["trace_route"])
    def trace_route(host: str, max_hops: int = 30, timeout_ms: int = 5000) -> dict:
        return trace_route_impl(host, max_hops=max_hops, timeout_ms=timeout_ms)

    @mcp.tool(description=TOOL_DESCRIPTIONS["resolve_dns_records"])
    def resolve_dns_records(
        hostname: str,
        record_types: list[str] | None = None,
        dns_server: str | None = None,
        timeout_ms: int = 3000,
    ) -> dict:
        return resolve_dns_records_impl(
            hostname,
            record_types=record_types,
            dns_server=dns_server,
            timeout_ms=timeout_ms,
        )

    @mcp.tool(description=TOOL_DESCRIPTIONS["reverse_dns_lookup"])
    def reverse_dns_lookup(ip_address: str) -> dict:
        return reverse_dns_lookup_impl(ip_address)

    @mcp.tool(description=TOOL_DESCRIPTIONS["dns_lookup"])
    def dns_lookup(hostname: str) -> dict:
        return dns_lookup_impl(hostname)

    @mcp.tool(description=TOOL_DESCRIPTIONS["get_tls_certificate"])
    def get_tls_certificate(
        host: str,
        port: int = 443,
        server_hostname: str | None = None,
        timeout_ms: int = 5000,
        verify: bool = False,
    ) -> dict:
        return get_tls_certificate_impl(
            host,
            port=port,
            server_hostname=server_hostname,
            timeout_ms=timeout_ms,
            verify=verify,
        )

    @mcp.tool(description=TOOL_DESCRIPTIONS["ping_host"])
    def ping_host(hostname: str, count: int = 4, timeout_ms: int = 4000) -> dict:
        return ping_host_impl(hostname, count=count, timeout_ms=timeout_ms)

    @mcp.tool(description=TOOL_DESCRIPTIONS["tcp_connect"])
    def tcp_connect(host: str, port: int, timeout_ms: int = 3000) -> dict:
        return tcp_connect_impl(host, port, timeout_ms=timeout_ms)

    @mcp.tool(description=TOOL_DESCRIPTIONS["raw_tcp_exchange"])
    def raw_tcp_exchange(
        host: str,
        port: int,
        data: str,
        timeout_ms: int = 5000,
        recv_max_bytes: int = 4096,
        input_encoding: str = "utf-8",
        output_encoding: str = "utf-8",
    ) -> dict:
        return raw_tcp_exchange_impl(
            host,
            port,
            data=data,
            timeout_ms=timeout_ms,
            recv_max_bytes=recv_max_bytes,
            input_encoding=input_encoding,
            output_encoding=output_encoding,
        )

    @mcp.tool(description=TOOL_DESCRIPTIONS["udp_send_receive"])
    def udp_send_receive(
        host: str,
        port: int,
        data: str,
        timeout_ms: int = 3000,
        recv_max_bytes: int = 4096,
        input_encoding: str = "utf-8",
        output_encoding: str = "utf-8",
    ) -> dict:
        return udp_send_receive_impl(
            host,
            port,
            data=data,
            timeout_ms=timeout_ms,
            recv_max_bytes=recv_max_bytes,
            input_encoding=input_encoding,
            output_encoding=output_encoding,
        )

    @mcp.tool(description=TOOL_DESCRIPTIONS["scan_ports"])
    def scan_ports(
        host: str,
        ports: list[int] | None = None,
        start_port: int | None = None,
        end_port: int | None = None,
        timeout_ms: int = 500,
        open_only: bool = True,
        max_results: int = 200,
    ) -> dict:
        return scan_ports_impl(
            host,
            ports=ports,
            start_port=start_port,
            end_port=end_port,
            timeout_ms=timeout_ms,
            open_only=open_only,
            max_results=max_results,
        )

    @mcp.tool(description=TOOL_DESCRIPTIONS["list_established_connections"])
    def list_established_connections(limit: int = 200) -> dict:
        return list_established_connections_impl(limit=limit)

    @mcp.tool(description=TOOL_DESCRIPTIONS["list_listening_ports"])
    def list_listening_ports() -> dict:
        return list_listening_ports_impl()
