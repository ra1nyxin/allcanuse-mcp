from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from allcanuse_mcp.core.filesystem import copy_path
from allcanuse_mcp.core.filesystem import delete_path
from allcanuse_mcp.core.filesystem import extract_archive
from allcanuse_mcp.core.filesystem import hash_file
from allcanuse_mcp.core.filesystem import list_desktop_files
from allcanuse_mcp.core.filesystem import list_recent_files
from allcanuse_mcp.core.filesystem import mkdir_path
from allcanuse_mcp.core.filesystem import move_path
from allcanuse_mcp.core.filesystem import patch_lines_in_file
from allcanuse_mcp.core.filesystem import read_binary_file
from allcanuse_mcp.core.filesystem import read_text_file
from allcanuse_mcp.core.filesystem import read_json_file
from allcanuse_mcp.core.filesystem import replace_text_in_file
from allcanuse_mcp.core.filesystem import search_text
from allcanuse_mcp.core.filesystem import stat_path
from allcanuse_mcp.core.filesystem import which_command
from allcanuse_mcp.core.filesystem import write_binary_file
from allcanuse_mcp.core.filesystem import write_json_file
from allcanuse_mcp.core.filesystem import write_text_file
from allcanuse_mcp.core.filesystem import zip_paths
from unittest.mock import patch


