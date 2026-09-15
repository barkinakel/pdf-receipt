from __future__ import annotations

import json
import os
import re
import tempfile
import unittest
from pathlib import Path

from pdf_receipt import converter, manifest
from pdf_receipt import quality_report
from tests.fixture_harness import assert_markdown_facts, load_fixture_cases

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"
RUN_LIVE = os.environ.get("PDF_RECEIPT_RUN_DOCLING_FIXTURES") == "1"
DROP_CAP_COMPLETE = "This chapter begins with a decorative drop cap"
DROP_CAP_REMAINDER = "his chapter begins with a decorative drop cap."


def _assert_adjacent(test: unittest.TestCase, texts: list[str], stage: str) -> None:
    cap_index = texts.index("T")
    test.assertEqual(
        texts[cap_index : cap_index + 2],
        ["T", DROP_CAP_REMAINDER],
        f"drop-cap fragments are no longer adjacent at the {stage} stage",
    )


def _contains_complete_drop_cap(texts: list[str]) -> bool:
    return any(DROP_CAP_COMPLETE in text for text in texts)


@unittest.skipUnless(
    RUN_LIVE,
    "set PDF_RECEIPT_RUN_DOCLING_FIXTURES=1 after caching Docling models",
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

    def test_manifest_reuses_real_exports_and_rejects_changed_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            source = FIXTURES / "structure_layout.pdf"
            output = converter.plan_output_paths([source], Path(temp_dir))[0][0]
            result = converter.convert_pdf(self.runtime, source, output)
            self.assertIsNone(result.report_error)
            self.assertIsNone(result.manifest_error)
            options = manifest.settings("quality", False, 1.0, True)
            self.assertTrue(manifest.reusable(source, output, options))
            payload = json.loads(manifest.manifest_path(output).read_text())
            artifact = output.directory / payload["outputs"]["artifact_paths"][0]
            artifact.write_bytes(b"broken")
            self.assertFalse(manifest.reusable(source, output, options))

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
                    self.assertIn("Structure: PASS", result.report_summary)
                    self.assertTrue(result.output.report.is_file())
                    markdown_path = result.output.markdown
                    assert_markdown_facts(
                        case,
                        markdown_path.read_text(encoding="utf-8"),
                        markdown_path=markdown_path,
                    )
                    if "images" in case.features:
                        report_text = result.output.report.read_text(encoding="utf-8")
                        self.assertRegex(report_text, re.compile(r"\d+ × \d+"))
                    if "decorative_drop_cap" in case.features:
                        source = quality_report.read_pdf_text(case.pdf_path)
                        markdown = markdown_path.read_text(encoding="utf-8")
                        self.assertIn(f"{DROP_CAP_COMPLETE}.", source.pages[0])
                        if DROP_CAP_COMPLETE not in markdown:
                            payload = json.loads(
                                result.output.json.read_text(encoding="utf-8")
                            )
                            texts_by_ref = {
                                item["self_ref"]: item
                                for item in payload.get("texts", ())
                            }
                            items_by_text = {
                                item.get("text"): item
                                for item in texts_by_ref.values()
                            }
                            cap = items_by_text["T"]
                            remainder = items_by_text[DROP_CAP_REMAINDER]
                            for item in (cap, remainder):
                                self.assertEqual(item["label"], "text")
                                self.assertEqual(item["content_layer"], "body")

                            body_refs = [
                                child["$ref"]
                                for child in payload["body"]["children"]
                            ]
                            cap_index = body_refs.index(cap["self_ref"])
                            remainder_index = body_refs.index(remainder["self_ref"])
                            intervening = body_refs[cap_index + 1 : remainder_index]
                            self.assertTrue(
                                any(ref.startswith("#/pictures/") for ref in intervening)
                            )
                            self.assertIn(
                                items_by_text["Right column third"]["self_ref"],
                                intervening,
                            )
                            self.assertIn(
                                items_by_text["Right column fourth"]["self_ref"],
                                intervening,
                            )

                            cap_match = re.search(r"(?m)^T\s*$", markdown)
                            self.assertIsNotNone(cap_match)
                            assert cap_match is not None
                            image_match = re.search(
                                r"!\[[^\]]*\]\([^)]+\)",
                                markdown[cap_match.end() :],
                            )
                            self.assertIsNotNone(image_match)
                            assert image_match is not None
                            markdown_positions = [
                                cap_match.start(),
                                cap_match.end() + image_match.start(),
                                markdown.index("Right column third"),
                                markdown.index("Right column fourth"),
                                markdown.index(DROP_CAP_REMAINDER),
                            ]
                            self.assertEqual(
                                markdown_positions,
                                sorted(markdown_positions),
                            )

    def test_image_scales_increase_dimensions_and_preserve_links(self) -> None:
        from PIL import Image

        case = next(case for case in load_fixture_cases(FIXTURES)
                    if case.pdf_path.name == "structure_layout.pdf")
        with tempfile.TemporaryDirectory() as temp_dir:
            for profile in ("fast", "quality"):
                baseline = None
                for scale in (1.0, 1.5, 2.0, 3.0):
                    with self.subTest(profile=profile, scale=scale):
                        runtime = converter.create_docling_runtime(
                            profile, False, report=False, image_scale=scale)
                        outputs, _ = converter.plan_output_paths(
                            [case.pdf_path], Path(temp_dir) / f"{profile}_{scale}")
                        result = converter.convert_pdf(runtime, case.pdf_path, outputs[0])
                        markdown = result.output.markdown.read_text(encoding="utf-8")
                        links = re.findall(r"!\[[^\]]*\]\(([^)]+)\)", markdown)
                        self.assertTrue(links)
                        dimensions = []
                        for link in links:
                            self.assertNotIn("\\", link)
                            path = result.output.directory / link
                            self.assertTrue(path.resolve().is_relative_to(result.output.directory.resolve()))
                            with Image.open(path) as image:
                                image.load()
                                dimensions.append(image.size)
                        if baseline is None:
                            baseline = dimensions
                        self.assertEqual(len(dimensions), len(baseline))
                        for original, scaled in zip(baseline, dimensions):
                            for before, after in zip(original, scaled):
                                self.assertAlmostEqual(after, before * scale, delta=2)
                        self.assertGreater(result.artifact_bytes, 0)
                        print(f"Image scale {profile} {scale}: {dimensions}; "
                              f"{result.duration_seconds:.2f} s; {result.artifact_bytes} bytes")

    def test_drop_cap_pipeline_stage_diagnosis(self) -> None:
        from docling.datamodel.base_models import InputFormat
        from docling.datamodel.pipeline_options import PdfPipelineOptions
        from docling.document_converter import DocumentConverter, PdfFormatOption

        options = converter.configure_pipeline_options(
            PdfPipelineOptions(), "quality", False
        )
        options.generate_parsed_pages = True
        diagnostic_converter = DocumentConverter(
            format_options={
                InputFormat.PDF: PdfFormatOption(pipeline_options=options),
            }
        )
        result = diagnostic_converter.convert(FIXTURES / "structure_layout.pdf")
        page = result.pages[0]
        final_items = [
            child.resolve(result.document)
            for child in result.document.body.children
        ]
        final_texts = [getattr(item, "text", None) for item in final_items]
        final_string_texts = [text for text in final_texts if text is not None]
        if _contains_complete_drop_cap(final_string_texts):
            return

        word_texts = [cell.text for cell in page.parsed_page.word_cells]
        cap_word_index = word_texts.index("T")
        self.assertEqual(
            word_texts[cap_word_index : cap_word_index + 2],
            ["T", "his"],
        )

        parsed_texts = [cell.text for cell in page.parsed_page.textline_cells]
        _assert_adjacent(self, parsed_texts, "parsed text-line")

        layout_texts = [
            " ".join(cell.text for cell in cluster.cells)
            for cluster in page.predictions.layout.clusters
        ]
        _assert_adjacent(self, layout_texts, "layout cluster")

        page_assembled_texts = [
            item.text for item in page.assembled.body if item.text is not None
        ]
        _assert_adjacent(self, page_assembled_texts, "page assembly")
        assembled_texts = [
            item.text for item in result.assembled.body if item.text is not None
        ]
        _assert_adjacent(self, assembled_texts, "conversion assembly")

        cap_index = final_texts.index("T")
        remainder_index = final_texts.index(DROP_CAP_REMAINDER)
        self.assertGreater(remainder_index, cap_index + 1)
        intervening = final_items[cap_index + 1 : remainder_index]
        self.assertTrue(
            any(item.label.value == "picture" for item in intervening)
        )
        intervening_texts = [getattr(item, "text", None) for item in intervening]
        self.assertIn("Right column third", intervening_texts)
        self.assertIn("Right column fourth", intervening_texts)

        for item in (final_items[cap_index], final_items[remainder_index]):
            self.assertEqual(item.label.value, "text")
            self.assertEqual(item.content_layer.value, "body")


if __name__ == "__main__":
    unittest.main()
