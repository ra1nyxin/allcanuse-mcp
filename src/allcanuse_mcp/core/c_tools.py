from __future__ import annotations

import os
import re
import shutil
import tempfile
from pathlib import Path
from typing import Any

from allcanuse_mcp.core.command_runner import run_command


C_SOURCE_EXTENSIONS = {".c", ".h", ".cc", ".cpp", ".cxx", ".hpp", ".hh", ".hxx"}
C_COMPILER_CANDIDATES = (
    ("gcc", ["gcc"]),
    ("clang", ["clang"]),
    ("msvc-cl", ["cl"]),
    ("tcc", ["tcc"]),
    ("zig-cc", ["zig", "cc"]),
)
RISKY_C_CALLS: dict[str, dict[str, str]] = {
    "gets": {"severity": "high", "reason": "unbounded input into caller-provided buffer"},
    "strcpy": {"severity": "high", "reason": "unbounded string copy"},
    "strcat": {"severity": "high", "reason": "unbounded string concatenation"},
    "sprintf": {"severity": "high", "reason": "unbounded formatted output"},
    "vsprintf": {"severity": "high", "reason": "unbounded formatted output"},
    "scanf": {"severity": "medium", "reason": "scanf can overflow buffers when %s/%[ widths are missing"},
    "sscanf": {"severity": "medium", "reason": "sscanf can overflow buffers when %s/%[ widths are missing"},
    "fscanf": {"severity": "medium", "reason": "fscanf can overflow buffers when %s/%[ widths are missing"},
    "memcpy": {"severity": "low", "reason": "memory copy requires validated bounds"},
    "memmove": {"severity": "low", "reason": "memory move requires validated bounds"},
    "malloc": {"severity": "low", "reason": "allocation result and ownership need review"},
    "calloc": {"severity": "low", "reason": "allocation result and ownership need review"},
    "realloc": {"severity": "medium", "reason": "realloc can leak the original pointer when assigned directly"},
    "system": {"severity": "high", "reason": "shell execution can introduce command injection"},
    "popen": {"severity": "high", "reason": "shell execution can introduce command injection"},
}
_BASE_MATH_FUNCTION_NAMES = {
    "acos",
    "asin",
    "atan",
    "atan2",
    "ceil",
    "copysign",
    "cos",
    "cosh",
    "exp",
    "fabs",
    "floor",
    "fma",
    "fmax",
    "fmin",
    "fmod",
    "hypot",
    "isfinite",
    "isinf",
    "isnan",
    "log",
    "log10",
    "nearbyint",
    "pow",
    "remainder",
    "round",
    "sin",
    "sinh",
    "sqrt",
    "tan",
    "tanh",
    "trunc",
}
MATH_FUNCTION_NAMES = _BASE_MATH_FUNCTION_NAMES | {f"{name}{suffix}" for name in _BASE_MATH_FUNCTION_NAMES for suffix in ("f", "l")}
_INCLUDE_RE = re.compile(r'^\s*#\s*include\s*([<"])([^>"]+)[>"]', re.MULTILINE)
_DEFINE_RE = re.compile(r"^\s*#\s*define\s+([A-Za-z_]\w*)(?:\s+(.*))?$", re.MULTILINE)
_FUNCTION_RE = re.compile(
    r"^\s*(?:static\s+|extern\s+|inline\s+|__inline\s+|__declspec\([^)]+\)\s+)*"
    r"([A-Za-z_][\w\s\*\(\),]*?)\s+([A-Za-z_]\w*)\s*\(([^;{}]*)\)\s*(\{|;)",
    re.MULTILINE,
)


def detect_c_toolchains() -> dict[str, Any]:
    compilers = []
    for name, command in C_COMPILER_CANDIDATES:
        executable = shutil.which(command[0])
        item: dict[str, Any] = {
            "name": name,
            "available": executable is not None,
            "command": command,
            "executable": executable,
        }
        if executable is not None:
            item["version"] = _read_tool_version([executable, *command[1:]])
        compilers.append(item)

    formatters = []
    for name in ("clang-format", "astyle", "uncrustify"):
        executable = shutil.which(name)
        formatters.append({"name": name, "available": executable is not None, "executable": executable})

    build_tools = []
    for name in ("make", "nmake", "cmake", "ninja"):
        executable = shutil.which(name)
        build_tools.append({"name": name, "available": executable is not None, "executable": executable})

    analyzers = []
    for name in ("clang-tidy", "cppcheck", "include-what-you-use"):
        executable = shutil.which(name)
        analyzers.append({"name": name, "available": executable is not None, "executable": executable})

    return {
        "ok": True,
        "compiler_order": [name for name, _ in C_COMPILER_CANDIDATES],
        "compilers": compilers,
        "formatters": formatters,
        "build_tools": build_tools,
        "analyzers": analyzers,
        "preferred_compiler": next((item["name"] for item in compilers if item["available"]), None),
    }


