from __future__ import annotations

import os
import shutil
import signal
import socket
import struct
from pathlib import Path
from typing import Any

try:
    import fcntl
except ImportError:
    fcntl = None


_PROC_ROOT = Path("/proc")
_SYS_NET_ROOT = Path("/sys/class/net")
_STATE_MAP = {
    "R": "running",
    "S": "sleeping",
    "D": "disk_sleep",
    "T": "stopped",
    "t": "tracing_stop",
    "Z": "zombie",
    "X": "dead",
    "I": "idle",
}
_TCP_STATES = {
    "01": "ESTABLISHED",
    "02": "SYN_SENT",
    "03": "SYN_RECV",
    "04": "FIN_WAIT1",
    "05": "FIN_WAIT2",
    "06": "TIME_WAIT",
    "07": "CLOSE",
    "08": "CLOSE_WAIT",
    "09": "LAST_ACK",
    "0A": "LISTEN",
    "0B": "CLOSING",
}
_SIOCGIFADDR = 0x8915
_SIOCGIFBRDADDR = 0x8919
_SIOCGIFNETMASK = 0x891B


def linux_procfs_available() -> bool:
    return os.name != "nt" and _PROC_ROOT.exists()


def get_virtual_memory() -> dict[str, Any]:
    values: dict[str, int] = {}
    for line in _safe_read_text(_PROC_ROOT / "meminfo").splitlines():
        if ":" not in line:
            continue
        key, raw = line.split(":", 1)
        parts = raw.strip().split()
        if not parts:
            continue
        try:
            values[key] = int(parts[0]) * 1024
        except ValueError:
            continue
    total = values.get("MemTotal", 0)
    available = values.get("MemAvailable", values.get("MemFree", 0))
    used = max(total - available, 0)
    percent = (used / total * 100) if total else 0.0
    return {
        "total": total,
        "available": available,
        "used": used,
        "percent": round(percent, 2),
    }


def get_boot_time() -> float | None:
    for line in _safe_read_text(_PROC_ROOT / "stat").splitlines():
        if line.startswith("btime "):
            try:
                return float(line.split()[1])
            except (IndexError, ValueError):
                return None
    return None


def get_cpu_count_physical() -> int | None:
    cpuinfo = _safe_read_text(_PROC_ROOT / "cpuinfo")
    if not cpuinfo:
        return None
    seen: set[tuple[str, str]] = set()
    current_physical = ""
    current_core = ""
    for line in cpuinfo.splitlines():
        if not line.strip():
            if current_physical or current_core:
                seen.add((current_physical, current_core))
            current_physical = ""
            current_core = ""
            continue
        if ":" not in line:
            continue
        key, value = [item.strip() for item in line.split(":", 1)]
        if key == "physical id":
            current_physical = value
        elif key == "core id":
            current_core = value
    if current_physical or current_core:
        seen.add((current_physical, current_core))
    if seen:
        return len(seen)
    logical = os.cpu_count()
    return logical if logical and logical > 0 else None


def get_disk_usage(path: str) -> dict[str, Any]:
    usage = shutil.disk_usage(path)
    percent = (usage.used / usage.total * 100) if usage.total else 0.0
    return {
        "total": usage.total,
        "used": usage.used,
        "free": usage.free,
        "percent": round(percent, 2),
    }


def list_network_adapters() -> dict[str, Any]:
    adapters: list[dict[str, Any]] = []
    ipv6_map = _read_ipv6_addresses()
    for item in sorted(_SYS_NET_ROOT.iterdir(), key=lambda path: path.name.lower()) if _SYS_NET_ROOT.exists() else []:
        if not item.is_dir():
            continue
        adapter = {
            "name": item.name,
            "is_up": _safe_read_text(item / "operstate").strip() == "up",
            "speed_mbps": _read_int(item / "speed"),
            "mtu": _read_int(item / "mtu"),
            "addresses": [],
        }
        ipv4_address = _ioctl_ipv4(item.name, _SIOCGIFADDR)
        if ipv4_address:
            adapter["addresses"].append(
                {
                    "family": str(socket.AF_INET),
                    "address": ipv4_address,
                    "netmask": _ioctl_ipv4(item.name, _SIOCGIFNETMASK),
                    "broadcast": _ioctl_ipv4(item.name, _SIOCGIFBRDADDR),
                }
            )
        for ipv6_item in ipv6_map.get(item.name, []):
            adapter["addresses"].append(ipv6_item)
        adapters.append(adapter)
    return {"adapters": adapters, "count": len(adapters)}


def list_processes(*, limit: int = 200, name_filter: str | None = None) -> list[dict[str, Any]]:
    lowered = name_filter.casefold() if name_filter else None
    matched: list[dict[str, Any]] = []
    for pid in _iter_pids():
        info = get_process_info(pid)
        if not info:
            continue
        name = info.get("name") or ""
        if lowered and lowered not in name.casefold():
            continue
        matched.append(info)
        if len(matched) >= limit:
            break
    return matched


