from __future__ import annotations

import contextlib
import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image

from pdf_receipt import cli, comparison as cp, quality_report as qr
from pdf_receipt.quality_metrics import summarize_alignment


class ComparisonTests(unittest.TestCase):
    def test_long_paragraph_duplication_preserves_unchanged_order(self):
        paragraph = " ".join(f"word{i}" for i in range(90))
        following = " ".join(f"tail{i}" for i in range(100))
        source = paragraph + " " + following
        metrics = self.metrics([source], paragraph + " " + source)
        self.assertEqual(metrics.unexpected_insertion_count, 90)
        self.assertEqual(metrics.matched_source_count, 190)
        self.assertEqual(metrics.order_risk_count, 0)

    def test_moved_hyphenated_word_uses_context_and_consumes_once(self):
        middle = " ".join(f"middle{i}" for i in range(90))
        metrics = self.metrics(["before inter-\nnational after " + middle],
                               middle + " before international after")
        self.assertEqual(metrics.unexplained_deletion_count, 0)
        self.assertEqual(metrics.unexpected_insertion_count, 0)
        self.assertEqual(metrics.order_risk_count, 3)

    def test_long_deletion_keeps_surviving_tokens_in_order(self):
        prefix = " ".join(f"word{i}" for i in range(90))
        suffix = " ".join(f"tail{i}" for i in range(100))
        metrics = self.metrics([prefix + " " + suffix], suffix)
        self.assertEqual(metrics.unexplained_deletion_count, 90)
        self.assertEqual(metrics.matched_source_count, 100)
        self.assertEqual(metrics.order_risk_count, 0)

    def test_moved_hyphen_join_without_neighbor_evidence_is_not_accepted(self):
        metrics = self.metrics(["start inter-\nnational finish"],
                               "other international words start finish")
        self.assertGreater(metrics.unexplained_loss_numerator, 0)

    def test_moved_hyphen_occurrences_cannot_share_target(self):
        middle = " ".join(f"middle{i}" for i in range(90))
        metrics = self.metrics(["before inter-\nnational after",
                                "before inter-\nnational after " + middle],
                               middle + " before international after")
        self.assertEqual(metrics.source_token_count - metrics.target_token_count, 3)
        self.assertEqual(metrics.unexplained_deletion_count, 3)
        self.assertEqual(metrics.order_risk_count, 3)

    def metrics(self, pages, markdown, profile="unicode"):
        result = cp.compare_text(qr.PdfText("source.pdf", tuple(pages), case_profile=profile), markdown)
        metrics = summarize_alignment(result)
        self.assertEqual(metrics.source_accounted_count, metrics.source_token_count)
        self.assertEqual(metrics.target_accounted_count, metrics.target_token_count)
        return metrics

    def test_global_repeated_occurrences_are_not_reused_across_pages(self):
        metrics = self.metrics(["echo", "echo"], "echo")
        self.assertEqual(metrics.matched_source_count, 1)
        self.assertEqual(metrics.unexplained_deletion_count, 1)

    def test_extra_occurrence_and_missing_occurrence(self):
        self.assertEqual(self.metrics(["alpha"], "alpha alpha").unexpected_insertion_count, 1)
        self.assertEqual(self.metrics(["alpha beta"], "alpha").unexplained_deletion_count, 1)

    def test_substitution_and_order_risk(self):
        self.assertEqual(self.metrics(["alpha beta"], "alpha gamma").substitution_count, 1)
        self.assertGreater(self.metrics(["alpha beta gamma"], "beta alpha gamma").order_risk_count, 0)

    def test_unicode_short_tokens_and_turkic_profile(self):
        self.assertEqual(self.metrics(["a I café"], "A i cafe\u0301").matched_source_count, 3)
        self.assertEqual(self.metrics(["I İ"], "ı i", "turkic").matched_source_count, 2)

    def test_empty_denominators_and_unverified_pages(self):
        metrics = self.metrics(["", ""], "")
        self.assertIsNone(metrics.normalized_exact_transfer_rate)
        self.assertIsNone(metrics.unexpected_addition_rate)
        report = cp.render_report(qr.PdfText("blank.pdf", ("", "word")), "word", Path("test.md"))
        self.assertIn("(unverified): 1", report)
        self.assertEqual(self.metrics([""], "word").unexpected_insertion_count, 1)

    def test_real_scanned_pdf_is_unverified_without_ocr(self):
        source = Path(__file__).parent / "fixtures" / "scanned_page.pdf"
        pdf = qr.read_pdf_text(source)
        report = cp.render_report(pdf, "Independently transcribed text", Path("scan.md"))
        self.assertIn("Source tokens: 0", report)
        self.assertIn("(unverified): 1", report)
        self.assertIn("n/a (empty denominator)", report)

    def test_real_pdf_matches_independently_selected_prose(self):
        source = Path(__file__).parent / "fixtures" / "formulas" / "formula_equations.pdf"
        markdown = "# Formula Conversion Fixture\n\nThe first equation states the relation between three squared lengths."
        metrics = summarize_alignment(cp.compare_text(qr.read_pdf_text(source), markdown))
        self.assertEqual(metrics.matched_source_count, 13)
        self.assertEqual(metrics.unexpected_insertion_count, 0)
        self.assertGreater(metrics.unexplained_deletion_count, 0)

    def test_common_markdown_syntax_and_original_line_offsets(self):
        markdown = "# Heading\r\n\r\n1. [alpha](https://example.invalid) **beta**\r\n![alt](picture.png)"
        self.assertEqual(self.metrics(["Heading alpha beta"], markdown).matched_source_count, 3)
        report = cp.render_report(qr.PdfText("source.pdf", ("Heading alpha gamma",)), markdown, Path("test.md"))
        self.assertIn("Markdown line 3", report)
        self.assertIn("PDF page 1", report)
        self.assertIn("raw span", report)
        self.assertIn("PDF context", report)

    def test_issue_limit_preserves_counts_and_escapes_evidence(self):
        report = cp.render_report(qr.PdfText("<img>.pdf", ("one keep two stay three",)), "keep stay", Path("test.md"), issue_limit=1)
        self.assertIn("Showing 1 of 3; omitted 2", report)
        self.assertIn("Missing occurrences: 3", report)
        self.assertIn("&lt;img&gt;", report)
        self.assertNotIn("<img>", report)

    def test_inline_images_missing_empty_invalid_remote_and_outside(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            Image.new("RGB", (2, 2)).save(root / "ok.png")
            (root / "empty.png").write_bytes(b"")
            (root / "bad.png").write_bytes(b"not an image")
            targets = ["ok.png", "empty.png", "bad.png", "missing.png", "../outside.png", "https://example.invalid/a.png"]
            checks = cp.image_checks("\n".join(f"![alt]({target})" for target in targets), root / "test.md")
            statuses = [entry[2] for entry in checks]
            self.assertIn("decodable image", statuses[0])
            self.assertEqual(statuses[1:5], ["empty image", "invalid image", "missing_local_target", "outside_output_root"])
            self.assertIn("not checked", statuses[5])
            self.assertEqual(cp.image_checks("```md\n![sample](missing.png)\n```", root / "test.md"), [])

    def test_reference_and_html_images_use_existing_local_checks(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            Image.new("RGB", (2, 2)).save(root / "a b.png")
            markdown = ('![ok][]\n![missing]\n<img src="../outside.png">\n'
                        '<img src="https://example.invalid/image.png">\n\n'
                        '[ok]: a%20b.png\n[missing]: absent.png')
            checks = cp.image_checks(markdown, root / "test.md")
            self.assertEqual([c[0] for c in checks], [1, 2, 3, 4])
            self.assertIn("decodable image", checks[0][2])
            self.assertEqual(checks[1][2], "missing_local_target")
            self.assertEqual(checks[2][2], "outside_output_root")
            self.assertIn("not checked", checks[3][2])

    def test_cli_compares_real_pdf_without_runtime_and_preserves_files(self):
        source = Path(__file__).parent / "fixtures" / "formulas" / "formula_equations.pdf"
        original = source.read_bytes()
        with tempfile.TemporaryDirectory() as folder:
            markdown = Path(folder) / "independent.md"
            markdown.write_text("# Independently authored summary\nA triangle equation and a fraction.\n", encoding="utf-8")
            before = markdown.read_bytes()
            with patch("pdf_receipt.cli.create_docling_runtime", side_effect=AssertionError("must not load")), contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(cli.main(["compare", str(source), str(markdown)]), 0)
            report = markdown.with_name("independent_comparison.md")
            self.assertIn("PDF-to-Markdown comparison", report.read_text(encoding="utf-8"))
            saved = report.read_bytes()
            with contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(cp.main([str(source), str(markdown)]), 1)
                self.assertEqual(cp.main([str(source), str(markdown), "--report", str(markdown)]), 1)
            self.assertEqual(report.read_bytes(), saved)
            self.assertEqual(markdown.read_bytes(), before)
            self.assertEqual(source.read_bytes(), original)

    def test_cli_rejects_missing_inputs_conversion_flags_and_invalid_limits(self):
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(cp.main(["missing.pdf", "missing.md"]), 1)
            for extra in (["--formula"], ["--profile", "fast"], ["--issue-limit", "0"]):
                with self.assertRaises(SystemExit) as error:
                    cp.main(["source.pdf", "existing.md", *extra])
                self.assertEqual(error.exception.code, 2)

    def test_cli_read_and_write_failures_are_nonzero(self):
        source = Path(__file__).parent / "fixtures" / "formulas" / "formula_equations.pdf"
        with tempfile.TemporaryDirectory() as folder, contextlib.redirect_stderr(io.StringIO()):
            markdown = Path(folder) / "test.md"
            markdown.write_bytes(b"\xff")
            self.assertEqual(cp.main([str(source), str(markdown)]), 1)
            markdown.write_text("text", encoding="utf-8")
            self.assertEqual(cp.main([str(source), str(markdown), "--report", str(Path(folder) / "absent" / "report.md")]), 1)


if __name__ == "__main__":
    unittest.main()
