from __future__ import annotations

import os
import fnmatch
import hashlib
import re
import shutil
import tarfile
import zipfile
import base64
from pathlib import Path
from typing import Any


def build_tree(
    root: str,
    *,
    max_depth: int,
    max_entries: int,
    include_files: bool,
    include_dirs: bool,
    show_hidden: bool,
) -> dict[str, Any]:
    root_path = Path(root).expanduser().resolve()
    if not root_path.exists():
        raise FileNotFoundError(f"Path does not exist: {root_path}")

    entries: list[dict[str, Any]] = []
    truncated = False

    def walk(current: Path, depth: int) -> None:
        nonlocal truncated
        if truncated or depth > max_depth:
            return

        try:
            children = sorted(current.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower()))
        except PermissionError:
            entries.append(
                {
                    "path": str(current),
                    "relative_path": str(current.relative_to(root_path)),
                    "type": "error",
                    "error": "permission_denied",
                }
            )
            return

        for child in children:
            if len(entries) >= max_entries:
                truncated = True
                return
            if not show_hidden and child.name.startswith("."):
                continue
            item_type = "dir" if child.is_dir() else "file"
            if (item_type == "dir" and include_dirs) or (item_type == "file" and include_files):
                info: dict[str, Any] = {
                    "path": str(child),
                    "relative_path": str(child.relative_to(root_path)),
                    "type": item_type,
                    "depth": depth,
                }
                if child.is_file():
                    try:
                        info["size"] = child.stat().st_size
                    except OSError:
                        info["size"] = None
                entries.append(info)
            if child.is_dir():
                walk(child, depth + 1)

    if root_path.is_file():
        entries.append(
            {
                "path": str(root_path),
                "relative_path": root_path.name,
                "type": "file",
                "depth": 0,
                "size": root_path.stat().st_size,
            }
        )
    else:
        walk(root_path, 1)

    return {
        "root": str(root_path),
        "exists": True,
        "is_dir": root_path.is_dir(),
        "entry_count": len(entries),
        "truncated": truncated,
        "entries": entries,
    }


def read_text_file(
    path: str,
    *,
    encoding: str = "utf-8",
    start_line: int | None = None,
    end_line: int | None = None,
) -> dict[str, Any]:
    file_path = Path(path).expanduser().resolve()
    text = file_path.read_text(encoding=encoding)
    lines = text.splitlines()
    total_lines = len(lines)

    if start_line is None and end_line is None:
        content = text
        selected_start = 1 if total_lines else 0
        selected_end = total_lines
    else:
        start = max((start_line or 1) - 1, 0)
        end = min(end_line or total_lines, total_lines)
        content = "\n".join(lines[start:end])
        if end < total_lines and content:
            content += "\n"
        selected_start = start + 1 if total_lines else 0
        selected_end = end

    return {
        "path": str(file_path),
        "encoding": encoding,
        "total_lines": total_lines,
        "start_line": selected_start,
        "end_line": selected_end,
        "content": content,
    }


def write_text_file(
    path: str,
    content: str,
    *,
    encoding: str = "utf-8",
    mode: str = "overwrite",
    create_dirs: bool = True,
) -> dict[str, Any]:
    file_path = Path(path).expanduser().resolve()
    if create_dirs:
        file_path.parent.mkdir(parents=True, exist_ok=True)

    if mode == "append":
        with file_path.open("a", encoding=encoding) as handle:
            handle.write(content)
    else:
        file_path.write_text(content, encoding=encoding)

    return {
        "path": str(file_path),
        "encoding": encoding,
        "mode": mode,
        "bytes_written": len(content.encode(encoding, errors="replace")),
    }


def patch_lines_in_file(
    path: str,
    *,
    start_line: int,
    end_line: int,
    new_text: str,
    encoding: str = "utf-8",
) -> dict[str, Any]:
    file_path = Path(path).expanduser().resolve()
    text = file_path.read_text(encoding=encoding)
    lines = text.splitlines(keepends=True)
    total_lines = len(lines)
    if start_line < 1 or end_line < start_line:
        raise ValueError("Invalid line range.")

    start_index = start_line - 1
    end_index = min(end_line, total_lines)
    replacement = new_text.splitlines(keepends=True)
    if new_text and not replacement:
        replacement = [new_text]
    lines[start_index:end_index] = replacement
    file_path.write_text("".join(lines), encoding=encoding)
    return {
        "path": str(file_path),
        "encoding": encoding,
        "start_line": start_line,
        "end_line": end_line,
        "new_line_count": len(replacement),
    }


