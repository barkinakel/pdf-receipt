from __future__ import annotations

import unittest
from dataclasses import replace
from types import SimpleNamespace

from pdftomd import alignment
from pdftomd import quality_metrics as qm
from pdftomd import quality_report as qr
from pdftomd import structural_integrity as si


def tokens(
    text: str,
    *,
    page_no: int | None = 1,
    block_id: str | None = None,
    provenance=(),
    semantic_role: str | None = None,
    character_boxes=(),
    spatial_regions=(),
) -> tuple[qr.Token, ...]:
    return qr.tokenize(
        text,
        page_no=page_no,
        block_id=block_id,
        provenance=provenance,
        semantic_role=semantic_role,
        character_boxes=character_boxes,
        spatial_regions=spatial_regions,
    )


def report_for(
    pdf_text: str,
    docling_source: qr.TextSource,
    markdown: str,
    *,
    pages: int = 1,
) -> qr.QualityReport:
    structure = qr.DocumentStructure(
        pages=pages,
        tables=0,
        merged_cell_tables=0,
        figures=(),
        furniture_text="",
        content_sources=(docling_source,),
    )
    return qr.analyze(
        qr.PdfText("document.pdf", (pdf_text,)),
        markdown,
        structure,
        "quality",
        si.empty_report(),
    )


class StageMetricContractTests(unittest.TestCase):
    def test_exact_counts_rates_and_accounting_identities(self) -> None:
        result = alignment.align_serialization(
            tokens("alpha old removed move"),
            tokens("alpha new move added"),
            case_profile="unicode",
        )

        metrics = qm.summarize_alignment(result)

        self.assertEqual(metrics.source_token_count, 4)
        self.assertEqual(metrics.target_token_count, 4)
        self.assertEqual(metrics.normalized_match_count, 2)
        self.assertEqual(metrics.contextual_hyphen_match_count, 0)
        self.assertEqual(metrics.explained_deletion_count, 0)
        self.assertEqual(metrics.unexplained_deletion_count, 1)
        self.assertEqual(metrics.unexpected_insertion_count, 1)
        self.assertEqual(metrics.explained_addition_count, 0)
        self.assertEqual(metrics.substitution_count, 1)
        self.assertEqual(metrics.order_risk_count, 0)
        self.assertEqual(metrics.source_accounted_count, metrics.source_token_count)
        self.assertEqual(metrics.target_accounted_count, metrics.target_token_count)
        self.assertEqual(metrics.normalized_exact_transfer_rate, 0.5)
        self.assertEqual(metrics.accounted_for_loss_rate, 0.0)
        self.assertEqual(metrics.unexplained_loss_rate, 0.5)
        self.assertEqual(metrics.unexpected_addition_rate, 0.5)

    def test_contextual_hyphen_is_an_accepted_match_not_exact_normalized(self) -> None:
        result = alignment.align_extraction(
            tokens("before hyphen-\nation after"),
            tokens("before hyphenation after"),
            case_profile="unicode",
        )

        metrics = qm.summarize_alignment(result)

        self.assertEqual(metrics.normalized_match_count, 2)
        self.assertEqual(metrics.contextual_hyphen_match_count, 1)
        self.assertEqual(metrics.matched_source_count, 3)
        self.assertEqual(metrics.normalized_exact_transfer_rate, 1.0)

    def test_substitution_counts_once_on_both_sides(self) -> None:
        metrics = qm.summarize_alignment(
            alignment.align_serialization(
                tokens("old"), tokens("new"), case_profile="unicode"
            )
        )

        self.assertEqual(metrics.substitution_count, 1)
        self.assertEqual(metrics.unexplained_loss_numerator, 1)
        self.assertEqual(metrics.unexpected_addition_numerator, 1)
        self.assertEqual(metrics.source_accounted_count, 1)
        self.assertEqual(metrics.target_accounted_count, 1)

    def test_reading_order_risk_is_neither_match_nor_loss(self) -> None:
        metrics = qm.summarize_alignment(
            alignment.align_serialization(
                tokens("one two"), tokens("two one"), case_profile="unicode"
            )
        )

        self.assertEqual(metrics.normalized_match_count, 1)
        self.assertEqual(metrics.order_risk_count, 1)
        self.assertEqual(metrics.unexplained_deletion_count, 0)
        self.assertEqual(metrics.unexpected_insertion_count, 0)
        self.assertEqual(metrics.source_accounted_count, 2)
        self.assertEqual(metrics.target_accounted_count, 2)

    def test_repeated_issue_samples_keep_occurrence_indexes_and_limit(self) -> None:
        metrics = qm.summarize_alignment(
            alignment.align_serialization(
                tokens("repeat " * 10), (), case_profile="unicode"
            )
        )

        self.assertEqual(len(metrics.representative_issues), 8)
        self.assertEqual(
            [
                issue.operation.source_index
                for issue in metrics.representative_issues[:2]
            ],
            [0, 1],
        )

    def test_empty_denominators_are_not_applicable(self) -> None:
        cases = (
            ((), tokens("target"), None, 1.0),
            (tokens("source"), (), 0.0, None),
            ((), (), None, None),
        )
        for source, target, expected_transfer, expected_addition in cases:
            with self.subTest(source=bool(source), target=bool(target)):
                metrics = qm.summarize_alignment(
                    alignment.align_serialization(
                        source, target, case_profile="unicode"
                    )
                )
                self.assertEqual(
                    metrics.normalized_exact_transfer_rate, expected_transfer
                )
                self.assertEqual(
                    metrics.unexpected_addition_rate, expected_addition
                )
                if not source:
                    self.assertIsNone(metrics.accounted_for_loss_rate)
                    self.assertIsNone(metrics.unexplained_loss_rate)