def compile_c_program(
    source_files: list[str],
    *,
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
) -> dict[str, Any]:
    if not source_files:
        raise ValueError("source_files must contain at least one C source file")

    working_dir = Path(cwd).expanduser().resolve() if cwd else Path.cwd()
    sources = [_resolve_source_path(item, working_dir) for item in source_files]
    missing = [str(path) for path in sources if not path.exists()]
    if missing:
        return {"ok": False, "error": "Some source files do not exist.", "missing": missing}
    c_standard = _normalize_c_standard(c_standard)

    output = Path(output_path).expanduser() if output_path else working_dir / _default_output_name(sources[0])
    if not output.is_absolute():
        output = working_dir / output
    output.parent.mkdir(parents=True, exist_ok=True)

    attempts: list[dict[str, Any]] = []
    for compiler in _ordered_compilers(preferred_compiler):
        executable = shutil.which(compiler["command"][0])
        if executable is None:
            attempts.append({"backend": compiler["name"], "ok": False, "error": "compiler executable was not found"})
            continue
        command = _build_compile_command(
            compiler["name"],
            [executable, *compiler["command"][1:]],
            sources=sources,
            output=output,
            include_dirs=include_dirs or [],
            library_dirs=library_dirs or [],
            libraries=libraries or [],
            c_standard=c_standard,
            extra_args=extra_args or [],
        )
        result = run_command(command, cwd=str(working_dir), timeout_ms=timeout_ms, max_output_chars=40_000)
        attempts.append(
            {
                "backend": compiler["name"],
                "ok": result.get("ok", False),
                "command": command,
                "returncode": result.get("returncode"),
                "stdout": result.get("stdout", ""),
                "stderr": result.get("stderr", ""),
            }
        )
        if not result.get("ok"):
            continue
        run_result = None
        if run_after_compile:
            run_result = run_command([str(output), *(run_args or [])], cwd=str(working_dir), timeout_ms=timeout_ms, max_output_chars=40_000)
        return {
            "ok": True,
            "backend": compiler["name"],
            "output_path": str(output),
            "attempts": attempts,
            "run_result": run_result,
        }

    return {
        "ok": False,
        "error": "No C compiler backend succeeded.",
        "output_path": str(output),
        "attempts": attempts,
    }


def check_c_syntax(
    source_files: list[str],
    *,
    include_dirs: list[str] | None = None,
    c_standard: str = "c11",
    extra_args: list[str] | None = None,
    cwd: str | None = None,
    preferred_compiler: str | None = None,
    timeout_ms: int = 120_000,
) -> dict[str, Any]:
    if not source_files:
        raise ValueError("source_files must contain at least one C source file")
    working_dir = Path(cwd).expanduser().resolve() if cwd else Path.cwd()
    sources = [_resolve_source_path(item, working_dir) for item in source_files]
    missing = [str(path) for path in sources if not path.exists()]
    if missing:
        return {"ok": False, "error": "Some source files do not exist.", "missing": missing}
    c_standard = _normalize_c_standard(c_standard)

    attempts: list[dict[str, Any]] = []
    for compiler in _ordered_compilers(preferred_compiler):
        executable = shutil.which(compiler["command"][0])
        if executable is None:
            attempts.append({"backend": compiler["name"], "ok": False, "error": "compiler executable was not found"})
            continue
        command = _build_syntax_command(
            compiler["name"],
            [executable, *compiler["command"][1:]],
            sources=sources,
            include_dirs=include_dirs or [],
            c_standard=c_standard,
            extra_args=extra_args or [],
        )
        result = run_command(command, cwd=str(working_dir), timeout_ms=timeout_ms, max_output_chars=40_000)
        attempts.append(
            {
                "backend": compiler["name"],
                "ok": result.get("ok", False),
                "command": command,
                "returncode": result.get("returncode"),
                "stdout": result.get("stdout", ""),
                "stderr": result.get("stderr", ""),
            }
        )
        if result.get("ok"):
            return {"ok": True, "backend": compiler["name"], "attempts": attempts}
    return {"ok": False, "error": "No C syntax-check backend succeeded.", "attempts": attempts}