def replace_text_in_file(
    path: str,
    *,
    old_text: str,
    new_text: str,
    count: int = 0,
    encoding: str = "utf-8",
) -> dict[str, Any]:
    file_path = Path(path).expanduser().resolve()
    original = file_path.read_text(encoding=encoding)
    replaced = original.replace(old_text, new_text, count or -1)
    replacements = original.count(old_text) if count == 0 else min(original.count(old_text), count)
    file_path.write_text(replaced, encoding=encoding)
    return {
        "path": str(file_path),
        "encoding": encoding,
        "replacements": replacements,
    }


def mkdir_path(path: str, *, parents: bool = True, exist_ok: bool = True) -> dict[str, Any]:
    target = Path(path).expanduser().resolve()
    existed_before = target.exists()
    target.mkdir(parents=parents, exist_ok=exist_ok)
    return {
        "path": str(target),
        "created": not existed_before,
        "exists": target.exists(),
        "is_dir": target.is_dir(),
    }


def move_path(source: str, destination: str, *, overwrite: bool = False) -> dict[str, Any]:
    src = Path(source).expanduser().resolve()
    dst = Path(destination).expanduser().resolve()
    if not src.exists():
        raise FileNotFoundError(f"Source does not exist: {src}")

    if dst.exists():
        if not overwrite:
            raise FileExistsError(f"Destination already exists: {dst}")
        if dst.is_dir() and not src.is_dir():
            raise IsADirectoryError(f"Destination is a directory: {dst}")
        if dst.is_dir():
            shutil.rmtree(dst)
        else:
            dst.unlink()

    dst.parent.mkdir(parents=True, exist_ok=True)
    final_path = Path(shutil.move(str(src), str(dst))).resolve()
    return {
        "source": str(src),
        "destination": str(final_path),
        "exists": final_path.exists(),
        "is_dir": final_path.is_dir(),
    }


def delete_path(path: str, *, recursive: bool = False, missing_ok: bool = False) -> dict[str, Any]:
    target = Path(path).expanduser().resolve()
    if not target.exists():
        if missing_ok:
            return {"path": str(target), "deleted": False, "missing": True}
        raise FileNotFoundError(f"Path does not exist: {target}")

    is_symlink = target.is_symlink()
    path_type = "symlink" if is_symlink else ("dir" if target.is_dir() else "file")
    if target.is_dir() and not is_symlink:
        if recursive:
            shutil.rmtree(target)
        else:
            target.rmdir()
    else:
        target.unlink()

    return {
        "path": str(target),
        "deleted": True,
        "type": path_type,
        "recursive": recursive,
    }


