from __future__ import annotations

from allcanuse_mcp.core.c_tools import compile_c_program as compile_c_program_impl
from allcanuse_mcp.core.c_tools import detect_c_toolchains as detect_c_toolchains_impl
from allcanuse_mcp.core.c_tools import format_c_code as format_c_code_impl
from allcanuse_mcp.core.c_tools import inspect_c_source as inspect_c_source_impl
from allcanuse_mcp.descriptions import TOOL_DESCRIPTIONS


def register(mcp) -> None:
    @mcp.tool(description=TOOL_DESCRIPTIONS["detect_c_toolchains"])
    def detect_c_toolchains() -> dict:
        return detect_c_toolchains_impl()

    @mcp.tool(description=TOOL_DESCRIPTIONS["compile_c_program"])
    def compile_c_program(
        source_files: list[str],
        output_path: str | None = None,
        include_dirs: list[str] | None = None,
        library_dirs: list[str] | None = None,
        libraries: list[str] | None = None,
        c_standard: str = "c11",
        extra_args: list[str] | None = None,
        cwd: str | None = None,
        preferred_compiler: str | None = None,
        timeout_ms: int = 120_000,
        run_after_compile: bool = False,
        run_args: list[str] | None = None,
    ) -> dict:
        return compile_c_program_impl(
            source_files,
            output_path=output_path,
            include_dirs=include_dirs,
            library_dirs=library_dirs,
            libraries=libraries,
            c_standard=c_standard,
            extra_args=extra_args,
            cwd=cwd,
            preferred_compiler=preferred_compiler,
            timeout_ms=timeout_ms,
            run_after_compile=run_after_compile,
            run_args=run_args,
        )

    @mcp.tool(description=TOOL_DESCRIPTIONS["inspect_c_source"])
    def inspect_c_source(paths: list[str], recursive: bool = True, max_files: int = 200) -> dict:
        return inspect_c_source_impl(paths, recursive=recursive, max_files=max_files)

    @mcp.tool(description=TOOL_DESCRIPTIONS["format_c_code"])
    def format_c_code(paths: list[str], in_place: bool = False, style: str = "file", recursive: bool = False, max_files: int = 100) -> dict:
        return format_c_code_impl(paths, in_place=in_place, style=style, recursive=recursive, max_files=max_files)