def preprocess_c_source(
    source_file: str,
    *,
    include_dirs: list[str] | None = None,
    defines: dict[str, str | int | None] | None = None,
    undefines: list[str] | None = None,
    c_standard: str = "c11",
    cwd: str | None = None,
    preferred_compiler: str | None = None,
    timeout_ms: int = 120_000,
    max_output_chars: int = 80_000,
) -> dict[str, Any]:
    working_dir = Path(cwd).expanduser().resolve() if cwd else Path.cwd()
    source = _resolve_source_path(source_file, working_dir)
    if not source.exists():
        return {"ok": False, "error": f"Source file does not exist: {source}"}
    c_standard = _normalize_c_standard(c_standard)

    attempts: list[dict[str, Any]] = []
    for compiler in _ordered_compilers(preferred_compiler):
        executable = shutil.which(compiler["command"][0])
        if executable is None:
            attempts.append({"backend": compiler["name"], "ok": False, "error": "compiler executable was not found"})
            continue
        command = _build_preprocess_command(
            compiler["name"],
            [executable, *compiler["command"][1:]],
            source=source,
            include_dirs=include_dirs or [],
            defines=defines or {},
            undefines=undefines or [],
            c_standard=c_standard,
        )
        result = run_command(command, cwd=str(working_dir), timeout_ms=timeout_ms, max_output_chars=max_output_chars)
        attempts.append(
            {
                "backend": compiler["name"],
                "ok": result.get("ok", False),
                "command": command,
                "returncode": result.get("returncode"),
                "stderr": result.get("stderr", ""),
            }
        )
        if result.get("ok"):
            return {
                "ok": True,
                "backend": compiler["name"],
                "source_file": str(source),
                "preprocessed_source": result.get("stdout", ""),
                "stdout_truncated": result.get("stdout_truncated", False),
                "attempts": attempts,
            }
    return {"ok": False, "error": "No C preprocessor backend succeeded.", "source_file": str(source), "attempts": attempts}


def inspect_c_source(paths: list[str], *, recursive: bool = True, max_files: int = 200) -> dict[str, Any]:
    source_paths = _iter_c_paths(paths, recursive=recursive, max_files=max_files)
    files = []
    totals = {"files": 0, "includes": 0, "defines": 0, "functions": 0}
    for path in source_paths:
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            files.append({"path": str(path), "ok": False, "error": str(exc)})
            continue
        includes = _parse_includes(text)
        defines = _parse_defines(text)
        functions = _parse_functions(_strip_comments(text))
        item = {
            "path": str(path),
            "ok": True,
            "line_count": text.count("\n") + (1 if text else 0),
            "includes": includes,
            "defines": defines,
            "functions": functions,
        }
        files.append(item)
        totals["files"] += 1
        totals["includes"] += len(includes)
        totals["defines"] += len(defines)
        totals["functions"] += len(functions)
    return {"ok": True, "count": len(files), "totals": totals, "files": files}


def scan_c_memory_risks(paths: list[str], *, recursive: bool = True, max_files: int = 200, max_results: int = 500) -> dict[str, Any]:
    source_paths = _iter_c_paths(paths, recursive=recursive, max_files=max_files)
    findings = []
    for path in source_paths:
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        stripped = _strip_comments(text)
        for line_number, line in enumerate(stripped.splitlines(), start=1):
            for call_name, metadata in RISKY_C_CALLS.items():
                if not re.search(rf"\b{re.escape(call_name)}\s*\(", line):
                    continue
                if call_name in {"scanf", "sscanf", "fscanf"} and not _scanf_looks_unbounded(line):
                    continue
                findings.append(
                    {
                        "path": str(path),
                        "line_number": line_number,
                        "symbol": call_name,
                        "severity": metadata["severity"],
                        "reason": metadata["reason"],
                        "excerpt": line.strip()[:240],
                    }
                )
                if len(findings) >= max_results:
                    return _memory_risk_result(findings, truncated=True)
    return _memory_risk_result(findings, truncated=False)


def scan_c_numeric_risks(paths: list[str], *, recursive: bool = True, max_files: int = 200, max_results: int = 500) -> dict[str, Any]:
    source_paths = _iter_c_paths(paths, recursive=recursive, max_files=max_files)
    findings = []
    for path in source_paths:
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        stripped = _strip_comments(text)
        includes = {item["name"] for item in _parse_includes(stripped)}
        has_math_h = "math.h" in includes
        for line_number, line in enumerate(stripped.splitlines(), start=1):
            findings.extend(_numeric_findings_for_line(path, line_number, line, has_math_h=has_math_h))
            if len(findings) >= max_results:
                return _numeric_risk_result(findings[:max_results], truncated=True)
    return _numeric_risk_result(findings, truncated=False)


