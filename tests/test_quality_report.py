from __future__ import annotations

import unittest
from types import SimpleNamespace

from pdftomd import quality_report as qr
from pdftomd import structural_integrity as si


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
    return qr.analyze(
        pdf_text,
        markdown,
        structure(**overrides),
        profile,
        si.empty_report(),
    )


class CoverageTests(unittest.TestCase):
    def test_full_coverage_when_markdown_has_every_word(self) -> None:
        report = analyze(["risk assessment guide"], "# risk assessment guide")

        self.assertEqual(report.words_in_pdf, 3)
        self.assertEqual(report.words_matched, 3)
        self.assertEqual(report.coverage, 100.0)
        self.assertEqual(report.legacy_coverage, 100.0)
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

    def test_words_containing_uppercase_i_match_english_lowercase(self) -> None:
        report = analyze(["RISK TITLE I"], "risk title i")

        self.assertEqual(report.words_matched, 3)

    def test_accented_words_are_matched_too(self) -> None:
        # The source PDFs are not English, so the word pattern must cover
        # Turkish and other accented letters.
        report = analyze(["Öğrenci başvurusu değerlendirildi"], "öğrenci BAŞVURUSU")

        self.assertEqual(report.words_in_pdf, 3)
        self.assertEqual(report.words_matched, 2)

    def test_one_and_two_character_words_and_numbers_are_not_omitted(self) -> None:
        report = analyze(["A ve 7 42"], "a VE 7 42")

        self.assertEqual(report.words_in_pdf, 4)
        self.assertEqual(report.words_matched, 4)

    def test_missing_short_words_and_numeric_cells_are_reported_as_loss(self) -> None:
        report = analyze(["A ve 7 42"], "A 42")

        self.assertEqual(report.words_in_pdf, 4)
        self.assertEqual(report.words_matched, 2)
        self.assertEqual(report.unexplained, 2)
        self.assertEqual(set(report.worst_pages[0].samples), {"ve", "7"})

    def test_ligatures_compare_equal_to_ordinary_letter_sequences(self) -> None:
        report = analyze(["oﬃce ﬂow ﬀ"], "office flow ff")

        self.assertEqual(report.words_matched, 3)
        self.assertEqual(report.unexplained, 0)

    def test_turkish_dotted_and_dotless_case_pairs_compare_correctly(self) -> None:
        pdf_text = qr.PdfText(
            "document.pdf",
            ("İ I i ı",),
            case_profile="turkic",
        )
        report = qr.analyze(
            pdf_text, "i ı İ I", structure(), "quality", si.empty_report()
        )

        self.assertEqual(report.words_matched, 4)

    def test_turkish_dotted_and_dotless_i_do_not_cross_match(self) -> None:
        dotted = qr.analyze(
            qr.PdfText("document.pdf", ("İ",), case_profile="turkic"),
            "ı",
            structure(),
            "quality",
            si.empty_report(),
        )
        dotless = qr.analyze(
            qr.PdfText("document.pdf", ("I",), case_profile="turkic"),
            "i",
            structure(),
            "quality",
            si.empty_report(),
        )

        self.assertEqual(dotted.words_matched, 0)
        self.assertEqual(dotless.words_matched, 0)

    def test_v1_counter_does_not_force_ambiguous_hyphenation_to_join(self) -> None:
        report = analyze(["hyphen-\nation"], "hyphenation")

        self.assertEqual(report.words_in_pdf, 1)
        self.assertEqual(report.words_matched, 0)

    def test_real_compound_does_not_match_separate_words(self) -> None:
        report = analyze(["risk-based"], "risk based")

        self.assertEqual(report.words_in_pdf, 1)
        self.assertEqual(report.words_matched, 0)
        self.assertEqual(report.worst_pages[0].samples, ("risk-based",))


