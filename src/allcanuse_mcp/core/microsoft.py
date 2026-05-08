from __future__ import annotations

import platform
import posixpath
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

try:  # pragma: no cover - Windows only import
    import winreg  # type: ignore[attr-defined]
except ImportError:  # pragma: no cover - non-Windows platforms
    winreg = None  # type: ignore[assignment]


_ZIP_NS = {"main": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
_WORD_NS = {
    "w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main",
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
}
_PPT_NS = {
    "p": "http://schemas.openxmlformats.org/presentationml/2006/main",
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
}
_REL_NS = {"rel": "http://schemas.openxmlformats.org/package/2006/relationships"}
_CORE_NS = {
    "cp": "http://schemas.openxmlformats.org/package/2006/metadata/core-properties",
    "dc": "http://purl.org/dc/elements/1.1/",
    "dcterms": "http://purl.org/dc/terms/",
}
_UNINSTALL_PATHS = (
    r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall",
    r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall",
)


def list_installed_microsoft_software(*, max_results: int = 200) -> dict[str, Any]:
    if platform.system() != "Windows" or winreg is None:
        return {"ok": False, "error": "Microsoft software inventory is only available on Windows."}
    entries = _windows_registry_microsoft_software_entries(max_results=max_results)
    return {"ok": True, "count": len(entries), "entries": entries}


def inspect_excel_workbook(
    path: str,
    *,
    max_sheets: int = 10,
    max_rows: int = 20,
    max_cells: int = 20,
) -> dict[str, Any]:
    workbook_path = Path(path).expanduser().resolve()
    if not workbook_path.exists():
        return {"ok": False, "error": f"Workbook does not exist: {workbook_path}", "path": str(workbook_path)}
    if workbook_path.suffix.lower() not in {".xlsx", ".xlsm", ".xltx", ".xltm"}:
        return {"ok": False, "error": "Expected an Excel Open XML workbook (.xlsx/.xlsm/.xltx/.xltm).", "path": str(workbook_path)}
    try:
        with zipfile.ZipFile(workbook_path) as archive:
            workbook = _read_xml_from_zip(archive, "xl/workbook.xml")
            if workbook is None:
                return {"ok": False, "error": "Workbook XML not found.", "path": str(workbook_path)}
            rels = _read_xml_from_zip(archive, "xl/_rels/workbook.xml.rels")
            shared_strings = _read_excel_shared_strings(archive)
            sheet_entries = _read_excel_sheet_entries(workbook, rels)
            sheets = []
            for item in sheet_entries[:max_sheets]:
                sheet = _read_excel_sheet(archive, item, shared_strings, max_rows=max_rows, max_cells=max_cells)
                sheets.append(sheet)
            return {
                "ok": True,
                "path": str(workbook_path),
                "sheet_count": len(sheet_entries),
                "sheets": sheets,
                "core_properties": _read_core_properties(archive),
            }
    except zipfile.BadZipFile:
        return {"ok": False, "error": "File is not a valid Open XML workbook.", "path": str(workbook_path)}


def inspect_word_document(
    path: str,
    *,
    max_paragraphs: int = 20,
    max_tables: int = 5,
) -> dict[str, Any]:
    document_path = Path(path).expanduser().resolve()
    if not document_path.exists():
        return {"ok": False, "error": f"Document does not exist: {document_path}", "path": str(document_path)}
    if document_path.suffix.lower() not in {".docx", ".docm", ".dotx", ".dotm"}:
        return {"ok": False, "error": "Expected a Word Open XML document (.docx/.docm/.dotx/.dotm).", "path": str(document_path)}
    try:
        with zipfile.ZipFile(document_path) as archive:
            document_xml = _read_xml_from_zip(archive, "word/document.xml")
            if document_xml is None:
                return {"ok": False, "error": "Document XML not found.", "path": str(document_path)}
            body = document_xml.find("w:body", _WORD_NS)
            if body is None:
                return {"ok": False, "error": "Word document body is missing.", "path": str(document_path)}
            paragraphs = _collect_word_paragraphs(body, max_paragraphs=max_paragraphs)
            return {
                "ok": True,
                "path": str(document_path),
                "paragraph_count": len(body.findall(".//w:p", _WORD_NS)),
                "table_count": len(body.findall(".//w:tbl", _WORD_NS)),
                "paragraphs": paragraphs,
                "core_properties": _read_core_properties(archive),
                "table_limit": max_tables,
            }
    except zipfile.BadZipFile:
        return {"ok": False, "error": "File is not a valid Open XML Word document.", "path": str(document_path)}


def inspect_powerpoint_presentation(
    path: str,
    *,
    max_slides: int = 20,
) -> dict[str, Any]:
    presentation_path = Path(path).expanduser().resolve()
    if not presentation_path.exists():
        return {"ok": False, "error": f"Presentation does not exist: {presentation_path}", "path": str(presentation_path)}
    if presentation_path.suffix.lower() not in {".pptx", ".pptm", ".potx", ".potm"}:
        return {"ok": False, "error": "Expected a PowerPoint Open XML presentation (.pptx/.pptm/.potx/.potm).", "path": str(presentation_path)}
    try:
        with zipfile.ZipFile(presentation_path) as archive:
            presentation_xml = _read_xml_from_zip(archive, "ppt/presentation.xml")
            rels_xml = _read_xml_from_zip(archive, "ppt/_rels/presentation.xml.rels")
            if presentation_xml is None or rels_xml is None:
                return {"ok": False, "error": "Presentation XML or relationship data not found.", "path": str(presentation_path)}
            slides = []
            for index, slide_target in enumerate(_read_ppt_slide_targets(presentation_xml, rels_xml), start=1):
                if index > max_slides:
                    break
                slide_xml = _read_xml_from_zip(archive, slide_target)
                if slide_xml is None:
                    slides.append({"index": index, "path": slide_target, "ok": False, "error": "Slide XML not found."})
                    continue
                texts = _collect_ppt_slide_text(slide_xml)
                slides.append(
                    {
                        "index": index,
                        "path": slide_target,
                        "ok": True,
                        "text_count": len(texts),
                        "texts": texts[:20],
                        "title": texts[0] if texts else "",
                    }
                )
            return {
                "ok": True,
                "path": str(presentation_path),
                "slide_count": len(_read_ppt_slide_targets(presentation_xml, rels_xml)),
                "slides": slides,
                "core_properties": _read_core_properties(archive),
            }
    except zipfile.BadZipFile:
        return {"ok": False, "error": "File is not a valid Open XML PowerPoint presentation.", "path": str(presentation_path)}


def _windows_registry_microsoft_software_entries(*, max_results: int) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()
    roots = [winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER]  # type: ignore[union-attr]
    for root in roots:
        for uninstall_path in _UNINSTALL_PATHS:
            try:
                with winreg.OpenKey(root, uninstall_path) as uninstall_root:  # type: ignore[union-attr]
                    entries.extend(_enumerate_windows_registry_entries(uninstall_root, uninstall_path, seen=seen, max_results=max_results - len(entries)))
            except OSError:
                continue
            if len(entries) >= max_results:
                return entries[:max_results]
    return entries[:max_results]


def _enumerate_windows_registry_entries(
    uninstall_root,
    uninstall_path: str,
    *,
    seen: set[tuple[str, str, str]],
    max_results: int,
) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    index = 0
    while len(entries) < max_results:
        try:
            subkey_name = winreg.EnumKey(uninstall_root, index)  # type: ignore[union-attr]
        except OSError:
            break
        index += 1
        try:
            with winreg.OpenKey(uninstall_root, subkey_name) as subkey:  # type: ignore[union-attr]
                values = _read_registry_values(subkey)
        except OSError:
            continue
        name = str(values.get("DisplayName") or "").strip()
        publisher = str(values.get("Publisher") or "").strip()
        version = str(values.get("DisplayVersion") or "").strip()
        if not _looks_like_microsoft_software(name=name, publisher=publisher):
            continue
        key = (name.casefold(), version.casefold(), uninstall_path.casefold())
        if key in seen:
            continue
        seen.add(key)
        entry = {
            "name": name,
            "version": version,
            "publisher": publisher,
            "install_location": str(values.get("InstallLocation") or "").strip(),
            "uninstall_string": str(values.get("UninstallString") or "").strip(),
            "quiet_uninstall_string": str(values.get("QuietUninstallString") or "").strip(),
            "source": uninstall_path,
        }
        entries.append(entry)
    return entries


def _read_registry_values(key) -> dict[str, Any]:
    values: dict[str, Any] = {}
    index = 0
    while True:
        try:
            name, value, _ = winreg.EnumValue(key, index)  # type: ignore[union-attr]
        except OSError:
            break
        values[name] = value
        index += 1
    return values


def _looks_like_microsoft_software(*, name: str, publisher: str) -> bool:
    name_l = name.casefold()
    publisher_l = publisher.casefold()
    if "microsoft" in name_l or "microsoft" in publisher_l:
        return True
    office_hits = ("office" in name_l and "365" in name_l) or ("visual studio" in name_l) or ("msbuild" in name_l) or ("edge" in name_l)
    return office_hits and ("microsoft" in publisher_l or "microsoft" in name_l)


def _read_xml_from_zip(archive: zipfile.ZipFile, name: str) -> ET.Element | None:
    try:
        data = archive.read(name)
    except KeyError:
        return None
    try:
        return ET.fromstring(data)
    except ET.ParseError:
        return None


def _read_core_properties(archive: zipfile.ZipFile) -> dict[str, str]:
    core = _read_xml_from_zip(archive, "docProps/core.xml")
    if core is None:
        return {}
    properties = {}
    for key, namespace in (("title", "dc:title"), ("subject", "dc:subject"), ("creator", "dc:creator"), ("description", "dc:description")):
        element = core.find(namespace, _CORE_NS)
        if element is not None and element.text:
            properties[key] = element.text.strip()
    modified = core.find("dcterms:modified", _CORE_NS)
    if modified is not None and modified.text:
        properties["modified"] = modified.text.strip()
    return properties


def _read_excel_shared_strings(archive: zipfile.ZipFile) -> list[str]:
    shared_strings_xml = _read_xml_from_zip(archive, "xl/sharedStrings.xml")
    if shared_strings_xml is None:
        return []
    values = []
    for item in shared_strings_xml.findall("main:si", _ZIP_NS):
        values.append("".join(text or "" for text in item.itertext()))
    return values


def _read_excel_sheet_entries(workbook_xml: ET.Element, rels_xml: ET.Element | None) -> list[dict[str, str]]:
    rel_targets: dict[str, str] = {}
    if rels_xml is not None:
        for relation in rels_xml.findall("rel:Relationship", _REL_NS):
            rel_targets[relation.attrib.get("Id", "")] = relation.attrib.get("Target", "")
    sheets = []
    for sheet in workbook_xml.findall("main:sheets/main:sheet", _ZIP_NS):
        rel_id = sheet.attrib.get("{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id", "")
        target = rel_targets.get(rel_id, "")
        if target:
            target = posixpath.normpath(f"xl/{target.lstrip('/')}")
        sheets.append({"name": sheet.attrib.get("name", ""), "path": target, "sheet_id": sheet.attrib.get("sheetId", "")})
    return sheets


def _read_excel_sheet(
    archive: zipfile.ZipFile,
    item: dict[str, str],
    shared_strings: list[str],
    *,
    max_rows: int,
    max_cells: int,
) -> dict[str, Any]:
    sheet_xml = _read_xml_from_zip(archive, item["path"])
    if sheet_xml is None:
        return {"name": item["name"], "path": item["path"], "ok": False, "error": "Sheet XML not found."}
    dimension = sheet_xml.find("main:dimension", _ZIP_NS)
    rows = []
    row_elements = sheet_xml.findall("main:sheetData/main:row", _ZIP_NS)
    for row in row_elements[:max_rows]:
        cells = []
        for cell in row.findall("main:c", _ZIP_NS)[:max_cells]:
            cells.append(_read_excel_cell(cell, shared_strings))
        rows.append({"row": row.attrib.get("r"), "cells": cells})
    return {
        "name": item["name"],
        "path": item["path"],
        "ok": True,
        "sheet_id": item["sheet_id"],
        "dimension": dimension.attrib.get("ref") if dimension is not None else "",
        "row_count": len(row_elements),
        "rows": rows,
    }


def _read_excel_cell(cell: ET.Element, shared_strings: list[str]) -> dict[str, Any]:
    cell_type = cell.attrib.get("t", "n")
    formula = cell.find("main:f", _ZIP_NS)
    value_node = cell.find("main:v", _ZIP_NS)
    value: Any = None
    if cell_type == "s" and value_node is not None and value_node.text is not None:
        index = int(value_node.text)
        value = shared_strings[index] if 0 <= index < len(shared_strings) else value_node.text
    elif cell_type == "inlineStr":
        value = "".join(node.text or "" for node in cell.findall(".//main:t", _ZIP_NS))
    elif cell_type == "b" and value_node is not None:
        value = value_node.text == "1"
    else:
        value = value_node.text if value_node is not None else ""
    return {
        "ref": cell.attrib.get("r", ""),
        "type": cell_type,
        "value": value,
        "formula": formula.text.strip() if formula is not None and formula.text else None,
    }


def _collect_word_paragraphs(body: ET.Element, *, max_paragraphs: int) -> list[dict[str, Any]]:
    paragraphs = []
    for paragraph in body.findall("w:p", _WORD_NS):
        text = "".join(node.text or "" for node in paragraph.findall(".//w:t", _WORD_NS)).strip()
        if not text:
            continue
        paragraphs.append({"text": text, "style": _word_paragraph_style(paragraph)})
        if len(paragraphs) >= max_paragraphs:
            break
    return paragraphs


def _word_paragraph_style(paragraph: ET.Element) -> str | None:
    style = paragraph.find("w:pPr/w:pStyle", _WORD_NS)
    return style.attrib.get("{http://schemas.openxmlformats.org/wordprocessingml/2006/main}val") if style is not None else None


def _read_ppt_slide_targets(presentation_xml: ET.Element, rels_xml: ET.Element) -> list[str]:
    rel_targets = {relation.attrib.get("Id", ""): relation.attrib.get("Target", "") for relation in rels_xml.findall("rel:Relationship", _REL_NS)}
    targets = []
    for slide in presentation_xml.findall("p:sldIdLst/p:sldId", _PPT_NS):
        rel_id = slide.attrib.get("{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id", "")
        target = rel_targets.get(rel_id, "")
        if target:
            targets.append(posixpath.normpath(f"ppt/{target.lstrip('/')}"))
    return targets


def _collect_ppt_slide_text(slide_xml: ET.Element) -> list[str]:
    texts = []
    for node in slide_xml.findall(".//a:t", _PPT_NS):
        if node.text and node.text.strip():
            texts.append(node.text.strip())
    return texts