def evaluate_c_math_expression(
    expression: str,
    *,
    variables: dict[str, float | int] | None = None,
    c_standard: str = "c11",
    preferred_compiler: str | None = None,
    timeout_ms: int = 120_000,
) -> dict[str, Any]:
    if not expression.strip():
        raise ValueError("expression must not be empty")
    variables = variables or {}
    invalid_names = [name for name in variables if not re.fullmatch(r"[A-Za-z_]\w*", name)]
    if invalid_names:
        return {"ok": False, "error": "Invalid C identifier in variables.", "invalid_names": invalid_names}

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        source = root / "math_expr.c"
        output = root / _default_output_name(source)
        source.write_text(_render_math_expression_source(expression, variables), encoding="utf-8")
        link_attempts = []
        for label, libraries in (("libm", ["m"]), ("default", [])):
            result = compile_c_program(
                [str(source)],
                output_path=str(output),
                libraries=libraries,
                c_standard=c_standard,
                cwd=str(root),
                preferred_compiler=preferred_compiler,
                timeout_ms=timeout_ms,
                run_after_compile=True,
            )
            link_attempts.append({"backend": label, "ok": result.get("ok", False), "compile_attempts": result.get("attempts", [])})
            if not result.get("ok"):
                continue
            run_result = result.get("run_result") or {}
            if not run_result.get("ok"):
                link_attempts[-1]["run_result"] = run_result
                continue
            stdout = (run_result.get("stdout") or "").strip()
            try:
                value = float(stdout.splitlines()[-1])
            except (IndexError, ValueError):
                value = None
            return {
                "ok": True,
                "backend": result.get("backend"),
                "link_backend": label,
                "expression": expression,
                "variables": variables,
                "value": value,
                "stdout": stdout,
                "attempts": link_attempts,
            }
    return {"ok": False, "error": "No C math expression backend succeeded.", "expression": expression, "attempts": link_attempts}


def generate_c_numeric_test_harness(
    path: str,
    *,
    function_name: str,
    cases: list[dict[str, Any]],
    include_path: str | None = None,
    tolerance: float = 1e-9,
    overwrite: bool = False,
) -> dict[str, Any]:
    if not re.fullmatch(r"[A-Za-z_]\w*", function_name):
        return {"ok": False, "error": "function_name must be a valid C identifier."}
    if not cases:
        return {"ok": False, "error": "cases must contain at least one numeric test case."}
    target = Path(path).expanduser().resolve()
    if target.exists() and not overwrite:
        return {"ok": False, "error": f"File already exists: {target}", "path": str(target)}
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        text = _render_numeric_test_harness(function_name=function_name, cases=cases, include_path=include_path, tolerance=tolerance)
    except ValueError as exc:
        return {"ok": False, "error": str(exc), "path": str(target)}
    target.write_text(text, encoding="utf-8")
    return {"ok": True, "path": str(target), "case_count": len(cases), "bytes": len(text.encode("utf-8"))}


def generate_c_math_utils_header(path: str, *, prefix: str = "acu", overwrite: bool = False) -> dict[str, Any]:
    if not re.fullmatch(r"[A-Za-z_]\w*", prefix):
        return {"ok": False, "error": "prefix must be a valid C identifier prefix."}
    target = Path(path).expanduser().resolve()
    if target.exists() and not overwrite:
        return {"ok": False, "error": f"File already exists: {target}", "path": str(target)}
    target.parent.mkdir(parents=True, exist_ok=True)
    text = _render_math_utils_header(prefix)
    target.write_text(text, encoding="utf-8")
    return {"ok": True, "path": str(target), "prefix": prefix, "bytes": len(text.encode("utf-8"))}


def generate_c_build_files(
    root: str,
    *,
    project_name: str = "c_app",
    executable_name: str | None = None,
    source_files: list[str] | None = None,
    c_standard: str = "11",
    overwrite: bool = False,
    include_cmake: bool = True,
    include_makefile: bool = True,
) -> dict[str, Any]:
    root_path = Path(root).expanduser().resolve()
    root_path.mkdir(parents=True, exist_ok=True)
    c_standard = _normalize_c_standard(c_standard)
    sources = source_files or [str(path.relative_to(root_path)) for path in _iter_c_paths([str(root_path)], recursive=False, max_files=100) if path.suffix.lower() == ".c"]
    if not sources:
        sources = ["main.c"]
    executable = executable_name or project_name
    generated = []
    skipped = []

    if include_cmake:
        cmake_path = root_path / "CMakeLists.txt"
        cmake_text = _render_cmake(project_name=project_name, executable_name=executable, source_files=sources, c_standard=c_standard)
        _write_generated_file(cmake_path, cmake_text, overwrite=overwrite, generated=generated, skipped=skipped)

    if include_makefile:
        makefile_path = root_path / "Makefile"
        makefile_text = _render_makefile(executable_name=executable, source_files=sources, c_standard=c_standard)
        _write_generated_file(makefile_path, makefile_text, overwrite=overwrite, generated=generated, skipped=skipped)

    return {
        "ok": True,
        "root": str(root_path),
        "project_name": project_name,
        "executable_name": executable,
        "source_files": sources,
        "generated": generated,
        "skipped": skipped,
    }


