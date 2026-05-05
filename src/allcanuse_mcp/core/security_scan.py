from __future__ import annotations

import ctypes
import hashlib
import os
import platform
import re
from pathlib import Path
from typing import Any


SUSPICIOUS_NAME_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("backdoor", re.compile(r"(?i)\bbackdoor\b")),
    ("loader", re.compile(r"(?i)\bloader\b")),
    ("dropper", re.compile(r"(?i)\bdropper\b")),
    ("injector", re.compile(r"(?i)\binject(?:or|ion)?\b")),
    ("keylogger", re.compile(r"(?i)\bkeylog(?:ger)?\b")),
    ("rat", re.compile(r"(?i)\brat\b")),
    ("stealer", re.compile(r"(?i)\bstealer\b")),
    ("miner", re.compile(r"(?i)\b(?:crypto)?miner\b")),
    ("payload", re.compile(r"(?i)\bpayload\b")),
    ("autorun", re.compile(r"(?i)\bautorun\b")),
]

SUSPICIOUS_CONTENT_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("powershell encoded command", re.compile(r"(?i)\b(?:powershell|pwsh)\b.{0,80}\-(?:enc|encodedcommand)\b")),
    ("downloadstring", re.compile(r"(?i)\bdownloadstring\b")),
    ("invoke-expression", re.compile(r"(?i)\b(?:invoke-expression|iex)\b")),
    ("webclient download", re.compile(r"(?i)\b(?:new-object|new\s+object)\b.{0,40}\bnet\.webclient\b|\bsystem\.net\.webclient\b")),
    ("base64 decode", re.compile(r"(?i)\bfrombase64string\b")),
    ("script host shell", re.compile(r"(?i)\b(?:wscript\.shell|shell\.application)\b")),
    ("scheduled task persistence", re.compile(r"(?i)\bschtasks(?:\.exe)?\b")),
    ("registry autorun", re.compile(r"(?i)\breg\s+add\b.{0,80}\\run(?:once)?\\|\bset-itemproperty\b.{0,80}\\run(?:once)?\\")),
    ("system defense tampering", re.compile(r"(?i)\b(?:add-mppreference|set-mppreference|disable-realtimemonitoring)\b")),
    ("process injection", re.compile(r"(?i)\b(?:virtualalloc(?:ex)?|writeprocessmemory|createremotethread)\b")),
    ("living off the land", re.compile(r"(?i)\b(?:mshta|rundll32|bitsadmin|certutil|curl|wget)\b")),
    ("command execution", re.compile(r"(?i)\b(?:cmd(?:\.exe)?\s+/c|python\s+-c|powershell\s+-c)\b")),
]

SUSPICIOUS_EXTENSIONS = {
    ".ps1",
    ".psm1",
    ".psd1",
    ".vbs",
    ".vbe",
    ".js",
    ".jse",
    ".wsf",
    ".hta",
    ".bat",
    ".cmd",
    ".sh",
    ".py",
    ".pyw",
    ".lnk",
    ".com",
    ".scr",
    ".pif",
    ".dll",
    ".exe",
}

TEXT_EXTENSIONS = {
    ".txt",
    ".md",
    ".log",
    ".cfg",
    ".conf",
    ".ini",
    ".json",
    ".xml",
    ".yml",
    ".yaml",
    ".ps1",
    ".psm1",
    ".psd1",
    ".vbs",
    ".vbe",
    ".js",
    ".jse",
    ".wsf",
    ".hta",
    ".bat",
    ".cmd",
    ".sh",
    ".py",
    ".pyw",
}

WINDOWS_STARTUP_SEGMENTS = {
    ("appdata", "roaming", "microsoft", "windows", "start menu", "programs", "startup"),
    ("programdata", "microsoft", "windows", "start menu", "programs", "startup"),
}

LINUX_STARTUP_SEGMENTS = {
    ("config", "autostart"),
    (".config", "autostart"),
    (".local", "share", "applications"),
}


def _is_windows() -> bool:
    return platform.system() == "Windows"