def zip_paths(
    paths: list[str],
    destination: str,
    *,
    archive_type: str = "zip",
) -> dict[str, Any]:
    if not paths:
        raise ValueError("At least one path is required.")

    resolved_paths = [Path(item).expanduser().resolve() for item in paths]
    for item in resolved_paths:
        if not item.exists():
            raise FileNotFoundError(f"Path does not exist: {item}")

    destination_path = Path(destination).expanduser().resolve()
    destination_path.parent.mkdir(parents=True, exist_ok=True)

    if archive_type == "zip":
        with zipfile.ZipFile(destination_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for item in resolved_paths:
                _write_to_zip(archive, item)
    elif archive_type in {"tar", "tar.gz"}:
        mode = "w:gz" if archive_type == "tar.gz" else "w"
        with tarfile.open(destination_path, mode) as archive:
            for item in resolved_paths:
                archive.add(item, arcname=item.name)
    else:
        raise ValueError("archive_type must be zip, tar, or tar.gz")

    return {
        "destination": str(destination_path),
        "archive_type": archive_type,
        "path_count": len(resolved_paths),
        "file_size": destination_path.stat().st_size,
    }


def extract_archive(
    archive_path: str,
    destination_dir: str,
    *,
    overwrite: bool = False,
) -> dict[str, Any]:
    archive = Path(archive_path).expanduser().resolve()
    if not archive.exists():
        raise FileNotFoundError(f"Archive does not exist: {archive}")

    destination = Path(destination_dir).expanduser().resolve()
    if destination.exists() and any(destination.iterdir()) and not overwrite:
        raise FileExistsError(f"Destination is not empty: {destination}")
    destination.mkdir(parents=True, exist_ok=True)

    suffixes = archive.suffixes
    if archive.suffix.lower() == ".zip":
        with zipfile.ZipFile(archive, "r") as handle:
            handle.extractall(destination)
    elif suffixes[-2:] == [".tar", ".gz"] or archive.suffix.lower() == ".tar":
        with tarfile.open(archive, "r:*") as handle:
            handle.extractall(destination)
    else:
        raise ValueError("Unsupported archive format.")

    extracted = sum(1 for _ in destination.rglob("*"))
    return {
        "archive": str(archive),
        "destination": str(destination),
        "extracted_entries": extracted,
    }


def list_desktop_files() -> dict[str, Any]:
    candidates = [
        Path.home() / "Desktop",
        Path(os.environ.get("USERPROFILE", "")) / "Desktop",
        Path.home() / "桌面",
    ]
    for candidate in candidates:
        if str(candidate) and candidate.exists():
            return build_tree(
                str(candidate),
                max_depth=2,
                max_entries=200,
                include_files=True,
                include_dirs=True,
                show_hidden=False,
            )
    return {
        "root": None,
        "exists": False,
        "entry_count": 0,
        "entries": [],
        "error": "Desktop directory was not found on this host.",
    }


def find_files(
    root: str,
    *,
    pattern: str = "*",
    max_depth: int = 5,
    max_results: int = 200,
    include_hidden: bool = False,
) -> dict[str, Any]:
    root_path = Path(root).expanduser().resolve()
    if not root_path.exists():
        raise FileNotFoundError(f"Path does not exist: {root_path}")

    matches: list[dict[str, Any]] = []
    truncated = False

    def walk(current: Path, depth: int) -> None:
        nonlocal truncated
        if truncated or depth > max_depth:
            return
        try:
            children = sorted(current.iterdir(), key=lambda p: p.name.lower())
        except PermissionError:
            return

        for child in children:
            if not include_hidden and child.name.startswith("."):
                continue
            if len(matches) >= max_results:
                truncated = True
                return
            if fnmatch.fnmatch(child.name, pattern):
                matches.append(
                    {
                        "path": str(child),
                        "relative_path": str(child.relative_to(root_path)),
                        "is_dir": child.is_dir(),
                        "is_file": child.is_file(),
                    }
                )
            if child.is_dir():
                walk(child, depth + 1)

    if root_path.is_dir():
        walk(root_path, 1)
    elif fnmatch.fnmatch(root_path.name, pattern):
        matches.append(
            {
                "path": str(root_path),
                "relative_path": root_path.name,
                "is_dir": False,
                "is_file": True,
            }
        )

    return {
        "root": str(root_path),
        "pattern": pattern,
        "count": len(matches),
        "truncated": truncated,
        "matches": matches,
    }


def search_text(
    root: str,
    *,
    query: str,
    use_regex: bool = False,
    case_sensitive: bool = False,
    file_pattern: str = "*",
    max_results: int = 200,
    max_file_size_bytes: int = 1_000_000,
    include_hidden: bool = False,
) -> dict[str, Any]:
    root_path = Path(root).expanduser().resolve()
    if not root_path.exists():
        raise FileNotFoundError(f"Path does not exist: {root_path}")

    flags = 0 if case_sensitive else re.IGNORECASE
    matcher = re.compile(query if use_regex else re.escape(query), flags)
    results: list[dict[str, Any]] = []
    truncated = False

    candidate_files = []
    if root_path.is_file():
        candidate_files = [root_path]
    else:
        for file_path in root_path.rglob("*"):
            if not file_path.is_file():
                continue
            if not include_hidden and any(part.startswith(".") for part in file_path.parts):
                continue
            if not fnmatch.fnmatch(file_path.name, file_pattern):
                continue
            candidate_files.append(file_path)

    for file_path in candidate_files:
        if len(results) >= max_results:
            truncated = True
            break
        try:
            if file_path.stat().st_size > max_file_size_bytes:
                continue
            text = file_path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for line_number, line in enumerate(text.splitlines(), start=1):
            if matcher.search(line):
                results.append(
                    {
                        "path": str(file_path),
                        "relative_path": (
                            str(file_path.relative_to(root_path)) if root_path.is_dir() else file_path.name
                        ),
                        "line_number": line_number,
                        "line": line,
                    }
                )
                if len(results) >= max_results:
                    truncated = True
                    break

    return {
        "root": str(root_path),
        "query": query,
        "use_regex": use_regex,
        "case_sensitive": case_sensitive,
        "count": len(results),
        "truncated": truncated,
        "matches": results,
    }


def stat_path(path: str) -> dict[str, Any]:
    target = Path(path).expanduser().resolve()
    if not target.exists() and not target.is_symlink():
        raise FileNotFoundError(f"Path does not exist: {target}")
    stats = target.lstat()
    return {
        "path": str(target),
        "exists": target.exists(),
        "is_file": target.is_file(),
        "is_dir": target.is_dir(),
        "is_symlink": target.is_symlink(),
        "size": stats.st_size,
        "modified_time": stats.st_mtime,
        "created_time": getattr(stats, "st_ctime", None),
        "accessed_time": stats.st_atime,
    }


def copy_path(source: str, destination: str, *, overwrite: bool = False) -> dict[str, Any]:
    src = Path(source).expanduser().resolve()
    dst = Path(destination).expanduser().resolve()
    if not src.exists():
        raise FileNotFoundError(f"Source does not exist: {src}")
    if dst.exists():
        if not overwrite:
            raise FileExistsError(f"Destination already exists: {dst}")
        if dst.is_dir() and not src.is_dir():
            raise IsADirectoryError(f"Destination is a directory: {dst}")
        if dst.is_dir():
            shutil.rmtree(dst)
        else:
            dst.unlink()
    dst.parent.mkdir(parents=True, exist_ok=True)
    if src.is_dir():
        shutil.copytree(src, dst)
    else:
        shutil.copy2(src, dst)
    return {
        "source": str(src),
        "destination": str(dst),
        "exists": dst.exists(),
        "is_dir": dst.is_dir(),
    }


def hash_file(path: str, *, algorithm: str = "sha256", chunk_size: int = 1024 * 1024) -> dict[str, Any]:
    target = Path(path).expanduser().resolve()
    if not target.is_file():
        raise FileNotFoundError(f"File does not exist: {target}")
    try:
        hasher = hashlib.new(algorithm)
    except ValueError as exc:
        raise ValueError(f"Unsupported hash algorithm: {algorithm}") from exc
    with target.open("rb") as handle:
        while True:
            chunk = handle.read(chunk_size)
            if not chunk:
                break
            hasher.update(chunk)
    return {
        "path": str(target),
        "algorithm": algorithm,
        "digest": hasher.hexdigest(),
        "size": target.stat().st_size,
    }


def read_binary_file(path: str, *, offset: int = 0, length: int = 4096, as_base64: bool = True) -> dict[str, Any]:
    target = Path(path).expanduser().resolve()
    if not target.is_file():
        raise FileNotFoundError(f"File does not exist: {target}")
    with target.open("rb") as handle:
        handle.seek(max(0, offset))
        data = handle.read(max(0, length))
    payload = base64.b64encode(data).decode("ascii") if as_base64 else data.hex()
    return {
        "path": str(target),
        "offset": offset,
        "length": len(data),
        "encoding": "base64" if as_base64 else "hex",
        "content": payload,
    }


def write_binary_file(
    path: str,
    content: str,
    *,
    input_encoding: str = "base64",
    mode: str = "overwrite",
    create_dirs: bool = True,
) -> dict[str, Any]:
    target = Path(path).expanduser().resolve()
    if create_dirs:
        target.parent.mkdir(parents=True, exist_ok=True)
    if input_encoding == "base64":
        data = base64.b64decode(content)
    elif input_encoding == "hex":
        data = bytes.fromhex(content)
    else:
        raise ValueError("input_encoding must be base64 or hex")
    file_mode = "ab" if mode == "append" else "wb"
    with target.open(file_mode) as handle:
        handle.write(data)
    return {
        "path": str(target),
        "bytes_written": len(data),
        "mode": mode,
        "input_encoding": input_encoding,
    }


def list_recent_files(root: str, *, limit: int = 50) -> dict[str, Any]:
    root_path = Path(root).expanduser().resolve()
    if not root_path.exists():
        raise FileNotFoundError(f"Path does not exist: {root_path}")
    files = []
    iterator = [root_path] if root_path.is_file() else list(root_path.rglob("*"))
    for item in iterator:
        if not item.is_file():
            continue
        try:
            stat = item.stat()
        except OSError:
            continue
        files.append(
            {
                "path": str(item),
                "relative_path": str(item.relative_to(root_path)) if root_path.is_dir() else item.name,
                "size": stat.st_size,
                "modified_time": stat.st_mtime,
            }
        )
    files.sort(key=lambda entry: entry["modified_time"], reverse=True)
    return {"root": str(root_path), "count": min(len(files), limit), "files": files[:limit]}


def read_json_file(path: str) -> dict[str, Any]:
    import json

    target = Path(path).expanduser().resolve()
    if not target.is_file():
        raise FileNotFoundError(f"File does not exist: {target}")
    data = json.loads(target.read_text(encoding="utf-8"))
    return {"path": str(target), "data": data}


def write_json_file(
    path: str,
    data: Any,
    *,
    indent: int = 2,
    ensure_ascii: bool = False,
    create_dirs: bool = True,
) -> dict[str, Any]:
    import json

    target = Path(path).expanduser().resolve()
    if create_dirs:
        target.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(data, indent=indent, ensure_ascii=ensure_ascii) + "\n"
    target.write_text(text, encoding="utf-8")
    return {"path": str(target), "bytes_written": len(text.encode("utf-8"))}


def which_command(name: str) -> dict[str, Any]:
    found = shutil.which(name)
    return {"name": name, "found": found is not None, "path": found}


def _write_to_zip(archive: zipfile.ZipFile, path: Path) -> None:
    if path.is_file():
        archive.write(path, arcname=path.name)
        return
    for item in path.rglob("*"):
        if item.is_dir():
            continue
        archive.write(item, arcname=str(Path(path.name) / item.relative_to(path)))
