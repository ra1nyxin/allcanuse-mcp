from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from allcanuse_mcp.core.filesystem import delete_path
from allcanuse_mcp.core.filesystem import find_files
from allcanuse_mcp.core.filesystem import mkdir_path
from allcanuse_mcp.core.filesystem import search_text


class SearchToolTests(unittest.TestCase):
    def test_find_files_matches_pattern(self) -> None:
        base = Path(tempfile.gettempdir(), "allcanuse-find-files-test")
        mkdir_path(str(base / "a"))
        (base / "a" / "main.py").write_text("print('ok')", encoding="utf-8")
        (base / "a" / "README.md").write_text("# readme", encoding="utf-8")
        result = find_files(str(base), pattern="*.py", max_depth=3)
        self.assertEqual(result["count"], 1)
        self.assertTrue(result["matches"][0]["path"].endswith("main.py"))
        delete_path(str(base), recursive=True, missing_ok=True)

    def test_search_text_plain_and_regex(self) -> None:
        base = Path(tempfile.gettempdir(), "allcanuse-search-text-test")
        mkdir_path(str(base))
        file_path = base / "notes.txt"
        file_path.write_text("hello world\nTODO item\nclass Demo\n", encoding="utf-8")

        plain = search_text(str(base), query="TODO")
        regex = search_text(str(base), query=r"class\s+\w+", use_regex=True)

        self.assertEqual(plain["count"], 1)
        self.assertEqual(regex["count"], 1)
        delete_path(str(base), recursive=True, missing_ok=True)


if __name__ == "__main__":
    unittest.main()
