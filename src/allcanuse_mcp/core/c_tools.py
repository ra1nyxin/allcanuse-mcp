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

    return {
        "ok": True,
        "compiler_order": [name for name, _ in C_COMPILER_CANDIDATES],
        "compilers": compilers,
        "formatters": formatters,
        "build_tools": build_tools,
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


def _basic_c_cleanup(text: str) -> str:
    lines = [line.rstrip() for line in text.splitlines()]
    return "\n".join(lines).rstrip() + "\n"