def format_c_code(
    paths: list[str],
    *,
    in_place: bool = False,
    style: str = "file",
    recursive: bool = False,
    max_files: int = 100,
) -> dict[str, Any]:
    source_paths = _iter_c_paths(paths, recursive=recursive, max_files=max_files)
    results = []
    clang_format = shutil.which("clang-format")
    for path in source_paths:
        attempts: list[dict[str, Any]] = []
        if clang_format is not None:
            command = [clang_format, f"-style={style}"]
            if in_place:
                command.append("-i")
            command.append(str(path))
            result = run_command(command, timeout_ms=60_000, max_output_chars=40_000)
            attempts.append(
                {
                    "backend": "clang-format",
                    "ok": result.get("ok", False),
                    "command": command,
                    "stdout": result.get("stdout", ""),
                    "stderr": result.get("stderr", ""),
                }
            )
            if result.get("ok"):
                results.append(
                    {
                        "ok": True,
                        "path": str(path),
                        "backend": "clang-format",
                        "formatted_text": None if in_place else result.get("stdout", ""),
                        "attempts": attempts,
                    }
                )
                continue
        else:
            attempts.append({"backend": "clang-format", "ok": False, "error": "clang-format executable was not found"})

        try:
            original = path.read_text(encoding="utf-8", errors="replace")
            formatted = _basic_c_cleanup(original)
            if in_place:
                path.write_text(formatted, encoding="utf-8")
            results.append(
                {
                    "ok": True,
                    "path": str(path),
                    "backend": "basic-cleanup",
                    "formatted_text": None if in_place else formatted,
                    "attempts": attempts + [{"backend": "basic-cleanup", "ok": True}],
                }
            )
        except OSError as exc:
            results.append({"ok": False, "path": str(path), "error": str(exc), "attempts": attempts})
    return {
        "ok": all(item.get("ok") for item in results) if results else True,
        "count": len(results),
        "results": results,
    }


def _read_tool_version(command: list[str]) -> str:
    candidates = [command + ["--version"], command + ["-v"]]
    if Path(command[0]).name.lower() == "cl.exe" or Path(command[0]).name.lower() == "cl":
        candidates = [command]
    for candidate in candidates:
        try:
            result = run_command(candidate, timeout_ms=5_000, max_output_chars=2000)
        except Exception:
            continue
        text = "\n".join(part for part in (result.get("stdout", ""), result.get("stderr", "")) if part).strip()
        if text:
            return text.splitlines()[0]
    return ""


def _resolve_source_path(path: str, working_dir: Path) -> Path:
    candidate = Path(path).expanduser()
    return candidate.resolve() if candidate.is_absolute() else (working_dir / candidate).resolve()


def _default_output_name(source: Path) -> str:
    suffix = ".exe" if os.name == "nt" else ""
    return f"{source.stem}{suffix}"


def _ordered_compilers(preferred_compiler: str | None) -> list[dict[str, Any]]:
    compilers = [{"name": name, "command": command} for name, command in C_COMPILER_CANDIDATES]
    if not preferred_compiler:
        return compilers
    preferred = preferred_compiler.casefold()
    matching = [item for item in compilers if item["name"].casefold() == preferred or item["command"][0].casefold() == preferred]
    remaining = [item for item in compilers if item not in matching]
    if matching:
        return matching + remaining
    return [{"name": preferred_compiler, "command": [preferred_compiler]}] + compilers


def _build_compile_command(
    backend: str,
    compiler_command: list[str],
    *,
    sources: list[Path],
    output: Path,
    include_dirs: list[str],
    library_dirs: list[str],
    libraries: list[str],
    c_standard: str,
    extra_args: list[str],
) -> list[str]:
    if backend == "msvc-cl":
        command = [*compiler_command, "/nologo", "/TC"]
        if c_standard in {"c11", "c17"}:
            command.append(f"/std:{c_standard}")
        command.extend([f"/I{item}" for item in include_dirs])
        command.extend(str(source) for source in sources)
        command.append(f"/Fe:{output}")
        command.extend(extra_args)
        if library_dirs or libraries:
            command.append("/link")
            command.extend(f"/LIBPATH:{item}" for item in library_dirs)
            command.extend(item if item.lower().endswith(".lib") else f"{item}.lib" for item in libraries)
        return command

    command = [*compiler_command]
    if c_standard:
        command.append(f"-std={c_standard}")
    command.extend(str(source) for source in sources)
    command.extend(f"-I{item}" for item in include_dirs)
    command.extend(f"-L{item}" for item in library_dirs)
    command.extend(f"-l{item}" for item in libraries)
    command.extend(extra_args)
    command.extend(["-o", str(output)])
    return command


