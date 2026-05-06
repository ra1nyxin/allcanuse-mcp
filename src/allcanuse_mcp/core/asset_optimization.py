from __future__ import annotations

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
    except Exception as exc:
        return {"ok": False, "error": f"Pillow is required for image optimization: {exc}", "results": []}

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

                target_extension = f".{convert_to.lower().lstrip('.')}" if convert_to else source.suffix
                destination = source if overwrite else _output_path(
                    source,
                    output_dir=output_dir,
                    suffix=suffix,
                    target_extension=target_extension,
                )
                destination.parent.mkdir(parents=True, exist_ok=True)
                format_name = _format_for_path(destination, original_format, convert_to)
                if format_name == "JPEG" and optimized.mode not in {"RGB", "L"}:
                    optimized = optimized.convert("RGB")

                optimized.save(destination, format=format_name, **_save_options(format_name, quality))
                optimized_size = destination.stat().st_size
        except Exception as exc:
            item.update({"ok": False, "error": str(exc)})
            results.append(item)
            continue

        item.update(
            {
                "ok": True,
                "output_path": str(destination),
                "original_size_bytes": original_size,
                "optimized_size_bytes": optimized_size,
                "saved_bytes": original_size - optimized_size,
                "saved_percent": round(((original_size - optimized_size) / original_size * 100), 2) if original_size else 0,
                "original_dimensions": list(original_dimensions),
                "optimized_dimensions": list(optimized.size),
                "resized": resized,
                "format": format_name,
                "overwrote_source": overwrite,
            }
        )
        if optimized_size > original_size and not overwrite:
            item["warning"] = "optimized file is larger than the source; keep the original if size is the priority"
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
