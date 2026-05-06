from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from allcanuse_mcp.core.c_tools import check_c_syntax
from allcanuse_mcp.core.c_tools import compile_c_program
from allcanuse_mcp.core.c_tools import format_c_code
from allcanuse_mcp.core.c_tools import generate_c_build_files
from allcanuse_mcp.core.c_tools import inspect_c_source
from allcanuse_mcp.core.c_tools import preprocess_c_source
from allcanuse_mcp.core.c_tools import scan_c_memory_risks


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

    def test_check_c_syntax_falls_back_to_clang_after_gcc_failure(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "main.c"
            source.write_text("int main(void) { return 0; }\n", encoding="utf-8")

            def fake_which(name: str) -> str | None:
                if name in {"gcc", "clang"}:
                    return f"/usr/bin/{name}"
                return None

            def fake_run(command, **_kwargs):
                if command[0].endswith("gcc"):
                    return {"ok": False, "returncode": 1, "stdout": "", "stderr": "syntax failed"}
                return {"ok": True, "returncode": 0, "stdout": "", "stderr": ""}

            with patch("allcanuse_mcp.core.c_tools.shutil.which", side_effect=fake_which), patch(
                "allcanuse_mcp.core.c_tools.run_command",
                side_effect=fake_run,
            ):
                result = check_c_syntax([str(source)], cwd=str(root))

        self.assertTrue(result["ok"])
        self.assertEqual(result["backend"], "clang")
        self.assertEqual(result["attempts"][0]["backend"], "gcc")
        self.assertFalse(result["attempts"][0]["ok"])

    def test_preprocess_c_source_returns_expanded_source(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "main.c"
            source.write_text("#define ANSWER 42\nint value = ANSWER;\n", encoding="utf-8")

            with patch("allcanuse_mcp.core.c_tools.shutil.which", side_effect=lambda name: "/usr/bin/gcc" if name == "gcc" else None), patch(
                "allcanuse_mcp.core.c_tools.run_command",
                return_value={"ok": True, "returncode": 0, "stdout": "int value = 42;\n", "stderr": "", "stdout_truncated": False},
            ):
                result = preprocess_c_source(str(source), cwd=str(root))

        self.assertTrue(result["ok"])
        self.assertEqual(result["backend"], "gcc")
        self.assertIn("42", result["preprocessed_source"])

    def test_scan_c_memory_risks_reports_high_risk_calls(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp, "unsafe.c")
            source.write_text(
                '#include <stdio.h>\nvoid f(char *dst, char *src) { strcpy(dst, src); scanf("%s", dst); scanf("%16s", dst); }\n',
                encoding="utf-8",
            )

            result = scan_c_memory_risks([str(source)])

        self.assertTrue(result["ok"])
        symbols = [item["symbol"] for item in result["findings"]]
        self.assertIn("strcpy", symbols)
        self.assertEqual(symbols.count("scanf"), 1)

    def test_generate_c_build_files_skips_existing_without_overwrite(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "main.c"
            source.write_text("int main(void) { return 0; }\n", encoding="utf-8")
            (root / "Makefile").write_text("custom\n", encoding="utf-8")

            result = generate_c_build_files(str(root), project_name="demo", source_files=["main.c"])

            cmake = (root / "CMakeLists.txt").read_text(encoding="utf-8")
            makefile = (root / "Makefile").read_text(encoding="utf-8")

        self.assertTrue(result["ok"])
        self.assertTrue(any(item["path"].endswith("CMakeLists.txt") for item in result["generated"]))
        self.assertTrue(any(item["path"].endswith("Makefile") for item in result["skipped"]))
        self.assertIn("add_executable(demo", cmake)
        self.assertEqual(makefile, "custom\n")


if __name__ == "__main__":
    unittest.main()