def _windows_hidden_attributes(path: Path) -> int | None:
    if not _is_windows():
        return None
    try:
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.GetFileAttributesW.argtypes = [ctypes.c_wchar_p]
        kernel32.GetFileAttributesW.restype = ctypes.c_uint32
        value = int(kernel32.GetFileAttributesW(str(path)))
    except Exception:
        return None
    if value == 0xFFFFFFFF:
        return None
    return value


def _is_hidden_path(path: Path) -> bool:
    if any(part.startswith(".") for part in path.parts if part not in {path.anchor}):
        return True
    if not _is_windows():
        return False
    attrs = _windows_hidden_attributes(path)
    if attrs is None:
        return False
    return bool(attrs & 0x2 or attrs & 0x4)


def _is_startup_location(path: Path) -> bool:
    parts = tuple(part.lower() for part in path.parts if part and part != path.anchor)
    if _is_windows():
        for segment in WINDOWS_STARTUP_SEGMENTS:
            if all(piece in parts for piece in segment):
                return True
    else:
        for segment in LINUX_STARTUP_SEGMENTS:
            if all(piece in parts for piece in segment):
                return True
    return False


def _filename_hits(name: str) -> list[str]:
    hits: list[str] = []
    for label, pattern in SUSPICIOUS_NAME_PATTERNS:
        if pattern.search(name):
            hits.append(label)
    return hits


def _file_hash(path: Path, *, chunk_size: int = 1024 * 1024) -> str | None:
    try:
        hasher = hashlib.sha256()
        with path.open("rb") as handle:
            while True:
                chunk = handle.read(chunk_size)
                if not chunk:
                    break
                hasher.update(chunk)
        return hasher.hexdigest()
    except OSError:
        return None


def _text_sample(path: Path, *, max_bytes: int) -> str:
    try:
        data = path.read_bytes()
    except OSError:
        return ""
    if not data:
        return ""
    sample = data[:max_bytes]
    try:
        return sample.decode("utf-8", errors="replace")
    except Exception:
        return ""


def _content_hits(path: Path, *, max_file_size_bytes: int) -> list[dict[str, Any]]:
    if path.suffix.lower() not in TEXT_EXTENSIONS:
        return []
    try:
        size = path.stat().st_size
    except OSError:
        return []
    if size > max_file_size_bytes:
        return []
    text = _text_sample(path, max_bytes=max_file_size_bytes)
    if not text:
        return []
    hits: list[dict[str, Any]] = []
    for line_number, line in enumerate(text.splitlines(), start=1):
        for label, pattern in SUSPICIOUS_CONTENT_PATTERNS:
            if pattern.search(line):
                hits.append(
                    {
                        "pattern": label,
                        "line_number": line_number,
                        "excerpt": line[:240],
                    }
                )
        if len(hits) >= 8:
            break
    return hits


def _default_scan_roots() -> list[Path]:
    home = Path.home()
    roots: list[Path] = []
    if _is_windows():
        appdata = Path(os.environ.get("APPDATA", home / "AppData" / "Roaming"))
        localappdata = Path(os.environ.get("LOCALAPPDATA", home / "AppData" / "Local"))
        programdata = Path(os.environ.get("PROGRAMDATA", r"C:\ProgramData"))
        roots.extend(
            [
                home / "Desktop",
                home / "Downloads",
                home / "Documents",
                localappdata / "Temp",
                appdata / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup",
                programdata / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup",
            ]
        )
    else:
        roots.extend(
            [
                home / "Desktop",
                home / "Downloads",
                home / "Documents",
                home / ".config" / "autostart",
                home / ".local" / "share" / "applications",
                Path("/tmp"),
                Path("/var/tmp"),
            ]
        )
    normalized: list[Path] = []
    seen: set[str] = set()
    for root in roots:
        resolved = root.expanduser().resolve()
        key = str(resolved).lower()
        if key in seen:
            continue
        seen.add(key)
        normalized.append(resolved)
    return normalized


def _relative_path(path: Path, root: Path) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return path.name