def _build_syntax_command(
    backend: str,
    compiler_command: list[str],
    *,
    sources: list[Path],
    include_dirs: list[str],
    c_standard: str,
    extra_args: list[str],
) -> list[str]:
    if backend == "msvc-cl":
        command = [*compiler_command, "/nologo", "/TC", "/Zs"]
        if c_standard in {"c11", "c17"}:
            command.append(f"/std:{c_standard}")
        command.extend(f"/I{item}" for item in include_dirs)
        command.extend(str(source) for source in sources)
        command.extend(extra_args)
        return command
    if backend == "tcc":
        command = [*compiler_command, "-c"]
        if len(sources) == 1:
            command.extend([str(sources[0]), "-o", os.devnull])
        else:
            command.extend(str(source) for source in sources)
        command.extend(f"-I{item}" for item in include_dirs)
        command.extend(extra_args)
        return command
    command = [*compiler_command]
    if c_standard:
        command.append(f"-std={c_standard}")
    command.append("-fsyntax-only")
    command.extend(str(source) for source in sources)
    command.extend(f"-I{item}" for item in include_dirs)
    command.extend(extra_args)
    return command


def _build_preprocess_command(
    backend: str,
    compiler_command: list[str],
    *,
    source: Path,
    include_dirs: list[str],
    defines: dict[str, str | int | None],
    undefines: list[str],
    c_standard: str,
) -> list[str]:
    if backend == "msvc-cl":
        command = [*compiler_command, "/nologo", "/TC", "/EP"]
        if c_standard in {"c11", "c17"}:
            command.append(f"/std:{c_standard}")
        command.extend(f"/I{item}" for item in include_dirs)
        command.extend(_msvc_define_arg(name, value) for name, value in defines.items())
        command.extend(f"/U{name}" for name in undefines)
        command.append(str(source))
        return command

    command = [*compiler_command]
    if c_standard:
        command.append(f"-std={c_standard}")
    command.append("-E")
    command.extend(f"-I{item}" for item in include_dirs)
    command.extend(_unix_define_arg(name, value) for name, value in defines.items())
    command.extend(f"-U{name}" for name in undefines)
    command.append(str(source))
    return command


def _unix_define_arg(name: str, value: str | int | None) -> str:
    return f"-D{name}" if value is None else f"-D{name}={value}"


def _msvc_define_arg(name: str, value: str | int | None) -> str:
    return f"/D{name}" if value is None else f"/D{name}={value}"


def _iter_c_paths(paths: list[str], *, recursive: bool, max_files: int) -> list[Path]:
    results: list[Path] = []
    seen: set[str] = set()
    for raw_path in paths:
        path = Path(raw_path).expanduser().resolve()
        if path.is_dir():
            iterator = path.rglob("*") if recursive else path.iterdir()
            candidates = [item for item in iterator if item.is_file() and item.suffix.lower() in C_SOURCE_EXTENSIONS]
        else:
            candidates = [path]
        for candidate in candidates:
            key = str(candidate).casefold()
            if key in seen:
                continue
            seen.add(key)
            results.append(candidate)
            if len(results) >= max_files:
                return results
    return results


def _parse_includes(text: str) -> list[dict[str, Any]]:
    return [
        {"name": match.group(2), "kind": "system" if match.group(1) == "<" else "local"}
        for match in _INCLUDE_RE.finditer(text)
    ]


def _parse_defines(text: str) -> list[dict[str, Any]]:
    return [{"name": match.group(1), "value": (match.group(2) or "").strip()} for match in _DEFINE_RE.finditer(text)]


def _parse_functions(text: str) -> list[dict[str, Any]]:
    functions = []
    for match in _FUNCTION_RE.finditer(text):
        name = match.group(2)
        if name in {"if", "for", "while", "switch", "return"}:
            continue
        functions.append(
            {
                "name": name,
                "return_type": " ".join(match.group(1).split()),
                "parameters": " ".join(match.group(3).split()),
                "kind": "definition" if match.group(4) == "{" else "declaration",
            }
        )
    return functions


def _strip_comments(text: str) -> str:
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.DOTALL)
    return re.sub(r"//.*", "", text)


