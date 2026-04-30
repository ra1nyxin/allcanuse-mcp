from __future__ import annotations

import platform
import os
from datetime import datetime, timezone as dt_timezone
from zoneinfo import ZoneInfo

import psutil

from allcanuse_mcp.core.command_runner import run_cmd
from allcanuse_mcp.core.command_runner import run_shell
from allcanuse_mcp.descriptions import TOOL_DESCRIPTIONS


def register(mcp) -> None:
    @mcp.tool(description=TOOL_DESCRIPTIONS["get_system_info"])
    def get_system_info() -> dict:
        uname = platform.uname()
        memory = psutil.virtual_memory()
        return {
            "platform": platform.platform(),
            "system": uname.system,
            "release": uname.release,
            "version": uname.version,
            "machine": uname.machine,
            "processor": uname.processor,
            "hostname": uname.node,
            "python_version": platform.python_version(),
            "cpu_count_logical": psutil.cpu_count(logical=True),
            "cpu_count_physical": psutil.cpu_count(logical=False),
            "memory_total": memory.total,
            "memory_available": memory.available,
            "memory_percent": memory.percent,
            "boot_time": datetime.fromtimestamp(psutil.boot_time()).astimezone().isoformat(),
            "current_working_directory": os.getcwd(),
        }

    @mcp.tool(description=TOOL_DESCRIPTIONS["get_env"])
    def get_env(names: list[str] | None = None) -> dict:
        if names:
            selected = {name: os.environ.get(name) for name in names}
        else:
            selected = dict(sorted(os.environ.items()))
        return {"count": len(selected), "variables": selected}

    @mcp.tool(description=TOOL_DESCRIPTIONS["get_time"])
    def get_time(timezone: str | None = None) -> dict:
        local_now = datetime.now().astimezone()
        utc_now = datetime.now(dt_timezone.utc)
        result = {
            "local_time": local_now.isoformat(),
            "local_timezone": str(local_now.tzinfo),
            "utc_time": utc_now.isoformat(),
        }
        if timezone:
            target = datetime.now(ZoneInfo(timezone))
            result["requested_timezone"] = timezone
            result["requested_time"] = target.isoformat()
        return result

    @mcp.tool(description=TOOL_DESCRIPTIONS["get_disk_usage"])
    def get_disk_usage(path: str = ".") -> dict:
        usage = psutil.disk_usage(path)
        return {
            "path": path,
            "total": usage.total,
            "used": usage.used,
            "free": usage.free,
            "percent": usage.percent,
        }

    @mcp.tool(description=TOOL_DESCRIPTIONS["get_network_config"])
    def get_network_config(max_output_chars: int = 12_000, timeout_ms: int = 30_000) -> dict:
        return _get_network_config(max_output_chars=max_output_chars, timeout_ms=timeout_ms)

    @mcp.tool(description=TOOL_DESCRIPTIONS["get_ipconfig"])
    def get_ipconfig(max_output_chars: int = 12_000, timeout_ms: int = 30_000) -> dict:
        return _get_network_config(max_output_chars=max_output_chars, timeout_ms=timeout_ms)

    @mcp.tool(description=TOOL_DESCRIPTIONS["list_network_adapters"])
    def list_network_adapters() -> dict:
        return _collect_network_adapters()


def _collect_network_adapters() -> dict:
    addrs = psutil.net_if_addrs()
    stats = psutil.net_if_stats()
    adapters: list[dict] = []
    for name, addr_list in addrs.items():
        adapter = {
            "name": name,
            "is_up": stats.get(name).isup if name in stats else None,
            "speed_mbps": stats.get(name).speed if name in stats else None,
            "mtu": stats.get(name).mtu if name in stats else None,
            "addresses": [],
        }
        for item in addr_list:
            adapter["addresses"].append(
                {
                    "family": str(item.family),
                    "address": item.address,
                    "netmask": item.netmask,
                    "broadcast": item.broadcast,
                }
            )
        adapters.append(adapter)
    return {"adapters": adapters, "count": len(adapters)}


def _get_network_config(*, max_output_chars: int, timeout_ms: int) -> dict:
    system = platform.system()
    if system == "Windows":
        result = run_cmd(
            "ipconfig /all",
            max_output_chars=max_output_chars,
            encoding="gbk",
            timeout_ms=timeout_ms,
        )
        result["platform"] = "Windows"
        result["command"] = "ipconfig /all"
    else:
        result = run_shell(
            "ip addr && printf '\\n--- ROUTES ---\\n' && ip route",
            max_output_chars=max_output_chars,
            encoding="utf-8",
            timeout_ms=timeout_ms,
        )
        if not result.get("ok"):
            result = run_shell(
                "ifconfig && printf '\\n--- ROUTES ---\\n' && route -n",
                max_output_chars=max_output_chars,
                encoding="utf-8",
                timeout_ms=timeout_ms,
            )
            result["command"] = "ifconfig && route -n"
        else:
            result["command"] = "ip addr && ip route"
        result["platform"] = system
    result["network_adapters"] = _collect_network_adapters()
    return result
