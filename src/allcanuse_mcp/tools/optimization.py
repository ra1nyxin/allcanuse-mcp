from __future__ import annotations

from allcanuse_mcp.core.asset_optimization import optimize_images_for_memory as optimize_images_for_memory_impl
from allcanuse_mcp.core.seo_tools import audit_seo as audit_seo_impl
from allcanuse_mcp.descriptions import TOOL_DESCRIPTIONS


def register(mcp) -> None:
    @mcp.tool(description=TOOL_DESCRIPTIONS["audit_seo"])
    def audit_seo(
        target: str,
        max_pages: int = 50,
        include_hidden: bool = False,
        max_file_size_bytes: int = 2_000_000,
        timeout_ms: int = 15_000,
    ) -> dict:
        return audit_seo_impl(
            target,
            max_pages=max_pages,
            include_hidden=include_hidden,
            max_file_size_bytes=max_file_size_bytes,
            timeout_ms=timeout_ms,
        )

    @mcp.tool(description=TOOL_DESCRIPTIONS["optimize_images_for_memory"])
    def optimize_images_for_memory(
        paths: list[str],
        output_dir: str | None = None,
        quality: int = 85,
        max_width: int | None = None,
        max_height: int | None = None,
        convert_to: str | None = None,
        overwrite: bool = False,
        recursive: bool = False,
        suffix: str = ".optimized",
    ) -> dict:
        return optimize_images_for_memory_impl(
            paths,
            output_dir=output_dir,
            quality=quality,
            max_width=max_width,
            max_height=max_height,
            convert_to=convert_to,
            overwrite=overwrite,
            recursive=recursive,
            suffix=suffix,
        )