class AlignmentRegressionTests(unittest.TestCase):
    """The integrated alignment supersedes the known v1 counter bugs."""

    def test_one_docling_occurrence_is_not_reused_across_pdf_pages(self) -> None:
        report = analyze(
            ["repeat", "repeat"],
            "repeat",
            content_sources=(qr.TextSource("repeat", page_no=1),),
        )

        operations = report.alignments.extraction.operations
        self.assertEqual(sum(operation.type.value == "match" for operation in operations), 1)
        self.assertEqual(
            sum(operation.type.value == "deletion" for operation in operations), 1
        )

    def test_figure_text_only_explains_an_occurrence_on_its_page(self) -> None:
        diagram_boxes = tuple(
            qr.SpatialBox(index, 0, index + 0.8, 1) for index in range(7)
        )
        pdf_text = qr.PdfText(
            "document.pdf",
            ("diagram", "diagram"),
            figure_sources=(
                qr.TextSource(
                    "diagram",
                    page_no=1,
                    spatial_regions=(
                        qr.SpatialRegion(1, qr.SpatialBox(0, 0, 7, 1)),
                    ),
                ),
            ),
            page_char_boxes=(diagram_boxes, diagram_boxes),
        )
        report = qr.analyze(
            pdf_text,
            "",
            structure(
                figures=(
                    qr.Figure(page_no=1, left=0, bottom=0, right=10, top=10),
                )
            ),
            "quality",
            si.empty_report(),
        )

        operations = report.alignments.extraction.operations
        self.assertEqual(
            sum(operation.match_kind.value == "figure" for operation in operations), 1
        )
        self.assertEqual(
            sum(operation.match_kind.value == "unexplained" for operation in operations),
            1,
        )

    def test_furniture_only_explains_an_occurrence_on_its_page(self) -> None:
        header_boxes = tuple(
            qr.SpatialBox(index, 0, index + 0.8, 1) for index in range(6)
        )
        report = qr.analyze(
            qr.PdfText(
                "document.pdf",
                ("header", "header"),
                page_char_boxes=(header_boxes, header_boxes),
            ),
            "",
            structure(
                furniture_text="header",
                furniture_sources=(
                    qr.TextSource(
                        "header",
                        page_no=1,
                        spatial_regions=(
                            qr.SpatialRegion(1, qr.SpatialBox(0, 0, 6, 1)),
                        ),
                    ),
                ),
            ),
            "quality",
            si.empty_report(),
        )

        operations = report.alignments.extraction.operations
        self.assertEqual(
            sum(operation.match_kind.value == "furniture" for operation in operations),
            1,
        )
        self.assertEqual(
            sum(operation.match_kind.value == "unexplained" for operation in operations),
            1,
        )


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