def find_matching_processes(pid: int | None = None, name: str | None = None) -> list[dict[str, Any]]:
    matches: list[dict[str, Any]] = []
    target_name = name.casefold() if name else None
    for proc_pid in _iter_pids():
        info = get_process_info(proc_pid)
        if not info:
            continue
        if pid is not None and info["pid"] != pid:
            continue
        if target_name and (info.get("name") or "").casefold() != target_name:
            continue
        matches.append(
            {
                "pid": info["pid"],
                "name": info.get("name") or "",
                "status": info.get("status") or "",
            }
        )
    return matches


def kill_processes(pid: int | None = None, name: str | None = None, *, force: bool = True) -> list[dict[str, Any]]:
    signal_value = signal.SIGKILL if force else signal.SIGTERM
    killed: list[dict[str, Any]] = []
    seen: set[int] = set()
    for match in find_matching_processes(pid=pid, name=name):
        proc_pid = int(match["pid"])
        if proc_pid in seen:
            continue
        try:
            os.kill(proc_pid, signal_value)
        except OSError:
            continue
        seen.add(proc_pid)
        killed.append({"pid": proc_pid, "name": match.get("name") or ""})
    return killed


def get_process_tree(pid: int, *, max_depth: int = 5) -> dict[str, Any]:
    root = get_process_info(pid) or {"pid": pid}
    children_map: dict[int, list[int]] = {}
    for proc_pid in _iter_pids():
        info = get_process_info(proc_pid)
        if not info:
            continue
        parent_pid = info.get("ppid")
        if isinstance(parent_pid, int):
            children_map.setdefault(parent_pid, []).append(proc_pid)
    return {
        "root": root,
        "children": _collect_children(pid, depth=1, max_depth=max_depth, children_map=children_map),
    }


def get_process_info(pid: int) -> dict[str, Any] | None:
    proc_dir = _PROC_ROOT / str(pid)
    if not proc_dir.exists():
        return None
    status_info = _read_status(proc_dir / "status")
    name = status_info.get("Name") or _safe_read_text(proc_dir / "comm").strip()
    ppid = _parse_int(status_info.get("PPid"))
    state_value = (status_info.get("State") or "").split()
    state_code = state_value[0] if state_value else ""
    return {
        "pid": pid,
        "name": name,
        "status": _STATE_MAP.get(state_code, state_code.lower() or None),
        "exe": _safe_readlink(proc_dir / "exe"),
        "cmdline": _read_cmdline(proc_dir / "cmdline"),
        "ppid": ppid,
        "memory_rss": _parse_status_memory(status_info.get("VmRSS")),
    }


def safe_process_name(pid: int) -> str | None:
    info = get_process_info(pid)
    return info.get("name") if info else None


def safe_process_exe(pid: int) -> str | None:
    info = get_process_info(pid)
    return info.get("exe") if info else None


def find_port_process(port: int) -> dict[str, Any] | None:
    for conn in _iter_socket_connections():
        if not conn.get("local_port") or int(conn["local_port"]) != port:
            continue
        pid = conn.get("pid")
        process = get_process_info(pid) if isinstance(pid, int) else None
        return {
            "found": True,
            "port": port,
            "status": conn["status"],
            "local_address": f'{conn["local_ip"]}:{conn["local_port"]}',
            "remote_address": (
                f'{conn["remote_ip"]}:{conn["remote_port"]}' if conn.get("remote_ip") and conn.get("remote_port") else None
            ),
            "pid": pid,
            "process": process or ({"pid": pid} if pid else None),
        }
    return None


def list_established_connections(limit: int = 200) -> dict[str, Any]:
    connections = []
    for conn in _iter_socket_connections():
        if conn["status"] != "ESTABLISHED":
            continue
        connections.append(
            {
                "family": str(conn["family"]),
                "type": str(conn["type"]),
                "local_ip": conn["local_ip"],
                "local_port": conn["local_port"],
                "remote_ip": conn["remote_ip"],
                "remote_port": conn["remote_port"],
                "pid": conn.get("pid"),
                "process_name": safe_process_name(conn["pid"]) if conn.get("pid") else "",
                "status": conn["status"],
            }
        )
    connections.sort(key=lambda item: (item["local_ip"], item["local_port"], item["remote_ip"], item["remote_port"]))
    truncated = len(connections) > limit > 0
    if truncated:
        connections = connections[:limit]
    return {"count": len(connections), "truncated": truncated, "connections": connections}


def list_listening_ports() -> dict[str, Any]:
    listeners = []
    for conn in _iter_socket_connections():
        if conn["status"] != "LISTEN":
            continue
        listeners.append(
            {
                "family": str(conn["family"]),
                "type": str(conn["type"]),
                "ip": conn["local_ip"],
                "port": conn["local_port"],
                "pid": conn.get("pid"),
            }
        )
    listeners.sort(key=lambda item: (item["ip"], item["port"]))
    return {"count": len(listeners), "listeners": listeners}


