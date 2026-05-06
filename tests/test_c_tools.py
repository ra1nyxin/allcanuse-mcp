from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from allcanuse_mcp.core.c_tools import compile_c_program
from allcanuse_mcp.core.c_tools import format_c_code
from allcanuse_mcp.core.c_tools import inspect_c_source


class CToolsTests(unittest.TestCase):
    def test_inspect_c_source_reports_includes_defines_and_functions(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp, "main.c")
            source.write_text(
                '#include <stdio.h>\n#define ANSWER 42\nint add(int a, int b);\nint main(void) { return add(1, 2); }\n',
                encoding="utf-8",
            )

            result = inspect_c_source([str(source)])

        self.assertTrue(result["ok"])
        self.assertEqual(result["totals"]["files"], 1)
        item = result["files"][0]
        self.assertEqual(item["includes"][0]["name"], "stdio.h")
        self.assertEqual(item["defines"][0]["name"], "ANSWER")
        self.assertIn("main", {function["name"] for function in item["functions"]})

    def test_format_c_code_falls_back_to_basic_cleanup(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp, "main.c")
            source.write_text("int main(void) { return 0; }   \n\n", encoding="utf-8")

            with patch("allcanuse_mcp.core.c_tools.shutil.which", return_value=None):
                result = format_c_code([str(source)], in_place=False)

        self.assertTrue(result["ok"])
        item = result["results"][0]
        self.assertEqual(item["backend"], "basic-cleanup")
        self.assertEqual(item["formatted_text"], "int main(void) { return 0; }\n")

    def test_compile_c_program_falls_back_to_clang_after_gcc_failure(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "main.c"
            output = root / "app"
            source.write_text("int main(void) { return 0; }\n", encoding="utf-8")

            def fake_which(name: str) -> str | None:
                if name in {"gcc", "clang"}:
                    return f"/usr/bin/{name}"
                return None

            def fake_run(command, **_kwargs):
                if command[0].endswith("gcc"):
                    return {"ok": False, "returncode": 1, "stdout": "", "stderr": "gcc failed"}
                if command[0].endswith("clang"):
                    output.write_bytes(b"binary")
                    return {"ok": True, "returncode": 0, "stdout": "", "stderr": ""}
                return {"ok": False, "returncode": 127, "stdout": "", "stderr": "unexpected"}

            with patch("allcanuse_mcp.core.c_tools.shutil.which", side_effect=fake_which), patch(
                "allcanuse_mcp.core.c_tools.run_command",
                side_effect=fake_run,
            ):
                result = compile_c_program([str(source)], output_path=str(output), cwd=str(root))

            self.assertTrue(result["ok"])
            self.assertEqual(result["backend"], "clang")
            self.assertEqual(result["attempts"][0]["backend"], "gcc")
            self.assertFalse(result["attempts"][0]["ok"])
            self.assertTrue(output.exists())


if __name__ == "__main__":
    unittest.main()