def _score_finding(
    *,
    hidden: bool,
    startup: bool,
    name_hits: list[str],
    content_hits: list[dict[str, Any]],
    suffix: str,
    file_size: int,
) -> tuple[int, list[str]]:
    reasons: list[str] = []
    score = 0
    if hidden:
        score += 20
        reasons.append("hidden path")
    if startup:
        score += 25
        reasons.append("startup location")
    if suffix in SUSPICIOUS_EXTENSIONS:
        score += 20
        reasons.append(f"suspicious extension {suffix}")
    if name_hits:
        score += min(20 + 5 * len(name_hits), 35)
        reasons.extend([f"filename hit: {hit}" for hit in name_hits[:4]])
    if content_hits:
        score += min(20 + 10 * len(content_hits), 50)
        reasons.extend([f"content hit: {item['pattern']}" for item in content_hits[:4]])
    if suffix in {".exe", ".dll", ".scr", ".com"} and file_size > 0 and startup:
        score += 20
        reasons.append("executable in startup location")
    return score, reasons


def _severity_from_score(score: int) -> str:
    if score >= 75:
        return "high"
    if score >= 40:
        return "medium"
    return "low"


def scan_suspicious_files(
    roots: list[str] | None = None,
    *,
    max_depth: int = 6,
    max_results: int = 200,
    include_hidden: bool = True,
    scan_contents: bool = True,
    max_file_size_bytes: int = 1_000_000,
) -> dict[str, Any]:
    scan_roots = [Path(root).expanduser().resolve() for root in (roots or [])] if roots else _default_scan_roots()
    max_depth = max(0, int(max_depth))
    max_results = max(1, int(max_results))
    max_file_size_bytes = max(1, int(max_file_size_bytes))

    findings: list[dict[str, Any]] = []
    warnings: list[str] = []
    scanned_roots: list[str] = []
    scanned_files = 0

    for root in scan_roots:
        if len(findings) >= max_results:
            break
        if not root.exists():
            warnings.append(f"root missing: {root}")
            continue
        scanned_roots.append(str(root))

        if root.is_file():
            candidates = [root]
        else:
            candidates = []
            for current_root, dirs, files in os.walk(root, followlinks=False):
                current_path = Path(current_root)
                try:
                    depth = len(current_path.relative_to(root).parts)
                except ValueError:
                    depth = 0
                if depth > max_depth:
                    dirs[:] = []
                    continue
                if not include_hidden:
                    dirs[:] = [item for item in dirs if not item.startswith(".")]
                    files = [item for item in files if not item.startswith(".")]
                for file_name in files:
                    candidates.append(current_path / file_name)

        for path in candidates:
            if len(findings) >= max_results:
                break
            if not path.exists() or not path.is_file():
                continue
            scanned_files += 1
            try:
                stat_result = path.stat()
            except OSError:
                continue

            hidden = _is_hidden_path(path)
            if hidden and not include_hidden:
                continue
            startup = _is_startup_location(path)
            suffix = path.suffix.lower()
            name_hits = _filename_hits(path.name)
            content_hits = _content_hits(path, max_file_size_bytes=max_file_size_bytes) if scan_contents else []
            score, reasons = _score_finding(
                hidden=hidden,
                startup=startup,
                name_hits=name_hits,
                content_hits=content_hits,
                suffix=suffix,
                file_size=stat_result.st_size,
            )
            if score < 25:
                continue
            finding = {
                "path": str(path),
                "root": str(root),
                "relative_path": _relative_path(path, root),
                "severity": _severity_from_score(score),
                "score": score,
                "reasons": reasons,
                "is_hidden": hidden,
                "is_startup_location": startup,
                "extension": suffix,
                "size": stat_result.st_size,
                "sha256": _file_hash(path) if stat_result.st_size <= max_file_size_bytes else None,
                "name_hits": name_hits,
                "content_hits": content_hits,
            }
            if path.is_symlink():
                finding["is_symlink"] = True
            findings.append(finding)

    findings.sort(key=lambda item: (item["score"], item["size"]), reverse=True)
    summary = {
        "high": sum(1 for item in findings if item["severity"] == "high"),
        "medium": sum(1 for item in findings if item["severity"] == "medium"),
        "low": sum(1 for item in findings if item["severity"] == "low"),
    }
    return {
        "ok": True,
        "platform": platform.system(),
        "scanned_roots": scanned_roots,
        "scanned_files": scanned_files,
        "count": len(findings),
        "summary": summary,
        "warnings": warnings,
        "truncated": len(findings) >= max_results,
        "findings": findings[:max_results],
    }