def _scanf_looks_unbounded(line: str) -> bool:
    match = re.search(r'"([^"]*)"', line)
    if match is None:
        return True
    format_string = match.group(1)
    for item in re.finditer(r"%(?:\*?)(?P<width>\d+)?(?:\.\d+)?[hlLjzt]*?(?P<spec>s|\[[^\]]*\])", format_string):
        if item.group("width") is None:
            return True
    return False


def _memory_risk_result(findings: list[dict[str, Any]], *, truncated: bool) -> dict[str, Any]:
    summary = {
        "high": sum(1 for item in findings if item["severity"] == "high"),
        "medium": sum(1 for item in findings if item["severity"] == "medium"),
        "low": sum(1 for item in findings if item["severity"] == "low"),
    }
    return {"ok": True, "count": len(findings), "summary": summary, "truncated": truncated, "findings": findings}


def _numeric_findings_for_line(path: Path, line_number: int, line: str, *, has_math_h: bool) -> list[dict[str, Any]]:
    findings = []
    stripped = line.strip()
    if not stripped:
        return findings
    if re.search(r"\b(float|double|long\s+double)\b[^;=]*==", stripped) or re.search(r"==[^;]*\b(float|double|long\s+double)\b", stripped):
        findings.append(_numeric_finding(path, line_number, "float_equality", "medium", "direct equality on floating-point values is often unstable", stripped))
    if re.search(r"\b(?:float|double|long\s+double)\s+\w+\s*=\s*[^;]*\b\d+\s*/\s*\d+\b", stripped):
        findings.append(_numeric_finding(path, line_number, "integer_division_assigned_to_float", "high", "integer division occurs before conversion to floating point", stripped))
    if re.search(r"\bpow[fl]?\s*\([^,]+,\s*2(?:\.0+)?[fFlL]?\s*\)", stripped):
        findings.append(_numeric_finding(path, line_number, "pow_square", "low", "x * x is usually clearer and faster than pow(x, 2)", stripped))
    if re.search(r"\babs\s*\(", stripped):
        findings.append(_numeric_finding(path, line_number, "abs_on_possible_float", "medium", "use fabs/fabsf/fabsl for floating-point absolute values", stripped))
    if re.search(r"\bM_PI\b", stripped):
        findings.append(_numeric_finding(path, line_number, "nonportable_m_pi", "low", "M_PI is not guaranteed by the C standard on every toolchain", stripped))
    if not has_math_h and any(re.search(rf"\b{name}\s*\(", stripped) for name in MATH_FUNCTION_NAMES):
        findings.append(_numeric_finding(path, line_number, "math_function_linkage", "low", "math functions may require #include <math.h> and libm on Unix-like toolchains", stripped))
    return findings


def _numeric_finding(path: Path, line_number: int, code: str, severity: str, reason: str, excerpt: str) -> dict[str, Any]:
    return {"path": str(path), "line_number": line_number, "code": code, "severity": severity, "reason": reason, "excerpt": excerpt[:240]}


def _numeric_risk_result(findings: list[dict[str, Any]], *, truncated: bool) -> dict[str, Any]:
    summary = {
        "high": sum(1 for item in findings if item["severity"] == "high"),
        "medium": sum(1 for item in findings if item["severity"] == "medium"),
        "low": sum(1 for item in findings if item["severity"] == "low"),
    }
    return {"ok": True, "count": len(findings), "summary": summary, "truncated": truncated, "findings": findings}


def _render_math_expression_source(expression: str, variables: dict[str, float | int]) -> str:
    declarations = "\n".join(f"    const double {name} = {float(value):.17g};" for name, value in variables.items())
    return (
        "#include <math.h>\n"
        "#include <stdio.h>\n\n"
        "int main(void) {\n"
        f"{declarations}\n"
        f"    const double result = (double)({expression});\n"
        "    printf(\"%.17g\\n\", result);\n"
        "    return 0;\n"
        "}\n"
    )


def _render_numeric_test_harness(*, function_name: str, cases: list[dict[str, Any]], include_path: str | None, tolerance: float) -> str:
    include = f'#include "{include_path}"\n' if include_path else f"/* Include the declaration for {function_name} before compiling this test. */\n"
    checks = []
    for index, case in enumerate(cases, start=1):
        args = case.get("args", [])
        expected = case.get("expected")
        if not isinstance(args, list) or expected is None:
            raise ValueError("Each case must include args (list) and expected")
        arg_text = ", ".join(f"{float(value):.17g}" for value in args)
        checks.append(
            f"    actual = {function_name}({arg_text});\n"
            f"    expected = {float(expected):.17g};\n"
            f"    if (fabs(actual - expected) > tolerance) {{\n"
            f"        fprintf(stderr, \"case {index} failed: expected %.17g got %.17g\\n\", expected, actual);\n"
            f"        failures++;\n"
            f"    }}\n"
        )
    return (
        "#include <math.h>\n"
        "#include <stdio.h>\n"
        f"{include}\n"
        "int main(void) {\n"
        f"    const double tolerance = {float(tolerance):.17g};\n"
        "    int failures = 0;\n"
        "    double actual = 0.0;\n"
        "    double expected = 0.0;\n"
        f"{''.join(checks)}"
        "    if (failures == 0) {\n"
        "        puts(\"all numeric cases passed\");\n"
        "    }\n"
        "    return failures ? 1 : 0;\n"
        "}\n"
    )


