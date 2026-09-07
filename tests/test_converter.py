from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from pdftomd import converter
from pdftomd import quality_report as qr


def output_paths(root: Path, stem: str = "source") -> converter.OutputPaths:
    directory = root / "output"
    return converter.OutputPaths(
        directory=directory,
        markdown=directory / f"{stem}.md",
        json=directory / f"{stem}.json",
        artifacts=directory / f"{stem}_artifacts",
        report=directory / f"{stem}_report.md",
    )


class PipelineOptionsTests(unittest.TestCase):
    def test_quality_enables_ocr_tables_and_formula_when_requested(self) -> None:
        options = SimpleNamespace()

        result = converter.configure_pipeline_options(options, "quality", True)

        self.assertIs(result, options)
        self.assertTrue(options.do_ocr)
        self.assertTrue(options.do_table_structure)
        self.assertTrue(options.generate_picture_images)
        self.assertTrue(options.do_formula_enrichment)

    def test_fast_disables_ocr_and_tables_but_keeps_formula_independent(self) -> None:
        options = SimpleNamespace()

        converter.configure_pipeline_options(options, "fast", True)

        self.assertFalse(options.do_ocr)
        self.assertFalse(options.do_table_structure)
        self.assertTrue(options.generate_picture_images)
        self.assertTrue(options.do_formula_enrichment)


@unittest.skipUnless(os.name == "nt", "The long path prefix is Windows only.")
class LongPathTests(unittest.TestCase):
    def test_absolute_paths_get_the_extended_length_prefix(self) -> None:
        self.assertEqual(
            converter.long_path(Path(r"C:\Users\test\document.pdf")),
            Path(r"\\?\C:\Users\test\document.pdf"),
        )

    def test_unc_and_prefixed_paths_stay_usable(self) -> None:
        self.assertEqual(
            converter.long_path(Path(r"\\server\share\document.pdf")),
            Path(r"\\?\UNC\server\share\document.pdf"),
        )
        already = Path(r"\\?\C:\Users\test\document.pdf")
        self.assertEqual(converter.long_path(already), already)

    def test_relative_paths_are_left_alone(self) -> None:
        self.assertEqual(converter.long_path(Path("document.pdf")), Path("document.pdf"))


class OutputPlanningTests(unittest.TestCase):
    def test_single_pdf_keeps_existing_default_and_custom_output_behavior(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir).resolve()
            pdf = root / "report.pdf"

            default_outputs, default_open = converter.plan_output_paths([pdf], None)
            custom_outputs, custom_open = converter.plan_output_paths(
                [pdf], root / "custom"
            )

            self.assertEqual(default_outputs[0].directory, root / "report_markdown")
            self.assertEqual(default_open, root / "report_markdown")
            self.assertEqual(custom_outputs[0].directory, root / "custom")
            self.assertEqual(custom_open, root / "custom")

    def test_every_output_file_lives_in_the_document_folder(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir).resolve()

            outputs, _ = converter.plan_output_paths([root / "report.pdf"], None)
            output = outputs[0]

            self.assertEqual(output.markdown, output.directory / "report.md")
            self.assertEqual(output.json, output.directory / "report.json")
            self.assertEqual(output.artifacts, output.directory / "report_artifacts")
            self.assertEqual(output.report, output.directory / "report_report.md")

    def test_batch_uses_common_root_and_suffixes_duplicate_stems(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir).resolve()
            pdfs = [root / "report.pdf", root / "other" / "REPORT.pdf"]

            outputs, folder_to_open = converter.plan_output_paths(pdfs, None)

            self.assertEqual(folder_to_open, root / "pdfmd_output")
            self.assertEqual(outputs[0].directory, folder_to_open / "report_markdown")
            self.assertEqual(
                outputs[1].directory,
                folder_to_open / "REPORT_markdown_2",
            )

    def test_batch_custom_output_is_the_common_root(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir).resolve()
            custom = root / "exports"

            outputs, folder_to_open = converter.plan_output_paths(
                [root / "one.pdf", root / "two.pdf"], custom
            )

            self.assertEqual(folder_to_open, custom)
            self.assertEqual(outputs[0].directory, custom / "one_markdown")
            self.assertEqual(outputs[1].directory, custom / "two_markdown")


