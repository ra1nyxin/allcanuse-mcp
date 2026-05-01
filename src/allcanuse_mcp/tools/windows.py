from __future__ import annotations

from allcanuse_mcp.core.windows import capture_desktop_screenshot
from allcanuse_mcp.core.vision_payloads import build_image_tool_result
from allcanuse_mcp.core.windows import get_desktop_context as get_desktop_context_impl
from allcanuse_mcp.core.windows import get_active_window_info
from allcanuse_mcp.core.windows import list_windows_info
from allcanuse_mcp.descriptions import TOOL_DESCRIPTIONS


def register(mcp) -> None:
    @mcp.tool(description=TOOL_DESCRIPTIONS["list_windows"])
    def list_windows(
        include_invisible: bool = False,
        title_filter: str | None = None,
        limit: int = 200,
    ) -> dict:
        return list_windows_info(
            include_invisible=include_invisible,
            title_filter=title_filter,
            limit=limit,
        )

    @mcp.tool(description=TOOL_DESCRIPTIONS["get_active_window"])
    def get_active_window() -> dict:
        return get_active_window_info()

    @mcp.tool(description=TOOL_DESCRIPTIONS["get_desktop_context"])
    def get_desktop_context(limit: int = 50, include_invisible: bool = False) -> dict:
        return get_desktop_context_impl(limit=limit, include_invisible=include_invisible)

    @mcp.tool(description=TOOL_DESCRIPTIONS["capture_screenshot"])
    def capture_screenshot(
        output_path: str | None = None,
        all_screens: bool = True,
        return_image_content: bool = False,
        include_image_preview_text: bool = True,
    ):
        result = capture_desktop_screenshot(output_path, all_screens=all_screens)
        if return_image_content and result.get("ok") and result.get("path"):
            summary = (
                f"桌面截图已生成：{result['path']}，"
                f"尺寸信息：{result.get('width') or '?'}x{result.get('height') or '?'}。"
                "如果当前客户端支持视觉内容，这张图像已经随工具结果一并返回。"
            )
            return build_image_tool_result(result, summary=summary, include_text=include_image_preview_text)
        return result
