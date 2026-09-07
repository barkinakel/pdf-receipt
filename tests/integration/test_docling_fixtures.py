from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from pdftomd import converter
from tests.fixture_harness import assert_markdown_facts, load_fixture_cases

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"
RUN_LIVE = os.environ.get("PDFTOMD_RUN_DOCLING_FIXTURES") == "1"


@unittest.skipUnless(
    RUN_LIVE,
    "set PDFTOMD_RUN_DOCLING_FIXTURES=1 after caching Docling models",
)
class LiveDoclingFixtureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        if os.environ.get("HF_HUB_OFFLINE") != "1":
            raise RuntimeError("live fixture tests require HF_HUB_OFFLINE=1")
        if os.environ.get("TRANSFORMERS_OFFLINE") != "1":
            raise RuntimeError("live fixture tests require TRANSFORMERS_OFFLINE=1")
        cls.runtime = converter.create_docling_runtime(
            "quality", formula=False, report=True
        )

    def test_fixture_facts_against_live_docling_output(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_root = Path(temp_dir).resolve()
            for case in load_fixture_cases(FIXTURES):
                with self.subTest(fixture=case.name):
                    outputs, _ = converter.plan_output_paths(
                        [case.pdf_path], output_root / case.name
                    )
                    result = converter.convert_pdf(
                        self.runtime, case.pdf_path, outputs[0]
                    )
                    self.assertIsNone(result.report_error)
                    self.assertIsNotNone(result.report_summary)
                    self.assertTrue(result.output.report.is_file())
                    markdown_path = result.output.markdown
                    assert_markdown_facts(
                        case,
                        markdown_path.read_text(encoding="utf-8"),
                        markdown_path=markdown_path,
                    )


if __name__ == "__main__":
    unittest.main()
