from __future__ import annotations

from pathlib import Path
from typing import Any

from mcp.server.fastmcp.utilities.types import Image
from mcp.types import CallToolResult, TextContent


def build_image_tool_result(
    payload: dict[str, Any],
    *,
    summary: str,
    include_text: bool = True,
) -> CallToolResult:
    path = payload.get("path")
    if not path:
        raise ValueError("payload must include image file path")
    image_path = Path(path).expanduser().resolve()

    content = []
    if include_text:
        content.append(TextContent(type="text", text=summary))
    content.append(Image(path=image_path).to_image_content())

    return CallToolResult(
        content=content,
        structuredContent=payload,
        isError=not bool(payload.get("ok", True)),
    )
