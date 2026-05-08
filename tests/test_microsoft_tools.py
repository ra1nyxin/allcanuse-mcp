from __future__ import annotations

import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from allcanuse_mcp.core import microsoft


class MicrosoftToolTests(unittest.TestCase):
    def test_list_installed_microsoft_software_uses_windows_inventory(self) -> None:
        with patch("allcanuse_mcp.core.microsoft.platform.system", return_value="Windows"), patch(
            "allcanuse_mcp.core.microsoft.winreg", object()
        ), patch(
            "allcanuse_mcp.core.microsoft._windows_registry_microsoft_software_entries",
            return_value=[{"name": "Microsoft Excel", "version": "16.0"}],
        ):
            result = microsoft.list_installed_microsoft_software(max_results=5)

        self.assertTrue(result["ok"])
        self.assertEqual(result["count"], 1)
        self.assertEqual(result["entries"][0]["name"], "Microsoft Excel")

    def test_inspect_excel_workbook_reads_sheet_samples(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workbook = Path(tmp, "sample.xlsx")
            with zipfile.ZipFile(workbook, "w") as archive:
                archive.writestr(
                    "xl/workbook.xml",
                    """<?xml version="1.0" encoding="UTF-8"?>
                    <workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"
                              xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
                      <sheets>
                        <sheet name="Sheet1" sheetId="1" r:id="rId1"/>
                      </sheets>
                    </workbook>""",
                )
                archive.writestr(
                    "xl/_rels/workbook.xml.rels",
                    """<?xml version="1.0" encoding="UTF-8"?>
                    <Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
                      <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>
                    </Relationships>""",
                )
                archive.writestr(
                    "xl/sharedStrings.xml",
                    """<?xml version="1.0" encoding="UTF-8"?>
                    <sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" count="1" uniqueCount="1">
                      <si><t>Hello</t></si>
                    </sst>""",
                )
                archive.writestr(
                    "xl/worksheets/sheet1.xml",
                    """<?xml version="1.0" encoding="UTF-8"?>
                    <worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
                      <dimension ref="A1:B2"/>
                      <sheetData>
                        <row r="1">
                          <c r="A1" t="s"><v>0</v></c>
                          <c r="B1"><v>42</v></c>
                        </row>
                        <row r="2">
                          <c r="A2" t="inlineStr"><is><t>World</t></is></c>
                        </row>
                      </sheetData>
                    </worksheet>""",
                )
                archive.writestr("docProps/core.xml", "<cp:coreProperties xmlns:cp=\"http://schemas.openxmlformats.org/package/2006/metadata/core-properties\"/>")

            result = microsoft.inspect_excel_workbook(str(workbook), max_sheets=1, max_rows=2, max_cells=2)

        self.assertTrue(result["ok"])
        self.assertEqual(result["sheet_count"], 1)
        sheet = result["sheets"][0]
        self.assertEqual(sheet["name"], "Sheet1")
        self.assertEqual(sheet["dimension"], "A1:B2")
        self.assertEqual(sheet["rows"][0]["cells"][0]["value"], "Hello")
        self.assertEqual(sheet["rows"][1]["cells"][0]["value"], "World")

    def test_inspect_word_document_reads_paragraphs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            document = Path(tmp, "sample.docx")
            with zipfile.ZipFile(document, "w") as archive:
                archive.writestr(
                    "word/document.xml",
                    """<?xml version="1.0" encoding="UTF-8"?>
                    <w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
                      <w:body>
                        <w:p><w:r><w:t>Hello Word</w:t></w:r></w:p>
                        <w:p><w:r><w:t>Second paragraph</w:t></w:r></w:p>
                        <w:tbl/>
                      </w:body>
                    </w:document>""",
                )
                archive.writestr("docProps/core.xml", "<cp:coreProperties xmlns:cp=\"http://schemas.openxmlformats.org/package/2006/metadata/core-properties\"/>")

            result = microsoft.inspect_word_document(str(document), max_paragraphs=2)

        self.assertTrue(result["ok"])
        self.assertEqual(result["paragraph_count"], 2)
        self.assertEqual(result["table_count"], 1)
        self.assertEqual(result["paragraphs"][0]["text"], "Hello Word")

    def test_inspect_powerpoint_presentation_reads_slide_text(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            presentation = Path(tmp, "sample.pptx")
            with zipfile.ZipFile(presentation, "w") as archive:
                archive.writestr(
                    "ppt/presentation.xml",
                    """<?xml version="1.0" encoding="UTF-8"?>
                    <p:presentation xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"
                                    xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
                      <p:sldIdLst>
                        <p:sldId id="256" r:id="rId1"/>
                      </p:sldIdLst>
                    </p:presentation>""",
                )
                archive.writestr(
                    "ppt/_rels/presentation.xml.rels",
                    """<?xml version="1.0" encoding="UTF-8"?>
                    <Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
                      <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slide" Target="slides/slide1.xml"/>
                    </Relationships>""",
                )
                archive.writestr(
                    "ppt/slides/slide1.xml",
                    """<?xml version="1.0" encoding="UTF-8"?>
                    <p:sld xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"
                           xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main">
                      <p:cSld>
                        <p:spTree>
                          <p:sp>
                            <p:txBody>
                              <a:p><a:r><a:t>Slide Title</a:t></a:r></a:p>
                              <a:p><a:r><a:t>Slide Body</a:t></a:r></a:p>
                            </p:txBody>
                          </p:sp>
                        </p:spTree>
                      </p:cSld>
                    </p:sld>""",
                )
                archive.writestr("docProps/core.xml", "<cp:coreProperties xmlns:cp=\"http://schemas.openxmlformats.org/package/2006/metadata/core-properties\"/>")

            result = microsoft.inspect_powerpoint_presentation(str(presentation))

        self.assertTrue(result["ok"])
        self.assertEqual(result["slide_count"], 1)
        self.assertEqual(result["slides"][0]["title"], "Slide Title")
        self.assertEqual(result["slides"][0]["texts"][1], "Slide Body")


if __name__ == "__main__":
    unittest.main()
