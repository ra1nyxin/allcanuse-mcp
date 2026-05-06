from __future__ import annotations

import os
import urllib.request
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


@dataclass
class _Tag:
    name: str
    attrs: dict[str, str]
    line: int
    text: str = ""


class _SeoHTMLParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.html_attrs: dict[str, str] = {}
        self.title: _Tag | None = None
        self.meta: list[_Tag] = []
        self.links: list[_Tag] = []
        self.images: list[_Tag] = []
        self.anchors: list[_Tag] = []
        self.h1: list[_Tag] = []
        self._capture: _Tag | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        line, _ = self.getpos()
        tag = tag.lower()
        normalized = {key.lower(): value or "" for key, value in attrs}
        if tag == "html":
            self.html_attrs = normalized
        elif tag == "title":
            self._capture = _Tag("title", normalized, line)
            self.title = self._capture
        elif tag == "meta":
            self.meta.append(_Tag("meta", normalized, line))
        elif tag == "link":
            self.links.append(_Tag("link", normalized, line))
        elif tag == "img":
            self.images.append(_Tag("img", normalized, line))
        elif tag == "a":
            self.anchors.append(_Tag("a", normalized, line))
        elif tag == "h1":
            self._capture = _Tag("h1", normalized, line)
            self.h1.append(self._capture)

    def handle_endtag(self, tag: str) -> None:
        if self._capture and self._capture.name == tag.lower():
            self._capture.text = " ".join(self._capture.text.split())
            self._capture = None

    def handle_data(self, data: str) -> None:
        if self._capture:
            self._capture.text += data


def _issue(
    severity: str,
    code: str,
    message: str,
    *,
    path: str,
    line: int | None = None,
    detail: dict[str, Any] | None = None,
) -> dict[str, Any]:
    item: dict[str, Any] = {
        "severity": severity,
        "code": code,
        "message": message,
        "path": path,
    }
    if line is not None:
        item["line"] = line
    if detail:
        item["detail"] = detail
    return item


def _first_meta(parser: _SeoHTMLParser, key: str, value: str) -> _Tag | None:
    key = key.lower()
    value = value.lower()
    for tag in parser.meta:
        if tag.attrs.get(key, "").lower() == value:
            return tag
    return None


def _link_rel(parser: _SeoHTMLParser, rel: str) -> _Tag | None:
    rel = rel.lower()
    for tag in parser.links:
        rels = {part.strip().lower() for part in tag.attrs.get("rel", "").split()}
        if rel in rels:
            return tag
    return None


def _read_url(url: str, *, timeout_ms: int, max_bytes: int) -> tuple[str, str]:
    request = urllib.request.Request(url, headers={"User-Agent": "allcanuse-mcp-seo-audit/1.0"})
    with urllib.request.urlopen(request, timeout=max(1, timeout_ms / 1000)) as response:
        content_type = response.headers.get_content_charset() or "utf-8"
        data = response.read(max_bytes + 1)
    if len(data) > max_bytes:
        data = data[:max_bytes]
    return data.decode(content_type, errors="replace"), url


def _read_file(path: Path, *, max_bytes: int) -> tuple[str, str]:
    data = path.read_bytes()
    if len(data) > max_bytes:
        data = data[:max_bytes]
    return data.decode("utf-8", errors="replace"), str(path)


def _is_url(value: str) -> bool:
    parsed = urlparse(value)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def _html_files(root: Path, *, max_pages: int, include_hidden: bool) -> list[Path]:
    if root.is_file():
        return [root]
    files: list[Path] = []
    for current_root, dirs, names in os.walk(root):
        if not include_hidden:
            dirs[:] = [name for name in dirs if not name.startswith(".")]
            names = [name for name in names if not name.startswith(".")]
        for name in names:
            path = Path(current_root, name)
            if path.suffix.lower() in {".html", ".htm"}:
                files.append(path)
                if len(files) >= max_pages:
                    return files
    return files


