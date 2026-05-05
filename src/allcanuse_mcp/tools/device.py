from __future__ import annotations

from allcanuse_mcp.core.device import capture_camera_photo as capture_camera_photo_impl
from allcanuse_mcp.core.vision_payloads import build_image_tool_result
from allcanuse_mcp.core.device import list_cameras as list_cameras_impl
from allcanuse_mcp.descriptions import TOOL_DESCRIPTIONS


def register(mcp) -> None:
    @mcp.tool(description=TOOL_DESCRIPTIONS["list_cameras"])
    def list_cameras(max_devices: int = 8) -> dict:
        return list_cameras_impl(max_devices=max_devices)

    @mcp.tool(description=TOOL_DESCRIPTIONS["capture_camera_photo"])
    def capture_camera_photo(
        camera_index: int = 0,
        output_path: str | None = None,
        warmup_ms: int = 10_000,
        return_image_content: bool = False,
        include_image_preview_text: bool = True,
    ):
        result = capture_camera_photo_impl(camera_index=camera_index, output_path=output_path, warmup_ms=warmup_ms)
        if return_image_content and result.get("ok") and result.get("path"):
            summary = (
                f"摄像头照片已生成：{result['path']}，"
                f"尺寸信息：{result.get('width') or '?'}x{result.get('height') or '?'}。"
                "如果当前客户端支持视觉内容，这张图像已经随工具结果一并返回。"
            )
            return build_image_tool_result(result, summary=summary, include_text=include_image_preview_text)
        return result
