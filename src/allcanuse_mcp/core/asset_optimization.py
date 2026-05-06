from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any


IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif", ".tiff"}


def _iter_image_paths(paths: list[str], *, recursive: bool) -> list[Path]:
    results: list[Path] = []
    seen: set[str] = set()
    for raw_path in paths:
        path = Path(raw_path).expanduser().resolve()
        candidates: list[Path]
        if path.is_dir():
            iterator = path.rglob("*") if recursive else path.iterdir()
            candidates = [item for item in iterator if item.is_file() and item.suffix.lower() in IMAGE_EXTENSIONS]
        else:
            candidates = [path]
        for candidate in candidates:
            key = str(candidate).lower()
            if key not in seen:
                seen.add(key)
                results.append(candidate)
    return results


def _output_path(source: Path, *, output_dir: str | None, suffix: str, target_extension: str) -> Path:
    extension = target_extension if target_extension.startswith(".") else f".{target_extension}"
    if output_dir:
        directory = Path(output_dir).expanduser().resolve()
        return directory / f"{source.stem}{extension}"
    return source.with_name(f"{source.stem}{suffix}{extension}")


def _format_for_path(path: Path, original_format: str | None, convert_to: str | None) -> str:
    if convert_to:
        value = convert_to.lower().strip().lstrip(".")
    else:
        value = path.suffix.lower().lstrip(".")
    if value == "jpg":
        return "JPEG"
    if value == "tif":
        return "TIFF"
    return value.upper() if value else (original_format or "PNG")


def _save_options(format_name: str, quality: int) -> dict[str, Any]:
    if format_name in {"JPEG", "WEBP"}:
        return {"quality": quality, "optimize": True}
    if format_name == "PNG":
        return {"optimize": True}
    return {}


def _summarize_success(
    *,
    source: Path,
    destination: Path,
    original_size: int,
    optimized_size: int,
    original_dimensions: tuple[int, int] | list[int] | None,
    optimized_dimensions: tuple[int, int] | list[int] | None,
    resized: bool,
    format_name: str,
    overwrite: bool,
    backend: str,
    attempts: list[dict[str, Any]],
) -> dict[str, Any]:
    item: dict[str, Any] = {
        "ok": True,
        "source_path": str(source),
        "output_path": str(destination),
        "backend": backend,
        "attempts": attempts,
        "original_size_bytes": original_size,
        "optimized_size_bytes": optimized_size,
        "saved_bytes": original_size - optimized_size,
        "saved_percent": round(((original_size - optimized_size) / original_size * 100), 2) if original_size else 0,
        "original_dimensions": list(original_dimensions) if original_dimensions else None,
        "optimized_dimensions": list(optimized_dimensions) if optimized_dimensions else None,
        "resized": resized,
        "format": format_name,
        "overwrote_source": overwrite,
    }
    if optimized_size > original_size and not overwrite:
        item["warning"] = "optimized file is larger than the source; keep the original if size is the priority"
    return item


def _target_extension_for(source: Path, convert_to: str | None) -> str:
    return f".{convert_to.lower().lstrip('.')}" if convert_to else source.suffix


def _quality_to_ffmpeg_qscale(quality: int) -> str:
    return str(max(2, min(31, round(31 - (quality / 100 * 29)))))


def _ffmpeg_filter(max_width: int | None, max_height: int | None) -> list[str]:
    if not max_width and not max_height:
        return []
    width = str(max_width) if max_width else "-2"
    height = str(max_height) if max_height else "-2"
    if max_width and max_height:
        return ["-vf", f"scale={width}:{height}:force_original_aspect_ratio=decrease"]
    return ["-vf", f"scale={width}:{height}"]


def _run_image_command(command: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )


def _optimize_with_ffmpeg(
    source: Path,
    destination: Path,
    *,
    quality: int,
    max_width: int | None,
    max_height: int | None,
) -> dict[str, Any]:
    executable = shutil.which("ffmpeg")
    if executable is None:
        return {"ok": False, "error": "ffmpeg executable was not found."}
    command = [executable, "-y", "-i", str(source)]
    command.extend(_ffmpeg_filter(max_width, max_height))
    command.extend(["-frames:v", "1", "-q:v", _quality_to_ffmpeg_qscale(quality), str(destination)])
    result = _run_image_command(command)
    return {
        "ok": result.returncode == 0 and destination.exists(),
        "command": command,
        "returncode": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr,
        "error": None if result.returncode == 0 and destination.exists() else (result.stderr.strip() or "ffmpeg failed."),
    }