class ExportTests(unittest.TestCase):
    def _write_markdown(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            "![Image](source_artifacts\\image_000000.png)\n$\\frac{a}{b}$\n",
            encoding="utf-8",
        )

    def _runtime(self, report: bool = False) -> tuple[converter.DoclingRuntime, Mock]:
        document = Mock()
        document.save_as_markdown.side_effect = lambda path, **_: self._write_markdown(path)
        docling = Mock()
        docling.convert.return_value = SimpleNamespace(document=document)
        runtime = converter.DoclingRuntime(docling, "referenced", "quality", report)
        return runtime, document

    def test_markdown_and_json_share_result_and_artifacts_directory(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir).resolve()
            pdf = root / "source.pdf"
            output = output_paths(root)
            runtime, document = self._runtime()

            result = converter.convert_pdf(runtime, pdf, output)

            self.assertEqual(result.output, output)
            runtime.converter.convert.assert_called_once_with(converter.long_path(pdf))
            document.save_as_markdown.assert_called_once_with(
                converter.long_path(output.markdown),
                artifacts_dir=Path("source_artifacts"),
                image_mode="referenced",
            )
            document.save_as_json.assert_called_once_with(
                converter.long_path(output.json),
                artifacts_dir=Path("source_artifacts"),
                image_mode="referenced",
            )

    def test_artifact_links_use_forward_slashes_but_formulas_are_kept(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            markdown = Path(temp_dir).resolve() / "output" / "source.md"
            self._write_markdown(markdown)

            converter.normalize_artifact_links(markdown, "source_artifacts")

            self.assertEqual(
                markdown.read_text(encoding="utf-8"),
                "![Image](source_artifacts/image_000000.png)\n$\\frac{a}{b}$\n",
            )

    def test_failed_json_export_fails_the_whole_document(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir).resolve()
            runtime, document = self._runtime()
            document.save_as_json.side_effect = RuntimeError("cannot write the JSON")

            with self.assertRaises(RuntimeError):
                converter.convert_pdf(runtime, root / "source.pdf", output_paths(root))

    def test_quality_report_summary_comes_back_with_the_result(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir).resolve()
            runtime, _ = self._runtime(report=True)

            with patch(
                "pdftomd.converter.write_quality_report", return_value="Quality: 100%"
            ) as report_mock:
                result = converter.convert_pdf(
                    runtime, root / "source.pdf", output_paths(root)
                )

            self.assertEqual(result.report_summary, "Quality: 100%")
            self.assertIsNone(result.report_error)
            report_mock.assert_called_once()

    def test_a_broken_report_does_not_fail_the_conversion(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir).resolve()
            runtime, _ = self._runtime(report=True)

            with patch(
                "pdftomd.converter.write_quality_report",
                side_effect=RuntimeError("cannot read the PDF"),
            ):
                result = converter.convert_pdf(
                    runtime, root / "source.pdf", output_paths(root)
                )

            self.assertEqual(result.report_error, "cannot read the PDF")
            self.assertIsNone(result.report_summary)

    def test_no_report_runtime_skips_the_measurement_entirely(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir).resolve()
            runtime, _ = self._runtime(report=False)

            with patch("pdftomd.converter.write_quality_report") as report_mock:
                result = converter.convert_pdf(
                    runtime, root / "source.pdf", output_paths(root)
                )

            report_mock.assert_not_called()
            self.assertIsNone(result.report_summary)

    def test_write_quality_report_builds_integrated_two_stage_alignment(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir).resolve()
            output = output_paths(root)
            output.directory.mkdir(parents=True)
            output.markdown.write_text("visible", encoding="utf-8")
            provenance = SimpleNamespace(page_no=1, charspan=(0, 7))
            body = SimpleNamespace(
                text="visible",
                self_ref="#/texts/1",
                prov=(provenance,),
                content_layer=SimpleNamespace(value="body"),
            )
            document = SimpleNamespace(
                pages={1: object()},
                tables=(),
                pictures=(),
                texts=(body,),
                iterate_items=lambda: iter(((body, 0),)),
            )

            with patch(
                "pdftomd.converter.quality_report.read_pdf_text",
                return_value=qr.PdfText("source.pdf", ("visible",)),
            ):
                summary = converter.write_quality_report(
                    root / "source.pdf",
                    output.markdown,
                    document,
                    output,
                    "quality",
                )

            self.assertEqual(
                summary,
                "Quality Report v2 | Extraction: transfer 100.0% (1/1);"
                " unexplained 0; order risks 0 | Serialization: transfer 100.0%"
                " (1/1); unexpected 0; order risks 0\n"
                "Structure: not evaluated in this milestone.",
            )
            self.assertTrue(output.report.is_file())
            described = qr.describe_document(document)
            report = qr.analyze(
                qr.PdfText("source.pdf", ("visible",)),
                "visible",
                described,
                "quality",
            )
            self.assertIsNotNone(report.alignments)
            self.assertEqual(
                report.alignments.extraction.operations[0].type.value,
                "match",
            )


if __name__ == "__main__":
    unittest.main()
