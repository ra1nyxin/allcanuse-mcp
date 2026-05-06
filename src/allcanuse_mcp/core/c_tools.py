from __future__ import annotations

import os
import re
import shutil
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
