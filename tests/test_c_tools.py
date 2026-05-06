from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from allcanuse_mcp.core.c_tools import check_c_syntax
from allcanuse_mcp.core.c_tools import compile_c_program
from allcanuse_mcp.core.c_tools import format_c_code
from allcanuse_mcp.core.c_tools import evaluate_c_math_expression
from allcanuse_mcp.core.c_tools import generate_c_fixed_point_header
from allcanuse_mcp.core.c_tools import generate_c_lookup_table_header
from allcanuse_mcp.core.c_tools import generate_c_matrix_math_header
from allcanuse_mcp.core.c_tools import generate_c_math_utils_header
from allcanuse_mcp.core.c_tools import generate_c_build_files
from allcanuse_mcp.core.c_tools import generate_c_numeric_test_harness
from allcanuse_mcp.core.c_tools import generate_c_polynomial_eval_header
from allcanuse_mcp.core.c_tools import generate_c_statistics_header
from allcanuse_mcp.core.c_tools import generate_c_vector_math_header
from allcanuse_mcp.core.c_tools import inspect_c_source
from allcanuse_mcp.core.c_tools import preprocess_c_source
from allcanuse_mcp.core.c_tools import scan_c_memory_risks
from allcanuse_mcp.core.c_tools import scan_c_numeric_risks


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

    def test_scan_c_numeric_risks_reports_math_pitfalls(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp, "math.c")
            source.write_text(
                "double a = 1 / 2;\nint same(double x, double y) { return x == y; }\ndouble y = pow(x, 2);\ndouble p = M_PI;\n",
                encoding="utf-8",
            )

            result = scan_c_numeric_risks([str(source)])

        self.assertTrue(result["ok"])
        codes = {item["code"] for item in result["findings"]}
        self.assertIn("integer_division_assigned_to_float", codes)
        self.assertIn("float_equality", codes)
        self.assertIn("pow_square", codes)
        self.assertIn("nonportable_m_pi", codes)

    def test_scan_c_numeric_risks_uses_file_level_math_include(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp, "math.c")
            source.write_text("#include <math.h>\nfloat y = powf(x, 2.0f);\n", encoding="utf-8")

            result = scan_c_numeric_risks([str(source)])

        codes = {item["code"] for item in result["findings"]}
        self.assertIn("pow_square", codes)
        self.assertNotIn("math_function_linkage", codes)

    def test_evaluate_c_math_expression_uses_default_link_after_libm_failure(self) -> None:
        def fake_compile(source_files, **kwargs):
            if kwargs.get("libraries") == ["m"]:
                return {"ok": False, "attempts": [{"backend": "gcc", "ok": False}]}
            return {
                "ok": True,
                "backend": "gcc",
                "attempts": [{"backend": "gcc", "ok": True}],
                "run_result": {"ok": True, "stdout": "1\n", "stderr": "", "returncode": 0},
            }

        with patch("allcanuse_mcp.core.c_tools.compile_c_program", side_effect=fake_compile):
            result = evaluate_c_math_expression("sin(x) * sin(x) + cos(x) * cos(x)", variables={"x": 0.5})

        self.assertTrue(result["ok"])
        self.assertEqual(result["link_backend"], "default")
        self.assertEqual(result["value"], 1.0)
        self.assertEqual(result["attempts"][0]["backend"], "libm")

    def test_generate_c_numeric_test_harness_writes_tolerance_checks(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp, "test_numeric.c")
            result = generate_c_numeric_test_harness(
                str(target),
                function_name="hypot2",
                include_path="mathlib.h",
                cases=[{"args": [3, 4], "expected": 5}],
            )
            text = target.read_text(encoding="utf-8")

        self.assertTrue(result["ok"])
        self.assertIn('#include "mathlib.h"', text)
        self.assertIn("hypot2(3", text)
        self.assertIn("fabs(actual - expected)", text)

    def test_generate_c_math_utils_header_writes_prefixed_helpers(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp, "acu_math_utils.h")
            result = generate_c_math_utils_header(str(target), prefix="acu")
            text = target.read_text(encoding="utf-8")

        self.assertTrue(result["ok"])
        self.assertIn("static inline double acu_clamp", text)
        self.assertIn("static inline int acu_nearly_equal", text)

    def test_generate_c_vector_math_header_writes_vec3_helpers(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp, "vec.h")
            result = generate_c_vector_math_header(str(target), prefix="acu", dimensions=[3])
            text = target.read_text(encoding="utf-8")

        self.assertTrue(result["ok"])
        self.assertEqual(result["dimensions"], [3])
        self.assertIn("typedef struct acu_vec3", text)
        self.assertIn("static inline acu_vec3 acu_vec3_cross", text)
        self.assertNotIn("acu_vec2_make", text)

    def test_generate_c_lookup_table_header_writes_samples(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp, "sin_lut.h")
            result = generate_c_lookup_table_header(
                str(target),
                table_name="sin_lut",
                function="sin",
                start=0.0,
                end=1.5707963267948966,
                samples=3,
                value_type="float",
            )
            text = target.read_text(encoding="utf-8")

        self.assertTrue(result["ok"])
        self.assertEqual(result["samples"], 3)
        self.assertIn("#define SIN_LUT_COUNT 3", text)
        self.assertIn("static const float sin_lut[3]", text)
        self.assertIn("1f", text)

    def test_generate_c_polynomial_eval_header_uses_horner_form(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp, "poly.h")
            result = generate_c_polynomial_eval_header(
                str(target),
                function_name="poly_eval",
                coefficients=[1, 2, 3],
            )
            text = target.read_text(encoding="utf-8")

        self.assertTrue(result["ok"])
        self.assertEqual(result["degree"], 2)
        self.assertIn("static inline double poly_eval(double x)", text)
        self.assertIn("double result = 3", text)
        self.assertIn("result = result * x + 2", text)
        self.assertIn("result = result * x + 1", text)

    def test_generate_c_matrix_math_header_writes_mat3_helpers(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp, "matrix.h")
            result = generate_c_matrix_math_header(str(target), prefix="acu", dimensions=[2, 3])
            text = target.read_text(encoding="utf-8")

        self.assertTrue(result["ok"])
        self.assertIn("typedef struct acu_mat2", text)
        self.assertIn("static inline double acu_mat3_det", text)
        self.assertIn("acu_mat2_identity", text)

    def test_generate_c_statistics_header_writes_array_helpers(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp, "stats.h")
            result = generate_c_statistics_header(str(target), prefix="acu")
            text = target.read_text(encoding="utf-8")

        self.assertTrue(result["ok"])
        self.assertIn("static inline double acu_mean", text)
        self.assertIn("static inline double acu_variance", text)
        self.assertIn("static inline double acu_rms", text)

    def test_generate_c_fixed_point_header_writes_q_helpers(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp, "q.h")
            result = generate_c_fixed_point_header(str(target), prefix="acu", fraction_bits=12)
            text = target.read_text(encoding="utf-8")

        self.assertTrue(result["ok"])
        self.assertEqual(result["fraction_bits"], 12)
        self.assertIn("#define ACU_Q_FRACTION_BITS 12", text)
        self.assertIn("typedef int32_t acu_q", text)
        self.assertIn("acu_q_mul", text)


if __name__ == "__main__":
    unittest.main()
