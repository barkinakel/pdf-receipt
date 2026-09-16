from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


class FormulaFixtureTests(unittest.TestCase):
    def test_formula_revision_is_pinned_without_changing_default_options(self) -> None:
        from docling.datamodel.pipeline_options import PdfPipelineOptions
        from tests.integration.test_formula_conversion import FORMULA_REVISION, pin_formula_options

        options = PdfPipelineOptions()
        original = options.code_formula_options.model_spec.model_dump()
        pin_formula_options(options)
        spec = options.code_formula_options.model_spec
        self.assertEqual(spec.revision, FORMULA_REVISION)
        for engine in spec.engine_overrides:
            self.assertEqual(spec.get_revision(engine), FORMULA_REVISION)
        self.assertEqual(PdfPipelineOptions().code_formula_options.model_spec.model_dump(), original)

    def test_hub_diagnostic_skips_other_versions(self) -> None:
        from tests.integration.test_hub_recovery import Hub129RecoveryTests

        with patch("tests.integration.test_hub_recovery.version", return_value="1.30.0"):
            with self.assertRaisesRegex(unittest.SkipTest, "installed 1.30.0"):
                Hub129RecoveryTests.setUpClass()
        with patch("tests.integration.test_hub_recovery.version", return_value="1.29.0"):
            Hub129RecoveryTests.setUpClass()

    def test_formula_comparison_ignores_spacing_but_keeps_mathematical_changes(self) -> None:
        from tests.integration.test_formula_conversion import normalize_latex

        self.assertEqual(normalize_latex(r"a ^ { 2 } \, + b^{2} = c^2"), "a^2+b^2=c^2")
        self.assertEqual(normalize_latex(r"x \, = \frac { a + b } { c + d }"),
                         r"x=\frac{a+b}{c+d}")
        for wrong in (r"a^3+b^2=c^2", r"a^2-b^2=c^2", r"a^2+b^2=d^2"):
            self.assertNotEqual(normalize_latex(wrong), "a^2+b^2=c^2")
        self.assertNotEqual(normalize_latex(r"x=\frac{c+d}{a+b}"), r"x=\frac{a+b}{c+d}")

    def test_checked_in_pdf_is_reproducible_from_original_generator(self) -> None:
        folder = Path(__file__).parent / "fixtures/formulas"
        spec = importlib.util.spec_from_file_location(
            "formula_fixture_generator", folder / "generate_formula_fixture.py")
        assert spec is not None and spec.loader is not None
        generator = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(generator)
        with tempfile.TemporaryDirectory() as temp:
            generated = Path(temp) / "formula.pdf"
            generator.generate(generated)
            self.assertEqual(generated.read_bytes(), (folder / "formula_equations.pdf").read_bytes())


if __name__ == "__main__":
    unittest.main()