def _audit_page(html: str, source: str) -> dict[str, Any]:
    parser = _SeoHTMLParser()
    parser.feed(html)

    issues: list[dict[str, Any]] = []
    title = parser.title.text.strip() if parser.title else ""
    description = _first_meta(parser, "name", "description")
    description_text = description.attrs.get("content", "").strip() if description else ""
    viewport = _first_meta(parser, "name", "viewport")
    canonical = _link_rel(parser, "canonical")
    og_title = _first_meta(parser, "property", "og:title")
    og_description = _first_meta(parser, "property", "og:description")

    if not title:
        issues.append(_issue("high", "missing_title", "Page is missing a title.", path=source))
    elif len(title) < 10:
        issues.append(_issue("medium", "short_title", "Title is very short.", path=source, line=parser.title.line))
    elif len(title) > 60:
        issues.append(_issue("medium", "long_title", "Title is longer than the common search snippet range.", path=source, line=parser.title.line))

    if not description_text:
        issues.append(_issue("high", "missing_meta_description", "Page is missing a meta description.", path=source, line=description.line if description else None))
    elif len(description_text) < 50:
        issues.append(_issue("medium", "short_meta_description", "Meta description is very short.", path=source, line=description.line))
    elif len(description_text) > 160:
        issues.append(_issue("medium", "long_meta_description", "Meta description is longer than the common search snippet range.", path=source, line=description.line))

    if not parser.h1:
        issues.append(_issue("high", "missing_h1", "Page is missing an H1.", path=source))
    elif len(parser.h1) > 1:
        issues.append(_issue("medium", "multiple_h1", "Page has multiple H1 elements.", path=source, line=parser.h1[1].line, detail={"count": len(parser.h1)}))

    missing_alt = [image for image in parser.images if not image.attrs.get("alt", "").strip()]
    if missing_alt:
        issues.append(
            _issue(
                "medium",
                "images_missing_alt",
                "Some images are missing alt text.",
                path=source,
                line=missing_alt[0].line,
                detail={"count": len(missing_alt), "examples": [item.attrs.get("src", "") for item in missing_alt[:5]]},
            )
        )

    if not parser.html_attrs.get("lang", "").strip():
        issues.append(_issue("medium", "missing_html_lang", "The html tag is missing a lang attribute.", path=source))
    if not viewport:
        issues.append(_issue("medium", "missing_viewport", "Page is missing a responsive viewport meta tag.", path=source))
    if not canonical:
        issues.append(_issue("low", "missing_canonical", "Page has no canonical link.", path=source))
    if not og_title or not og_description:
        issues.append(_issue("low", "missing_social_metadata", "Open Graph title or description is missing.", path=source))

    return {
        "source": source,
        "title": title,
        "title_length": len(title),
        "meta_description": description_text,
        "meta_description_length": len(description_text),
        "h1_count": len(parser.h1),
        "h1_text": [item.text for item in parser.h1[:5]],
        "image_count": len(parser.images),
        "images_missing_alt": len(missing_alt),
        "link_count": len(parser.anchors),
        "has_lang": bool(parser.html_attrs.get("lang", "").strip()),
        "has_viewport": viewport is not None,
        "canonical": canonical.attrs.get("href", "") if canonical else "",
        "issues": issues,
    }


def audit_seo(
    target: str,
    *,
    max_pages: int = 50,
    include_hidden: bool = False,
    max_file_size_bytes: int = 2_000_000,
    timeout_ms: int = 15_000,
) -> dict[str, Any]:
    """Audit local HTML files or one URL for common SEO problems."""

    max_pages = max(1, int(max_pages))
    max_file_size_bytes = max(1024, int(max_file_size_bytes))
    warnings: list[str] = []

    if _is_url(target):
        try:
            html, source = _read_url(target, timeout_ms=timeout_ms, max_bytes=max_file_size_bytes)
            pages = [_audit_page(html, source)]
        except Exception as exc:
            return {"ok": False, "target": target, "error": str(exc), "pages": [], "issues": [], "warnings": warnings}
        site_assets = {"robots_txt": None, "sitemap_xml": None}
    else:
        root = Path(target).expanduser().resolve()
        if not root.exists():
            raise FileNotFoundError(f"Path does not exist: {root}")
        files = _html_files(root, max_pages=max_pages, include_hidden=include_hidden)
        pages = []
        for path in files:
            try:
                html, source = _read_file(path, max_bytes=max_file_size_bytes)
            except OSError as exc:
                warnings.append(f"failed to read {path}: {exc}")
                continue
            pages.append(_audit_page(html, source))
        asset_root = root if root.is_dir() else root.parent
        site_assets = {
            "robots_txt": str(asset_root / "robots.txt") if (asset_root / "robots.txt").exists() else None,
            "sitemap_xml": str(asset_root / "sitemap.xml") if (asset_root / "sitemap.xml").exists() else None,
        }
        if not site_assets["robots_txt"]:
            warnings.append("robots.txt was not found next to the audited site root")
        if not site_assets["sitemap_xml"]:
            warnings.append("sitemap.xml was not found next to the audited site root")

    issues = [issue for page in pages for issue in page["issues"]]
    titles: dict[str, list[str]] = {}
    descriptions: dict[str, list[str]] = {}
    for page in pages:
        if page["title"]:
            titles.setdefault(page["title"], []).append(page["source"])
        if page["meta_description"]:
            descriptions.setdefault(page["meta_description"], []).append(page["source"])
    for value, sources in titles.items():
        if len(sources) > 1:
            issues.append(_issue("medium", "duplicate_title", "Multiple pages share the same title.", path=sources[0], detail={"count": len(sources), "title": value, "sources": sources[:10]}))
    for value, sources in descriptions.items():
        if len(sources) > 1:
            issues.append(_issue("medium", "duplicate_meta_description", "Multiple pages share the same meta description.", path=sources[0], detail={"count": len(sources), "sources": sources[:10]}))

    summary = {
        "high": sum(1 for item in issues if item["severity"] == "high"),
        "medium": sum(1 for item in issues if item["severity"] == "medium"),
        "low": sum(1 for item in issues if item["severity"] == "low"),
    }
    return {
        "ok": True,
        "target": target,
        "page_count": len(pages),
        "issue_count": len(issues),
        "summary": summary,
        "site_assets": site_assets,
        "warnings": warnings,
        "pages": pages,
        "issues": issues,
    }
