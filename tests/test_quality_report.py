from __future__ import annotations

import unittest

from pdftomd import quality_report as qr


def structure(**overrides) -> qr.DocumentStructure:
    defaults = dict(
        pages=2,
        tables=0,
        merged_cell_tables=0,
        figures=(),
        furniture_text="",
    )
    defaults.update(overrides)
    return qr.DocumentStructure(**defaults)


def analyze(page_texts, markdown, profile="quality", figure_text="", **overrides):
    """Run a report on hand-written page text instead of a real PDF."""
    pdf_text = qr.PdfText("document.pdf", tuple(page_texts), figure_text)
    return qr.analyze(pdf_text, markdown, structure(**overrides), profile)


class CoverageTests(unittest.TestCase):
    def test_full_coverage_when_markdown_has_every_word(self) -> None:
        report = analyze(["risk assessment guide"], "# risk assessment guide")

        self.assertEqual(report.words_in_pdf, 3)
        self.assertEqual(report.words_matched, 3)
        self.assertEqual(report.coverage, 100.0)
        self.assertEqual(report.unexplained, 0)

    def test_missing_words_are_counted_and_reported_per_page(self) -> None:
        report = analyze(
            ["alpha bravo charlie delta", "echo foxtrot"],
            "alpha bravo echo foxtrot",
        )

        self.assertEqual(report.words_in_pdf, 6)
        self.assertEqual(report.words_matched, 4)
        self.assertEqual(report.unexplained, 2)
        self.assertEqual(report.worst_pages[0].page_no, 1)
        self.assertEqual(report.worst_pages[0].missing, 2)
        self.assertEqual(set(report.worst_pages[0].samples), {"charlie", "delta"})

    def test_words_are_matched_case_insensitively(self) -> None:
        report = analyze(["Risk ASSESSMENT"], "risk assessment")

        self.assertEqual(report.words_matched, 2)

    def test_accented_words_are_matched_too(self) -> None:
        # The source PDFs are not English, so the word pattern must cover
        # Turkish and other accented letters.
        report = analyze(["Öğrenci başvurusu değerlendirildi"], "öğrenci BAŞVURUSU")

        self.assertEqual(report.words_in_pdf, 3)
        self.assertEqual(report.words_matched, 2)


class AttributionTests(unittest.TestCase):
    def test_text_inside_a_figure_is_not_counted_as_unexplained(self) -> None:
        report = analyze(
            ["intro monitor respond"],
            "intro",
            figure_text="monitor respond",
            figures=(qr.Figure(page_no=1, left=0, bottom=0, right=100, top=100),),
        )

        self.assertEqual(report.in_figures, 2)
        self.assertEqual(report.unexplained, 0)
        self.assertEqual(report.worst_pages, ())

    def test_page_headers_and_footers_count_as_intentionally_dropped(self) -> None:
        report = analyze(
            ["Special Publication content"],
            "content",
            furniture_text="Special Publication",
        )

        self.assertEqual(report.in_furniture, 2)
        self.assertEqual(report.unexplained, 0)

    def test_footnote_number_glued_to_a_word_is_not_a_real_loss(self) -> None:
        report = analyze(["the likelihood55 of risk"], "the likelihood of risk")

        self.assertEqual(report.footnote_glued, 1)
        self.assertEqual(report.unexplained, 0)

    def test_a_word_that_only_looks_glued_stays_unexplained(self) -> None:
        report = analyze(["the sha256 hash"], "the hash")

        self.assertEqual(report.footnote_glued, 0)
        self.assertEqual(report.unexplained, 1)

    def test_image_links_in_markdown_do_not_mask_missing_words(self) -> None:
        report = analyze(["diagram alpha"], "![diagram](out_artifacts/diagram.png) alpha")

        self.assertEqual(report.unexplained, 1)
        self.assertEqual(report.worst_pages[0].samples, ("diagram",))


class ScannedPageTests(unittest.TestCase):
    def test_pages_without_a_text_layer_are_listed_not_counted_as_loss(self) -> None:
        report = analyze(["", "real text here", ""], "real text here")

        self.assertEqual(report.pages_without_text_layer, (1, 3))
        self.assertEqual(report.words_in_pdf, 3)
        self.assertEqual(report.coverage, 100.0)

    def test_fast_profile_warns_that_scanned_pages_came_out_empty(self) -> None:
        report = analyze(["", "text here"], "text here", profile="fast")

        console = qr.render_console(report)
        self.assertIn("WARNING", console)
        self.assertIn("--quality", console)

    def test_quality_profile_only_notes_that_ocr_cannot_be_verified(self) -> None:
        report = analyze(["", "text here"], "text here")

        console = qr.render_console(report)
        self.assertNotIn("WARNING", console)
        self.assertIn("OCR", console)

    def test_a_fully_scanned_document_says_coverage_cannot_be_measured(self) -> None:
        report = analyze(["", ""], "text that came from OCR")

        self.assertEqual(report.words_in_pdf, 0)
        self.assertIn("coverage cannot be measured", qr.render_console(report))
        self.assertIn("coverage cannot be measured", qr.render_markdown(report))


class RenderTests(unittest.TestCase):
    def test_large_word_counts_get_thousands_separators(self) -> None:
        report = analyze(["word " * 1500], "word")

        self.assertIn("1,500", qr.render_markdown(report))

    def test_merged_cell_tables_are_explained_in_the_report(self) -> None:
        report = analyze(["text"], "text", tables=4, merged_cell_tables=3)

        text = qr.render_markdown(report)
        self.assertIn("3 tables contain merged cells", text)

    def test_singular_counts_read_correctly(self) -> None:
        report = analyze(["text"], "text", tables=1, merged_cell_tables=1, pages=1)

        text = qr.render_markdown(report)
        self.assertIn("1 page | 1 table | 0 images", text)
        self.assertIn("1 table contains merged cells", text)
        self.assertNotIn("1 tables", text)
        self.assertNotIn("1 pages", text)

    def test_a_single_scanned_page_is_not_called_pages(self) -> None:
        report = analyze(["", "text"], "text", profile="fast")

        console = qr.render_console(report)
        self.assertIn("1 page without a text layer", console)
        self.assertIn("1 page looks scanned", qr.render_markdown(report))

    def test_plain_documents_do_not_mention_merged_cells(self) -> None:
        report = analyze(["text"], "text", tables=2)

        self.assertNotIn("merged cells", qr.render_markdown(report))


if __name__ == "__main__":
    unittest.main()
