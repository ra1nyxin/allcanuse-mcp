from __future__ import annotations

from allcanuse_mcp.core.c_tools import compile_c_program as compile_c_program_impl
from allcanuse_mcp.core.c_tools import check_c_syntax as check_c_syntax_impl
from allcanuse_mcp.core.c_tools import detect_c_toolchains as detect_c_toolchains_impl
from allcanuse_mcp.core.c_tools import format_c_code as format_c_code_impl
from allcanuse_mcp.core.c_tools import generate_c_build_files as generate_c_build_files_impl
from allcanuse_mcp.core.c_tools import generate_c_math_utils_header as generate_c_math_utils_header_impl
from allcanuse_mcp.core.c_tools import generate_c_numeric_test_harness as generate_c_numeric_test_harness_impl
from allcanuse_mcp.core.c_tools import inspect_c_source as inspect_c_source_impl
from allcanuse_mcp.core.c_tools import preprocess_c_source as preprocess_c_source_impl
from allcanuse_mcp.core.c_tools import evaluate_c_math_expression as evaluate_c_math_expression_impl
from allcanuse_mcp.core.c_tools import scan_c_memory_risks as scan_c_memory_risks_impl
from allcanuse_mcp.core.c_tools import scan_c_numeric_risks as scan_c_numeric_risks_impl
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

    @mcp.tool(description=TOOL_DESCRIPTIONS["check_c_syntax"])
    def check_c_syntax(
        source_files: list[str],
        include_dirs: list[str] | None = None,
        c_standard: str = "c11",
        extra_args: list[str] | None = None,
        cwd: str | None = None,
        preferred_compiler: str | None = None,
        timeout_ms: int = 120_000,
    ) -> dict:
        return check_c_syntax_impl(
            source_files,
            include_dirs=include_dirs,
            c_standard=c_standard,
            extra_args=extra_args,
            cwd=cwd,
            preferred_compiler=preferred_compiler,
            timeout_ms=timeout_ms,
        )

    @mcp.tool(description=TOOL_DESCRIPTIONS["preprocess_c_source"])
    def preprocess_c_source(
        source_file: str,
        include_dirs: list[str] | None = None,
        defines: dict[str, str | int | None] | None = None,
        undefines: list[str] | None = None,
        c_standard: str = "c11",
        cwd: str | None = None,
        preferred_compiler: str | None = None,
        timeout_ms: int = 120_000,
        max_output_chars: int = 80_000,
    ) -> dict:
        return preprocess_c_source_impl(
            source_file,
            include_dirs=include_dirs,
            defines=defines,
            undefines=undefines,
            c_standard=c_standard,
            cwd=cwd,
            preferred_compiler=preferred_compiler,
            timeout_ms=timeout_ms,
            max_output_chars=max_output_chars,
        )

    @mcp.tool(description=TOOL_DESCRIPTIONS["inspect_c_source"])
    def inspect_c_source(paths: list[str], recursive: bool = True, max_files: int = 200) -> dict:
        return inspect_c_source_impl(paths, recursive=recursive, max_files=max_files)

    @mcp.tool(description=TOOL_DESCRIPTIONS["scan_c_memory_risks"])
    def scan_c_memory_risks(paths: list[str], recursive: bool = True, max_files: int = 200, max_results: int = 500) -> dict:
        return scan_c_memory_risks_impl(paths, recursive=recursive, max_files=max_files, max_results=max_results)

    @mcp.tool(description=TOOL_DESCRIPTIONS["scan_c_numeric_risks"])
    def scan_c_numeric_risks(paths: list[str], recursive: bool = True, max_files: int = 200, max_results: int = 500) -> dict:
        return scan_c_numeric_risks_impl(paths, recursive=recursive, max_files=max_files, max_results=max_results)

    @mcp.tool(description=TOOL_DESCRIPTIONS["evaluate_c_math_expression"])
    def evaluate_c_math_expression(
        expression: str,
        variables: dict[str, float | int] | None = None,
        c_standard: str = "c11",
        preferred_compiler: str | None = None,
        timeout_ms: int = 120_000,
    ) -> dict:
        return evaluate_c_math_expression_impl(
            expression,
            variables=variables,
            c_standard=c_standard,
            preferred_compiler=preferred_compiler,
            timeout_ms=timeout_ms,
        )

    @mcp.tool(description=TOOL_DESCRIPTIONS["generate_c_numeric_test_harness"])
    def generate_c_numeric_test_harness(
        path: str,
        function_name: str,
        cases: list[dict],
        include_path: str | None = None,
        tolerance: float = 1e-9,
        overwrite: bool = False,
    ) -> dict:
        return generate_c_numeric_test_harness_impl(
            path,
            function_name=function_name,
            cases=cases,
            include_path=include_path,
            tolerance=tolerance,
            overwrite=overwrite,
        )

    @mcp.tool(description=TOOL_DESCRIPTIONS["generate_c_math_utils_header"])
    def generate_c_math_utils_header(path: str, prefix: str = "acu", overwrite: bool = False) -> dict:
        return generate_c_math_utils_header_impl(path, prefix=prefix, overwrite=overwrite)

    @mcp.tool(description=TOOL_DESCRIPTIONS["generate_c_build_files"])
    def generate_c_build_files(
        root: str,
        project_name: str = "c_app",
        executable_name: str | None = None,
        source_files: list[str] | None = None,
        c_standard: str = "11",
        overwrite: bool = False,
        include_cmake: bool = True,
        include_makefile: bool = True,
    ) -> dict:
        return generate_c_build_files_impl(
            root,
            project_name=project_name,
            executable_name=executable_name,
            source_files=source_files,
            c_standard=c_standard,
            overwrite=overwrite,
            include_cmake=include_cmake,
            include_makefile=include_makefile,
        )

    @mcp.tool(description=TOOL_DESCRIPTIONS["format_c_code"])
    def format_c_code(paths: list[str], in_place: bool = False, style: str = "file", recursive: bool = False, max_files: int = 100) -> dict:
        return format_c_code_impl(paths, in_place=in_place, style=style, recursive=recursive, max_files=max_files)