def _optimize_with_magick(
    source: Path,
    destination: Path,
    *,
    quality: int,
    max_width: int | None,
    max_height: int | None,
) -> dict[str, Any]:
    executable = shutil.which("magick")
    if executable is None and not _is_windows_platform():
        executable = shutil.which("convert")
    if executable is None:
        return {"ok": False, "error": "ImageMagick executable was not found."}
    command = [executable, str(source), "-auto-orient"]
    if max_width or max_height:
        width = str(max_width) if max_width else ""
        height = str(max_height) if max_height else ""
        command.extend(["-resize", f"{width}x{height}>"])
    command.extend(["-quality", str(quality), str(destination)])
    result = _run_image_command(command)
    return {
        "ok": result.returncode == 0 and destination.exists(),
        "command": command,
        "returncode": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr,
        "error": None if result.returncode == 0 and destination.exists() else (result.stderr.strip() or "ImageMagick failed."),
    }


def _is_windows_platform() -> bool:
    return Path("C:/").anchor != ""


def _optimize_with_cli_fallbacks(
    source: Path,
    destination: Path,
    *,
    original_size: int,
    quality: int,
    max_width: int | None,
    max_height: int | None,
    format_name: str,
    overwrite: bool,
    attempts: list[dict[str, Any]],
) -> dict[str, Any] | None:
    command_destination = destination
    temporary_destination: Path | None = None
    if overwrite:
        handle = tempfile.NamedTemporaryFile(
            prefix=f"{source.stem}.",
            suffix=destination.suffix,
            dir=str(destination.parent),
            delete=False,
        )
        handle.close()
        command_destination = Path(handle.name)
        temporary_destination = command_destination

    for backend, optimizer in (
        ("ffmpeg", _optimize_with_ffmpeg),
        ("imagemagick", _optimize_with_magick),
    ):
        try:
            if temporary_destination is not None and temporary_destination.exists():
                temporary_destination.unlink()
            result = optimizer(source, command_destination, quality=quality, max_width=max_width, max_height=max_height)
        except Exception as exc:
            result = {"ok": False, "error": str(exc)}
        attempt = {"backend": backend, "ok": bool(result.get("ok"))}
        if result.get("error"):
            attempt["error"] = result["error"]
        attempts.append(attempt)
        if result.get("ok"):
            if temporary_destination is not None:
                shutil.move(str(temporary_destination), str(destination))
            optimized_size = destination.stat().st_size
            return _summarize_success(
                source=source,
                destination=destination,
                original_size=original_size,
                optimized_size=optimized_size,
                original_dimensions=None,
                optimized_dimensions=None,
                resized=bool(max_width or max_height),
                format_name=format_name,
                overwrite=overwrite,
                backend=backend,
                attempts=attempts,
            )
    if temporary_destination is not None:
        try:
            temporary_destination.unlink()
        except OSError:
            pass
    return None