class ExplanationMetricTests(unittest.TestCase):
    def test_spatial_figure_explanation_does_not_raise_transfer_rate(self) -> None:
        boxes = tuple(qr.SpatialBox(index, 0, index + 0.8, 1) for index in range(7))
        source = tokens("diagram", character_boxes=boxes)
        figure = tokens(
            "diagram",
            spatial_regions=(qr.SpatialRegion(1, qr.SpatialBox(0, 0, 7, 1)),),
        )
        result = alignment.align_extraction(
            source, (), case_profile="unicode", figure_tokens=figure
        )

        metrics = qm.summarize_alignment(result)

        self.assertEqual(metrics.matched_source_count, 0)
        self.assertEqual(metrics.explained_deletion_count, 1)
        self.assertEqual(metrics.normalized_exact_transfer_rate, 0.0)
        self.assertEqual(metrics.accounted_for_loss_rate, 1.0)

    def test_page_or_region_mismatch_stays_unexplained(self) -> None:
        boxes = tuple(qr.SpatialBox(index, 0, index + 0.8, 1) for index in range(7))
        result = alignment.align_extraction(
            tokens("diagram", page_no=1, character_boxes=boxes),
            (),
            case_profile="unicode",
            figure_tokens=tokens(
                "diagram",
                page_no=2,
                spatial_regions=(qr.SpatialRegion(2, qr.SpatialBox(0, 0, 7, 1)),),
            ),
        )

        metrics = qm.summarize_alignment(result)

        self.assertEqual(metrics.explained_deletion_count, 0)
        self.assertEqual(metrics.unexplained_deletion_count, 1)

    def test_docling_footnote_deletion_requires_role_block_and_provenance(self) -> None:
        provenance = SimpleNamespace(page_no=1, charspan=(0, 2))
        source = tokens(
            "55",
            block_id="#/texts/footnote",
            provenance=(provenance,),
            semantic_role="footnote",
        )
        result = alignment.align_serialization(source, (), case_profile="unicode")

        metrics = qm.summarize_alignment(result)

        self.assertEqual(metrics.explained_deletion_count, 1)
        self.assertEqual(result.operations[0].match_kind, alignment.MatchKind.FOOTNOTE)

        ambiguous = alignment.align_serialization(
            tokens("55", semantic_role="footnote"), (), case_profile="unicode"
        )
        self.assertEqual(
            qm.summarize_alignment(ambiguous).unexplained_deletion_count,
            1,
        )

    def test_table_repeat_evidence_explains_only_its_bounded_capacity(self) -> None:
        provenance = SimpleNamespace(page_no=1, charspan=(0, 5))
        source = tokens(
            "value",
            block_id="#/tables/1/cells/0",
            provenance=(provenance,),
            semantic_role="table_cell",
        )
        target = tokens("value value value", page_no=None)
        repeated_slot = tokens(
            "value",
            block_id="#/tables/1/cells/0",
            provenance=(provenance,),
            semantic_role="table_repeat",
        )
        result = alignment.align_serialization(
            source,
            target,
            case_profile="unicode",
            table_repeat_tokens=repeated_slot,
        )

        metrics = qm.summarize_alignment(result)

        self.assertEqual(metrics.explained_addition_count, 1)
        self.assertEqual(metrics.unexpected_insertion_count, 1)
        self.assertEqual(metrics.target_accounted_count, 3)

    def test_docling_merged_cell_span_supplies_exact_repeat_slots(self) -> None:
        provenance = SimpleNamespace(page_no=1, charspan=(0, 5))
        table = SimpleNamespace(
            self_ref="#/tables/1",
            prov=(provenance,),
            data=SimpleNamespace(
                table_cells=(
                    SimpleNamespace(text="value", row_span=1, col_span=3),
                )
            ),
        )
        document = SimpleNamespace(
            pages={1: object()},
            tables=(table,),
            pictures=(),
            texts=(),
            iterate_items=lambda: iter(((table, 0),)),
        )
        structure = qr.describe_document(document)

        report = qr.analyze(
            qr.PdfText("table.pdf", ("value",)),
            "value value value",
            structure,
            "quality",
            si.empty_report(),
        )

        self.assertEqual(len(structure.table_repeat_sources), 2)
        self.assertEqual(report.serialization_metrics.explained_addition_count, 2)
        self.assertEqual(report.serialization_metrics.unexpected_insertion_count, 0)

    def test_docling_footnote_role_and_provenance_flow_into_report(self) -> None:
        provenance = SimpleNamespace(page_no=1, charspan=(0, 2))
        footnote = SimpleNamespace(
            text="55",
            self_ref="#/texts/footnote",
            prov=(provenance,),
            label=SimpleNamespace(value="footnote"),
            content_layer=SimpleNamespace(value="body"),
        )
        document = SimpleNamespace(
            pages={1: object()},
            tables=(),
            pictures=(),
            texts=(footnote,),
            iterate_items=lambda: iter(((footnote, 0),)),
        )
        structure = qr.describe_document(document)

        report = qr.analyze(
            qr.PdfText("footnote.pdf", ("55",)),
            "",
            structure,
            "quality",
            si.empty_report(),
        )

        self.assertEqual(report.serialization_metrics.explained_deletion_count, 1)
        self.assertEqual(
            report.alignments.serialization.operations[0].match_kind,
            alignment.MatchKind.FOOTNOTE,
        )


