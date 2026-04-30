from __future__ import annotations

from allcanuse_mcp.core.device import capture_camera_photo as capture_camera_photo_impl
from allcanuse_mcp.core.device import list_cameras as list_cameras_impl
from allcanuse_mcp.descriptions import TOOL_DESCRIPTIONS


def register(mcp) -> None:
    @mcp.tool(description=TOOL_DESCRIPTIONS["list_cameras"])
    def list_cameras(max_devices: int = 8) -> dict:
        return list_cameras_impl(max_devices=max_devices)

    @mcp.tool(description=TOOL_DESCRIPTIONS["capture_camera_photo"])
    def capture_camera_photo(camera_index: int = 0, output_path: str | None = None) -> dict:
        return capture_camera_photo_impl(camera_index=camera_index, output_path=output_path)