def _render_math_utils_header(prefix: str) -> str:
    guard = f"{prefix.upper()}_MATH_UTILS_H"
    return (
        f"#ifndef {guard}\n"
        f"#define {guard}\n\n"
        "#include <float.h>\n"
        "#include <math.h>\n\n"
        f"static inline double {prefix}_clamp(double value, double low, double high) {{\n"
        "    return value < low ? low : (value > high ? high : value);\n"
        "}\n\n"
        f"static inline double {prefix}_lerp(double a, double b, double t) {{\n"
        "    return a + (b - a) * t;\n"
        "}\n\n"
        f"static inline int {prefix}_nearly_equal(double a, double b, double rel_tol, double abs_tol) {{\n"
        "    const double diff = fabs(a - b);\n"
        "    const double scale = fmax(fabs(a), fabs(b));\n"
        "    return diff <= fmax(abs_tol, rel_tol * scale);\n"
        "}\n\n"
        f"static inline double {prefix}_deg_to_rad(double degrees) {{\n"
        "    return degrees * 0.017453292519943295769;\n"
        "}\n\n"
        f"static inline double {prefix}_rad_to_deg(double radians) {{\n"
        "    return radians * 57.295779513082320876;\n"
        "}\n\n"
        f"#endif /* {guard} */\n"
    )


def _render_cmake(*, project_name: str, executable_name: str, source_files: list[str], c_standard: str) -> str:
    sources = "\n    ".join(source_files)
    cmake_standard = c_standard[1:] if c_standard.startswith("c") and c_standard[1:].isdigit() else c_standard
    return (
        "cmake_minimum_required(VERSION 3.16)\n"
        f"project({project_name} C)\n\n"
        f"set(CMAKE_C_STANDARD {cmake_standard})\n"
        "set(CMAKE_C_STANDARD_REQUIRED ON)\n\n"
        f"add_executable({executable_name}\n    {sources}\n)\n"
    )


def _render_makefile(*, executable_name: str, source_files: list[str], c_standard: str) -> str:
    sources = " ".join(source_files)
    if c_standard.startswith("gnu") or c_standard.startswith("iso"):
        flag_standard = c_standard
    elif c_standard.startswith("c") and c_standard[1:].isdigit():
        flag_standard = c_standard
    else:
        flag_standard = f"c{c_standard}" if c_standard.isdigit() else c_standard
    return (
        "CC ?= cc\n"
        f"CFLAGS ?= -std={flag_standard} -Wall -Wextra -O2\n\n"
        f"TARGET := {executable_name}\n"
        f"SRCS := {sources}\n"
        "OBJS := $(SRCS:.c=.o)\n\n"
        "all: $(TARGET)\n\n"
        "$(TARGET): $(OBJS)\n"
        "\t$(CC) $(OBJS) -o $@\n\n"
        "%.o: %.c\n"
        "\t$(CC) $(CFLAGS) -c $< -o $@\n\n"
        "clean:\n"
        "\trm -f $(TARGET) $(OBJS)\n"
    )


def _write_generated_file(path: Path, text: str, *, overwrite: bool, generated: list[dict[str, Any]], skipped: list[dict[str, Any]]) -> None:
    if path.exists() and not overwrite:
        skipped.append({"path": str(path), "reason": "file already exists"})
        return
    path.write_text(text, encoding="utf-8")
    generated.append({"path": str(path), "bytes": len(text.encode("utf-8"))})


def _basic_c_cleanup(text: str) -> str:
    lines = [line.rstrip() for line in text.splitlines()]
    return "\n".join(lines).rstrip() + "\n"


def _normalize_c_standard(c_standard: str) -> str:
    value = (c_standard or "").strip().lower()
    if not value:
        return "c11"
    if value.startswith("gnu") or value.startswith("iso"):
        return value
    if value.startswith("c") and value[1:].isdigit():
        return value
    if value.isdigit():
        return f"c{value}"
    return value
