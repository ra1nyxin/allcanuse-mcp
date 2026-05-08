from __future__ import annotations

from allcanuse_mcp.core.microsoft import inspect_excel_workbook as inspect_excel_workbook_impl
from allcanuse_mcp.core.microsoft import inspect_powerpoint_presentation as inspect_powerpoint_presentation_impl
from allcanuse_mcp.core.microsoft import inspect_word_document as inspect_word_document_impl
from allcanuse_mcp.core.microsoft import list_installed_microsoft_software as list_installed_microsoft_software_impl
from allcanuse_mcp.descriptions import TOOL_DESCRIPTIONS


def register(mcp) -> None:
    @mcp.tool(description=TOOL_DESCRIPTIONS["list_installed_microsoft_software"])
    def list_installed_microsoft_software(max_results: int = 200) -> dict:
        return list_installed_microsoft_software_impl(max_results=max_results)

    @mcp.tool(description=TOOL_DESCRIPTIONS["inspect_excel_workbook"])
    def inspect_excel_workbook(path: str, max_sheets: int = 10, max_rows: int = 20, max_cells: int = 20) -> dict:
        return inspect_excel_workbook_impl(path, max_sheets=max_sheets, max_rows=max_rows, max_cells=max_cells)

    @mcp.tool(description=TOOL_DESCRIPTIONS["inspect_word_document"])
    def inspect_word_document(path: str, max_paragraphs: int = 20, max_tables: int = 5) -> dict:
        return inspect_word_document_impl(path, max_paragraphs=max_paragraphs, max_tables=max_tables)

    @mcp.tool(description=TOOL_DESCRIPTIONS["inspect_powerpoint_presentation"])
    def inspect_powerpoint_presentation(path: str, max_slides: int = 20) -> dict:
        return inspect_powerpoint_presentation_impl(path, max_slides=max_slides)