class DocumentEvidenceTests(unittest.TestCase):
    def test_top_left_docling_regions_are_converted_to_pdf_coordinates(self) -> None:
        provenance = SimpleNamespace(
            page_no=1,
            charspan=(0, 6),
            bbox=SimpleNamespace(
                l=10,
                t=20,
                r=30,
                b=40,
                coord_origin=SimpleNamespace(value="TOPLEFT"),
            ),
        )
        item = SimpleNamespace(
            text="header",
            self_ref="#/texts/10",
            prov=(provenance,),
            content_layer=SimpleNamespace(value="furniture"),
        )
        document = SimpleNamespace(
            pages={1: SimpleNamespace(size=SimpleNamespace(height=100))},
            tables=(),
            pictures=(),
            texts=(item,),
        )

        source = qr.describe_document(document).furniture_sources[0]

        self.assertEqual(
            source.spatial_regions,
            (qr.SpatialRegion(1, qr.SpatialBox(10, 60, 30, 80)),),
        )

    def test_docling_figure_and_furniture_provenance_is_retained(self) -> None:
        figure_provenance = SimpleNamespace(
            page_no=2,
            bbox=SimpleNamespace(
                l=40,
                b=20,
                r=10,
                t=60,
                coord_origin=SimpleNamespace(value="BOTTOMLEFT"),
            ),
        )
        furniture_provenance = SimpleNamespace(page_no=3)
        document = SimpleNamespace(
            pages={1: object(), 2: object(), 3: object()},
            tables=(),
            pictures=(
                SimpleNamespace(self_ref="#/pictures/4", prov=(figure_provenance,)),
            ),
            texts=(
                SimpleNamespace(
                    text="Page header",
                    self_ref="#/texts/8",
                    prov=(furniture_provenance,),
                    content_layer=SimpleNamespace(value="furniture"),
                ),
                SimpleNamespace(
                    text="Body",
                    self_ref="#/texts/9",
                    prov=(SimpleNamespace(page_no=3),),
                    content_layer=SimpleNamespace(value="body"),
                ),
            ),
        )

        described = qr.describe_document(document)

        self.assertEqual(described.figures[0].page_no, 2)
        self.assertEqual(described.figures[0].block_id, "#/pictures/4")
        self.assertEqual(described.figures[0].provenance, (figure_provenance,))
        self.assertEqual(described.furniture_text, "Page header")
        self.assertEqual(described.furniture_sources[0].page_no, 3)
        self.assertEqual(described.furniture_sources[0].block_id, "#/texts/8")
        self.assertEqual(
            described.furniture_sources[0].provenance,
            (furniture_provenance,),
        )

    def test_docling_body_and_table_cells_follow_document_iteration_order(self) -> None:
        page = SimpleNamespace(page_no=1, charspan=(0, 20))
        first = SimpleNamespace(
            text="Before table",
            self_ref="#/texts/1",
            prov=(page,),
            content_layer=SimpleNamespace(value="body"),
        )
        table = SimpleNamespace(
            self_ref="#/tables/1",
            prov=(page,),
            content_layer=SimpleNamespace(value="body"),
            data=SimpleNamespace(
                table_cells=(
                    SimpleNamespace(text="7", col_span=1, row_span=1),
                    SimpleNamespace(text="42", col_span=1, row_span=1),
                )
            ),
        )
        last = SimpleNamespace(
            text="After table",
            self_ref="#/texts/2",
            prov=(page,),
            content_layer=SimpleNamespace(value="body"),
        )
        document = SimpleNamespace(
            pages={1: object()},
            tables=(table,),
            pictures=(),
            texts=(first, last),
            iterate_items=lambda: iter(((first, 0), (table, 0), (last, 0))),
        )

        described = qr.describe_document(document)

        self.assertEqual(
            [source.text for source in described.content_sources],
            ["Before table", "7", "42", "After table"],
        )
        self.assertEqual(
            [source.block_id for source in described.content_sources],
            ["#/texts/1", "#/tables/1/cells/0", "#/tables/1/cells/1", "#/texts/2"],
        )
        self.assertTrue(
            all(source.provenance == (page,) for source in described.content_sources)
        )

    def test_multi_page_table_cells_keep_page_unknown_without_cell_spans(self) -> None:
        first = SimpleNamespace(page_no=1, charspan=(0, 20))
        second = SimpleNamespace(page_no=2, charspan=(20, 40))
        table = SimpleNamespace(
            self_ref="#/tables/2",
            prov=(first, second),
            content_layer=SimpleNamespace(value="body"),
            data=SimpleNamespace(
                table_cells=(SimpleNamespace(text="42", col_span=1, row_span=1),)
            ),
        )
        document = SimpleNamespace(
            pages={1: object(), 2: object()},
            tables=(table,),
            pictures=(),
            texts=(),
            iterate_items=lambda: iter(((table, 0),)),
        )

        described = qr.describe_document(document)
        source = described.content_sources[0]
        token = qr.tokenize_sources((source,))[0]

        self.assertIsNone(source.page_no)
        self.assertIsNone(token.page_no)
        self.assertEqual(token.provenance, (first, second))
        self.assertEqual(token.all_provenance, (first, second))
        self.assertEqual(token.provenance_status, "multiple_unmapped")


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
