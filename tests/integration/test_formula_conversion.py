"""Opt-in formula checks with cached models and no network downloads."""

from __future__ import annotations

import json
import os
import re
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from pdf_receipt import converter

FORMULA_REVISION = "ecedbe111d15c2dc60bfd4a823cbe80127b58af4"

SOURCE = Path(__file__).resolve().parents[1] / "fixtures/formulas/formula_equations.pdf"
PROSE = (
    "The first equation states the relation between three squared lengths.",
    "The squared terms belong to the equation above, not this sentence.",
    "The second equation divides one sum by another sum.",
    "The denominator is the sum of c and d. This concludes the example.",
)


def normalize_latex(text: str) -> str:
    """Ignore whitespace, thin-space commands, and braces around digit exponents."""
    text = re.sub(r"\s+", "", text).replace(r"\,", "")
    return re.sub(r"\^\{([0-9])\}", r"^\1", text)


def pin_formula_options(options):
    """Pin only the test's formula model, including engine-specific revisions."""
    spec = options.code_formula_options.model_spec.model_copy(deep=True)
    spec.revision = FORMULA_REVISION
    for override in spec.engine_overrides.values():
        override.revision = FORMULA_REVISION
    options.code_formula_options = options.code_formula_options.model_copy(
        update={"model_spec": spec})
    return options


def create_formula_runtime(profile):
    configure = converter.configure_pipeline_options

    def configure_pinned(*args, **kwargs):
        return pin_formula_options(configure(*args, **kwargs))

    with patch.object(converter, "configure_pipeline_options", side_effect=configure_pinned):
        return converter.create_docling_runtime(profile, True)


@unittest.skipUnless(
    os.environ.get("PDF_RECEIPT_RUN_FORMULA_TESTS") == "1",
    "set PDF_RECEIPT_RUN_FORMULA_TESTS=1 after caching the optional formula model",
)
class LiveFormulaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        for variable in ("HF_HUB_OFFLINE", "TRANSFORMERS_OFFLINE"):
            if os.environ.get(variable) != "1":
                raise RuntimeError(f"formula tests require {variable}=1")

    def assert_prose(self, markdown: str) -> None:
        positions = []
        for sentence in PROSE:
            self.assertEqual(markdown.count(sentence), 1)
            positions.append(markdown.index(sentence))
        self.assertEqual(positions, sorted(positions))

    def test_latex_and_surrounding_prose_in_both_profiles(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            for profile in ("fast", "quality"):
                with self.subTest(profile=profile):
                    runtime = create_formula_runtime(profile)
                    output = converter.plan_output_paths([SOURCE], Path(temp) / profile)[0][0]
                    result = converter.convert_pdf(runtime, SOURCE, output)
                    self.assertIsNone(result.report_error)
                    self.assertIsNone(result.manifest_error)
                    markdown = output.markdown.read_text(encoding="utf-8")
                    self.assert_prose(markdown)
                    self.assertNotIn("formula-not-decoded", markdown)
                    payload = json.loads(output.json.read_text(encoding="utf-8"))
                    formulas = [item["text"] for item in payload["texts"]
                                if item["label"] == "formula"]
                    self.assertEqual([normalize_latex(text) for text in formulas],
                                     ["a^2+b^2=c^2", r"x=\frac{a+b}{c+d}"])
                    blocks = list(re.finditer(r"\$\$(.*?)\$\$", markdown, re.DOTALL))
                    self.assertEqual([normalize_latex(block.group(1)) for block in blocks],
                                     [normalize_latex(text) for text in formulas])
                    for index, block in enumerate(blocks):
                        self.assertLess(markdown.index(PROSE[index * 2]), block.start())
                        self.assertLess(block.end(), markdown.index(PROSE[index * 2 + 1]))
                    print(f"Formula {profile}: {formulas}")

    def test_missing_formula_model_does_not_break_ordinary_conversion(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            with patch("docling.models.stages.code_formula.code_formula_vlm_model.create_vlm_engine",
                              side_effect=RuntimeError("Optional formula model unavailable")) as download:
                for profile in ("fast", "quality"):
                    with self.subTest(profile=profile):
                        runtime = converter.create_docling_runtime(profile, False)
                        output = converter.plan_output_paths([SOURCE], Path(temp) / profile)[0][0]
                        result = converter.convert_pdf(runtime, SOURCE, output)
                        self.assertIsNone(result.manifest_error)
                        self.assert_prose(output.markdown.read_text(encoding="utf-8"))
                download.assert_not_called()
                runtime = converter.create_docling_runtime("fast", True)
                output = converter.plan_output_paths([SOURCE], Path(temp) / "missing")[0][0]
                with self.assertRaisesRegex(Exception, "Optional formula model unavailable"):
                    converter.convert_pdf(runtime, SOURCE, output)
                self.assertFalse(json.loads((output.directory / "formula_equations_manifest.json")
                                            .read_text())["complete"])



if __name__ == "__main__":
    unittest.main()