def _collect_children(
    pid: int,
    *,
    depth: int,
    max_depth: int,
    children_map: dict[int, list[int]],
) -> list[dict[str, Any]]:
    if depth > max_depth:
        return []
    nodes: list[dict[str, Any]] = []
    for child_pid in children_map.get(pid, []):
        info = get_process_info(child_pid) or {"pid": child_pid}
        info["children"] = _collect_children(
            child_pid,
            depth=depth + 1,
            max_depth=max_depth,
            children_map=children_map,
        )
        nodes.append(info)
    return nodes


def _iter_socket_connections() -> list[dict[str, Any]]:
    inode_map = _build_socket_inode_map()
    connections: list[dict[str, Any]] = []
    connections.extend(_parse_proc_net_table(_PROC_ROOT / "net/tcp", socket.AF_INET, socket.SOCK_STREAM, inode_map))
    connections.extend(_parse_proc_net_table(_PROC_ROOT / "net/tcp6", socket.AF_INET6, socket.SOCK_STREAM, inode_map))
    return connections


def _parse_proc_net_table(
    path: Path,
    family: int,
    sock_type: int,
    inode_map: dict[int, list[int]],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    text = _safe_read_text(path)
    for line in text.splitlines()[1:]:
        parts = line.split()
        if len(parts) < 10:
            continue
        local_ip, local_port = _decode_proc_address(parts[1], family)
        remote_ip, remote_port = _decode_proc_address(parts[2], family)
        inode = _parse_int(parts[9])
        pids = inode_map.get(inode or -1, [])
        rows.append(
            {
                "family": family,
                "type": sock_type,
                "local_ip": local_ip,
                "local_port": local_port,
                "remote_ip": remote_ip,
                "remote_port": remote_port,
                "status": _TCP_STATES.get(parts[3].upper(), parts[3].upper()),
                "inode": inode,
                "pid": pids[0] if pids else None,
            }
        )
    return rows


def _build_socket_inode_map() -> dict[int, list[int]]:
    mapping: dict[int, list[int]] = {}
    for pid in _iter_pids():
        fd_dir = _PROC_ROOT / str(pid) / "fd"
        if not fd_dir.exists():
            continue
        try:
            entries = list(fd_dir.iterdir())
        except OSError:
            continue
        for entry in entries:
            target = _safe_readlink(entry)
            if not target.startswith("socket:[") or not target.endswith("]"):
                continue
            inode = _parse_int(target[8:-1])
            if inode is None:
                continue
            mapping.setdefault(inode, []).append(pid)
    return mapping


def _decode_proc_address(value: str, family: int) -> tuple[str, int]:
    address_hex, port_hex = value.split(":", 1)
    port = int(port_hex, 16)
    if family == socket.AF_INET:
        raw = bytes.fromhex(address_hex)[::-1]
    else:
        packed = bytes.fromhex(address_hex)
        raw = b"".join(packed[index : index + 4][::-1] for index in range(0, len(packed), 4))
    return socket.inet_ntop(family, raw), port


def _read_ipv6_addresses() -> dict[str, list[dict[str, Any]]]:
    mapping: dict[str, list[dict[str, Any]]] = {}
    text = _safe_read_text(_PROC_ROOT / "net/if_inet6")
    for line in text.splitlines():
        parts = line.split()
        if len(parts) < 6:
            continue
        hex_address, _, prefix_length, _, _, name = parts[:6]
        try:
            address = socket.inet_ntop(socket.AF_INET6, bytes.fromhex(hex_address))
        except (OSError, ValueError):
            continue
        mapping.setdefault(name, []).append(
            {
                "family": str(socket.AF_INET6),
                "address": address,
                "netmask": prefix_length,
                "broadcast": None,
            }
        )
    return mapping


def _ioctl_ipv4(interface_name: str, request_code: int) -> str | None:
    if fcntl is None:
        return None
    if_name = struct.pack("256s", interface_name[:15].encode("utf-8"))
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            response = fcntl.ioctl(sock.fileno(), request_code, if_name)
        return socket.inet_ntoa(response[20:24])
    except OSError:
        return None


def _iter_pids() -> list[int]:
    if not _PROC_ROOT.exists():
        return []
    pids = []
    for entry in _PROC_ROOT.iterdir():
        if entry.is_dir() and entry.name.isdigit():
            pids.append(int(entry.name))
    pids.sort()
    return pids


def _read_status(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in _safe_read_text(path).splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        values[key.strip()] = value.strip()
    return values


def _read_cmdline(path: Path) -> list[str]:
    try:
        raw = path.read_bytes()
    except OSError:
        return []
    parts = [item.decode("utf-8", errors="replace") for item in raw.split(b"\x00") if item]
    return parts


def _parse_status_memory(value: str | None) -> int | None:
    if not value:
        return None
    parts = value.split()
    if not parts:
        return None
    try:
        return int(parts[0]) * 1024
    except ValueError:
        return None


def _read_int(path: Path) -> int | None:
    raw = _safe_read_text(path).strip()
    if not raw:
        return None
    try:
        value = int(raw)
    except ValueError:
        return None
    return value if value >= 0 else None


def _parse_int(value: str | None) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except ValueError:
        return None


def _safe_read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def _safe_readlink(path: Path) -> str:
    try:
        return os.readlink(path)
    except OSError:
        return ""
