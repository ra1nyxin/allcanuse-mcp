from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from allcanuse_mcp.core.asset_optimization import optimize_images_for_memory
from allcanuse_mcp.core.seo_tools import audit_seo


class SeoAndOptimizationTests(unittest.TestCase):
    def test_audit_seo_reports_common_html_issues(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            html = root / "index.html"
            html.write_text(
                """
                <!doctype html>
                <html>
                <head><title>Short</title></head>
                <body>
                  <h1>Main</h1>
                  <h1>Duplicate</h1>
                  <img src="hero.png">
                </body>
                </html>
                """,
                encoding="utf-8",
            )

            result = audit_seo(str(root))

        self.assertTrue(result["ok"])
        self.assertEqual(result["page_count"], 1)
        codes = {issue["code"] for issue in result["issues"]}
        self.assertIn("short_title", codes)
        self.assertIn("missing_meta_description", codes)
        self.assertIn("multiple_h1", codes)
        self.assertIn("images_missing_alt", codes)
        self.assertIn("missing_html_lang", codes)

    def test_optimize_images_for_memory_writes_non_destructive_output(self) -> None:
        try:
            from PIL import Image
        except Exception:
            self.skipTest("Pillow is not installed")

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "sample.png"
            Image.new("RGB", (64, 64), (32, 96, 160)).save(source)

            result = optimize_images_for_memory([str(source)], quality=85)

            self.assertTrue(result["ok"])
            self.assertEqual(result["optimized_count"], 1)
            item = result["results"][0]
            output = Path(item["output_path"])
            self.assertTrue(output.exists())
            self.assertNotEqual(output, source)
            self.assertFalse(item["overwrote_source"])
            self.assertEqual(item["original_dimensions"], [64, 64])
            self.assertEqual(item["optimized_dimensions"], [64, 64])


if __name__ == "__main__":
    unittest.main()