class FilesystemTests(unittest.TestCase):
    def test_mkdir_reports_existing_state(self) -> None:
        base = Path(tempfile.gettempdir(), "allcanuse-mkdir-test")
        if base.exists():
            delete_path(str(base), recursive=True, missing_ok=True)
        first = mkdir_path(str(base))
        second = mkdir_path(str(base))
        self.assertTrue(first["created"])
        self.assertFalse(second["created"])
        delete_path(str(base), recursive=True, missing_ok=True)

    def test_move_path_overwrite_file(self) -> None:
        base = Path(tempfile.gettempdir(), "allcanuse-move-test")
        mkdir_path(str(base))
        src = base / "src.txt"
        dst = base / "dst.txt"
        src.write_text("new", encoding="utf-8")
        dst.write_text("old", encoding="utf-8")
        result = move_path(str(src), str(dst), overwrite=True)
        self.assertTrue(result["exists"])
        self.assertEqual(dst.read_text(encoding="utf-8"), "new")
        delete_path(str(base), recursive=True, missing_ok=True)

    def test_delete_path_missing_ok(self) -> None:
        missing = Path(tempfile.gettempdir(), "allcanuse-missing-test")
        result = delete_path(str(missing), missing_ok=True)
        self.assertTrue(result["missing"])

    def test_zip_and_extract_paths(self) -> None:
        base = Path(tempfile.gettempdir(), "allcanuse-archive-test")
        source_dir = base / "src"
        out_dir = base / "out"
        archive = base / "bundle.zip"
        mkdir_path(str(source_dir))
        (source_dir / "a.txt").write_text("hello", encoding="utf-8")
        zipped = zip_paths([str(source_dir)], str(archive))
        self.assertTrue(Path(zipped["destination"]).exists())
        extracted = extract_archive(str(archive), str(out_dir))
        self.assertGreaterEqual(extracted["extracted_entries"], 1)
        self.assertTrue((out_dir / "src" / "a.txt").exists())
        delete_path(str(base), recursive=True, missing_ok=True)

    def test_list_desktop_files_not_found(self) -> None:
        with patch("allcanuse_mcp.core.filesystem.Path.home", return_value=Path(tempfile.gettempdir(), "missing-home")), patch.dict(
            "allcanuse_mcp.core.filesystem.os.environ",
            {"USERPROFILE": str(Path(tempfile.gettempdir(), "missing-profile"))},
            clear=False,
        ):
            result = list_desktop_files()
        self.assertFalse(result["exists"])

    def test_binary_copy_hash_and_stat_tools(self) -> None:
        base = Path(tempfile.gettempdir(), "allcanuse-binary-test")
        mkdir_path(str(base))
        original = base / "sample.bin"
        copied = base / "copy.bin"

        write_binary_file(str(original), "AAECAw==")
        binary = read_binary_file(str(original))
        self.assertEqual(binary["encoding"], "base64")

        copied_result = copy_path(str(original), str(copied))
        self.assertTrue(copied_result["exists"])

        digest = hash_file(str(original))
        self.assertEqual(digest["algorithm"], "sha256")

        stat = stat_path(str(original))
        self.assertTrue(stat["is_file"])

        recent = list_recent_files(str(base), limit=5)
        self.assertGreaterEqual(recent["count"], 1)

        delete_path(str(base), recursive=True, missing_ok=True)

    def test_json_and_which_command_tools(self) -> None:
        base = Path(tempfile.gettempdir(), "allcanuse-json-test")
        mkdir_path(str(base))
        target = base / "data.json"
        write_json_file(str(target), {"name": "allcanuse", "ok": True})
        data = read_json_file(str(target))
        self.assertEqual(data["data"]["name"], "allcanuse")
        which = which_command("python")
        self.assertTrue(which["found"])
        delete_path(str(base), recursive=True, missing_ok=True)

    def test_read_text_file_supports_line_ranges(self) -> None:
        base = Path(tempfile.gettempdir(), "allcanuse-read-text-test")
        if base.exists():
            delete_path(str(base), recursive=True, missing_ok=True)
        mkdir_path(str(base))
        target = base / "sample.txt"
        write_text_file(str(target), "line1\nline2\nline3\nline4\n")

        result = read_text_file(str(target), start_line=2, end_line=3)
        self.assertEqual(result["total_lines"], 4)
        self.assertEqual(result["start_line"], 2)
        self.assertEqual(result["end_line"], 3)
        self.assertEqual(result["content"], "line2\nline3\n")

        delete_path(str(base), recursive=True, missing_ok=True)

    def test_patch_lines_and_replace_text_update_expected_content(self) -> None:
        base = Path(tempfile.gettempdir(), "allcanuse-patch-test")
        if base.exists():
            delete_path(str(base), recursive=True, missing_ok=True)
        mkdir_path(str(base))
        target = base / "module.py"
        write_text_file(str(target), "a = 1\nb = 2\nc = 3\n")

        patched = patch_lines_in_file(
            str(target),
            start_line=2,
            end_line=2,
            new_text="b = 20\n",
        )
        self.assertEqual(patched["new_line_count"], 1)
        self.assertEqual(target.read_text(encoding="utf-8"), "a = 1\nb = 20\nc = 3\n")

        replaced = replace_text_in_file(
            str(target),
            old_text="c = 3",
            new_text="c = 30",
            count=1,
        )
        self.assertEqual(replaced["replacements"], 1)
        self.assertIn("c = 30", target.read_text(encoding="utf-8"))

        delete_path(str(base), recursive=True, missing_ok=True)

    def test_search_text_supports_pattern_and_regex(self) -> None:
        base = Path(tempfile.gettempdir(), "allcanuse-search-test")
        if base.exists():
            delete_path(str(base), recursive=True, missing_ok=True)
        source = base / "src"
        mkdir_path(str(source))
        write_text_file(str(source / "app.py"), "def alpha():\n    return 1\n")
        write_text_file(str(source / "notes.txt"), "alpha appears here too\n")

        literal = search_text(str(source), query="alpha", file_pattern="*.py")
        self.assertEqual(literal["count"], 1)
        self.assertEqual(literal["matches"][0]["relative_path"], "app.py")

        regex = search_text(str(source), query=r"def\s+\w+\(", use_regex=True, file_pattern="*.py")
        self.assertEqual(regex["count"], 1)
        self.assertEqual(regex["matches"][0]["line_number"], 1)

        delete_path(str(base), recursive=True, missing_ok=True)


if __name__ == "__main__":
    unittest.main()