class ReportV2Tests(unittest.TestCase):
    def test_integrated_report_keeps_exact_stage_denominators_separate(self) -> None:
        report = report_for(
            "alpha old removed move",
            qr.TextSource("alpha new move", 1, "#/texts/1"),
            "alpha new move added",
        )

        extraction = report.extraction_metrics
        serialization = report.serialization_metrics
        self.assertEqual(
            (
                extraction.source_token_count,
                extraction.target_token_count,
                extraction.normalized_match_count,
                extraction.unexplained_deletion_count,
                extraction.substitution_count,
            ),
            (4, 3, 2, 1, 1),
        )
        self.assertEqual(
            (
                serialization.source_token_count,
                serialization.target_token_count,
                serialization.normalized_match_count,
                serialization.unexpected_insertion_count,
            ),
            (3, 4, 3, 1),
        )

    def test_report_version_and_legacy_coverage_are_explicit(self) -> None:
        report = report_for("alpha lost", qr.TextSource("alpha", 1), "alpha")

        self.assertEqual(report.report_version, 2)
        self.assertEqual(report.coverage, report.legacy_coverage)
        self.assertEqual(report.legacy_coverage, 50.0)
        self.assertEqual(report.extraction_metrics.source_token_count, 2)
        self.assertEqual(report.serialization_metrics.source_token_count, 1)

    def test_markdown_separates_stages_and_reports_structural_integrity(self) -> None:
        report = report_for(
            "pdf lost",
            qr.TextSource("pdf changed", 1, "#/texts/1"),
            "pdf changed added",
        )

        rendered = qr.render_markdown(report)

        self.assertIn("Quality Report v2", rendered)
        self.assertIn("Extraction: PDF text layer → Docling", rendered)
        self.assertIn("Serialization: Docling → Markdown", rendered)
        self.assertIn("Structural and artifact integrity", rendered)
        self.assertIn("**PASS.**", rendered)
        self.assertIn("Valid decoded images", rendered)
        self.assertIn("not verified document accuracy", rendered)

    def test_issue_rendering_keeps_raw_normalized_context_and_unknowns(self) -> None:
        provenance = SimpleNamespace(page_no=None, charspan=(0, 4))
        report = report_for(
            "final",
            qr.TextSource(
                "ﬁnal",
                None,
                "#/texts/7",
                (provenance,),
            ),
            "",
        )

        rendered = qr.render_markdown(report)

        self.assertIn("raw `ﬁnal`", rendered)
        self.assertIn("normalized `final`", rendered)
        self.assertIn("page unknown", rendered)
        self.assertIn("block `#/texts/7`", rendered)
        self.assertIn("provenance", rendered)
        self.assertIn("Source context", rendered)

    def test_console_is_concise_and_separates_both_stages(self) -> None:
        console = qr.render_console(
            report_for("alpha", qr.TextSource("alpha", 1), "alpha")
        )

        self.assertIn("Quality Report v2", console)
        self.assertIn("Extraction", console)
        self.assertIn("Serialization", console)
        self.assertIn("Structure: PASS", console)
        self.assertIn("images 0/0", console)
        self.assertNotIn("legacy", console.lower())
        self.assertLessEqual(len(console.splitlines()), 3)

    def test_structural_issues_and_artifact_dimensions_are_rendered(self) -> None:
        integrity = si.StructuralIntegrityReport(
            headings=si.CountComparison(1, 1),
            lists=si.CountComparison(0, 0),
            list_items=si.CountComparison(0, 0),
            tables=si.CountComparison(0, 0),
            table_cells=si.CountComparison(0, 0),
            links=si.CountComparison(0, 0),
            images=si.CountComparison(1, 1),
            issues=(
                si.IntegrityIssue(
                    "heading",
                    "changed_heading",
                    "level 2: Expected",
                    "level 1: Expected",
                    "Markdown line 1",
                ),
            ),
            artifacts=(
                si.ArtifactCheck(
                    "document_artifacts/figure.png",
                    "valid",
                    size_bytes=123,
                    format="PNG",
                    width=4,
                    height=5,
                ),
            ),
        )
        report = replace(
            report_for("alpha", qr.TextSource("alpha", 1), "alpha"),
            structural_integrity=integrity,
        )

        console = qr.render_console(report)
        rendered = qr.render_markdown(report)

        self.assertIn("Structure: ISSUES 1", console)
        self.assertIn("images 1/1", console)
        self.assertIn("changed_heading", rendered)
        self.assertIn("Markdown line 1", rendered)
        self.assertIn("document_artifacts/figure.png", rendered)
        self.assertIn("4 × 5", rendered)

    def test_ocr_only_pages_are_unverified_with_not_applicable_extraction(self) -> None:
        report = report_for("", qr.TextSource("ocr text", 1), "ocr text")

        console = qr.render_console(report)
        rendered = qr.render_markdown(report)

        self.assertIsNone(report.extraction_metrics.normalized_exact_transfer_rate)
        self.assertIn("n/a", console.lower())
        self.assertIn("unverified", console.lower())
        self.assertIn("cannot verify", rendered)
        self.assertNotIn("verified accuracy", rendered)


if __name__ == "__main__":
    unittest.main()