def optimize_images_for_memory(
    paths: list[str],
    *,
    output_dir: str | None = None,
    quality: int = 85,
    max_width: int | None = None,
    max_height: int | None = None,
    convert_to: str | None = None,
    overwrite: bool = False,
    recursive: bool = False,
    suffix: str = ".optimized",
) -> dict[str, Any]:
    """Create smaller image files while preserving the main visual result by default."""

    try:
        from PIL import Image
        pillow_error = None
    except Exception as exc:
        Image = None  # type: ignore[assignment]
        pillow_error = f"Pillow is not available: {exc}"

    if not paths:
        raise ValueError("paths must contain at least one file or directory")
    if overwrite and convert_to:
        raise ValueError("overwrite cannot be combined with convert_to because the output extension may change")
    quality = min(100, max(1, int(quality)))
    if max_width is not None:
        max_width = max(1, int(max_width))
    if max_height is not None:
        max_height = max(1, int(max_height))

    source_paths = _iter_image_paths(paths, recursive=recursive)
    results: list[dict[str, Any]] = []
    warnings: list[str] = []

    for source in source_paths:
        item: dict[str, Any] = {"source_path": str(source)}
        if not source.exists():
            item.update({"ok": False, "error": "source path does not exist"})
            results.append(item)
            continue
        if not source.is_file():
            item.update({"ok": False, "error": "source path is not a file"})
            results.append(item)
            continue
        if source.suffix.lower() not in IMAGE_EXTENSIONS:
            item.update({"ok": False, "error": "unsupported image extension"})
            results.append(item)
            continue

        try:
            original_size = source.stat().st_size
            target_extension = _target_extension_for(source, convert_to)
            destination = source if overwrite else _output_path(
                source,
                output_dir=output_dir,
                suffix=suffix,
                target_extension=target_extension,
            )
            destination.parent.mkdir(parents=True, exist_ok=True)
            format_name = _format_for_path(destination, None, convert_to)
            attempts: list[dict[str, Any]] = []

            if Image is None:
                attempts.append({"backend": "pillow", "ok": False, "error": pillow_error})
                cli_item = _optimize_with_cli_fallbacks(
                    source,
                    destination,
                    original_size=original_size,
                    quality=quality,
                    max_width=max_width,
                    max_height=max_height,
                    format_name=format_name,
                    overwrite=overwrite,
                    attempts=attempts,
                )
                if cli_item is None:
                    item.update({"ok": False, "error": pillow_error or "No image optimization backend succeeded.", "attempts": attempts})
                    results.append(item)
                    continue
                results.append(cli_item)
                continue

            try:
                with Image.open(source) as image:
                    original_format = image.format
                    original_dimensions = image.size
                    optimized = image.copy()
                    resized = False

                    if max_width or max_height:
                        limit_width = max_width or optimized.width
                        limit_height = max_height or optimized.height
                        if optimized.width > limit_width or optimized.height > limit_height:
                            optimized.thumbnail((limit_width, limit_height), Image.Resampling.LANCZOS)
                            resized = optimized.size != original_dimensions

                    format_name = _format_for_path(destination, original_format, convert_to)
                    if format_name == "JPEG" and optimized.mode not in {"RGB", "L"}:
                        optimized = optimized.convert("RGB")

                    optimized.save(destination, format=format_name, **_save_options(format_name, quality))
                    optimized_size = destination.stat().st_size
                    attempts.append({"backend": "pillow", "ok": True})
            except Exception as exc:
                attempts.append({"backend": "pillow", "ok": False, "error": str(exc)})
                cli_item = _optimize_with_cli_fallbacks(
                    source,
                    destination,
                    original_size=original_size,
                    quality=quality,
                    max_width=max_width,
                    max_height=max_height,
                    format_name=format_name,
                    overwrite=overwrite,
                    attempts=attempts,
                )
                if cli_item is None:
                    raise
                results.append(cli_item)
                continue
        except Exception as exc:
            item.update({"ok": False, "error": str(exc)})
            results.append(item)
            continue

        item = _summarize_success(
            source=source,
            destination=destination,
            original_size=original_size,
            optimized_size=optimized_size,
            original_dimensions=original_dimensions,
            optimized_dimensions=optimized.size,
            resized=resized,
            format_name=format_name,
            overwrite=overwrite,
            backend="pillow",
            attempts=attempts,
        )
        results.append(item)

    ok_count = sum(1 for item in results if item.get("ok"))
    total_original = sum(int(item.get("original_size_bytes", 0)) for item in results if item.get("ok"))
    total_optimized = sum(int(item.get("optimized_size_bytes", 0)) for item in results if item.get("ok"))
    return {
        "ok": all(item.get("ok") for item in results) if results else True,
        "processed_count": len(results),
        "optimized_count": ok_count,
        "total_original_size_bytes": total_original,
        "total_optimized_size_bytes": total_optimized,
        "total_saved_bytes": total_original - total_optimized,
        "warnings": warnings,
        "results": results,
    }
