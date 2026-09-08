from __future__ import annotations

import time
import tracemalloc
import unittest
from pathlib import Path
from types import SimpleNamespace

from pdftomd import alignment
from pdftomd import quality_report as qr
from pdftomd import structural_integrity as si


FIXTURES = Path(__file__).resolve().parent / "fixtures"


def tokens(
    text: str,
    *,
    page_no: int | None = 1,
    block_id: str | None = None,
    provenance=(),
    case_profile: qr.CaseProfile = "unicode",
    character_boxes=(),
    spatial_regions=(),
) -> tuple[qr.Token, ...]:
    return qr.tokenize(
        text,
        page_no=page_no,
        block_id=block_id,
        provenance=provenance,
        case_profile=case_profile,
        character_boxes=character_boxes,
        spatial_regions=spatial_regions,
    )


def operations_of(
    result: alignment.AlignmentResult,
    operation_type: alignment.OperationType,
) -> list[alignment.AlignmentOperation]:
    return [operation for operation in result.operations if operation.type == operation_type]


def transferred(result: alignment.AlignmentResult) -> list[alignment.AlignmentOperation]:
    return [
        operation
        for operation in result.operations
        if operation.type in {alignment.OperationType.MATCH, alignment.OperationType.ORDER_RISK}
    ]


def word_boxes(*left_edges: float) -> tuple[qr.SpatialBox | None, ...]:
    """Build one character box per letter for space-separated four-letter words."""
    boxes: list[qr.SpatialBox | None] = []
    for word_index, left in enumerate(left_edges):
        if word_index:
            boxes.append(None)
        boxes.extend(
            qr.SpatialBox(left + offset, 10.0, left + offset + 0.8, 11.0)
            for offset in range(4)
        )
    return tuple(boxes)


class OccurrenceAlignmentTests(unittest.TestCase):
    def test_repeated_target_prefix_is_one_insertion_not_a_lost_source(self) -> None:
        result = alignment.align_serialization(
            tokens("alpha echo"),
            tokens("echo alpha echo"),
            case_profile="unicode",
        )

        self.assertEqual(len(transferred(result)), 2)
        self.assertEqual(len(operations_of(result, alignment.OperationType.INSERTION)), 1)
        self.assertFalse(operations_of(result, alignment.OperationType.DELETION))
        self.assertFalse(operations_of(result, alignment.OperationType.SUBSTITUTION))
        self.assertFalse(operations_of(result, alignment.OperationType.ORDER_RISK))

    def test_repeated_source_suffix_preserves_common_reordered_occurrences(self) -> None:
        result = alignment.align_serialization(
            tokens("alpha echo echo"),
            tokens("echo alpha"),
            case_profile="unicode",
        )

        self.assertEqual(len(transferred(result)), 2)
        deletions = operations_of(result, alignment.OperationType.DELETION)
        self.assertEqual(
            [operation.source_token.normalized_text for operation in deletions],
            ["echo"],
        )
        self.assertEqual(len(operations_of(result, alignment.OperationType.ORDER_RISK)), 1)
        self.assertFalse(operations_of(result, alignment.OperationType.INSERTION))
        self.assertFalse(operations_of(result, alignment.OperationType.SUBSTITUTION))

    def test_symmetric_repeated_source_prefix_is_one_deletion(self) -> None:
        result = alignment.align_serialization(
            tokens("echo alpha echo"),
            tokens("alpha echo"),
            case_profile="unicode",
        )

        self.assertEqual(len(transferred(result)), 2)
        self.assertEqual(len(operations_of(result, alignment.OperationType.DELETION)), 1)
        self.assertFalse(operations_of(result, alignment.OperationType.INSERTION))
        self.assertFalse(operations_of(result, alignment.OperationType.SUBSTITUTION))
        self.assertFalse(operations_of(result, alignment.OperationType.ORDER_RISK))

    def test_symmetric_repeated_target_suffix_preserves_reordered_occurrences(self) -> None:
        result = alignment.align_serialization(
            tokens("echo alpha"),
            tokens("alpha echo echo"),
            case_profile="unicode",
        )

        self.assertEqual(len(transferred(result)), 2)
        self.assertEqual(len(operations_of(result, alignment.OperationType.INSERTION)), 1)
        self.assertEqual(len(operations_of(result, alignment.OperationType.ORDER_RISK)), 1)
        self.assertFalse(operations_of(result, alignment.OperationType.DELETION))
        self.assertFalse(operations_of(result, alignment.OperationType.SUBSTITUTION))

    def test_repeat_repeat_to_repeat_is_one_match_and_one_deletion(self) -> None:
        result = alignment.align_extraction(
            tokens("repeat repeat"),
            tokens("repeat"),
            case_profile="unicode",
        )

        self.assertEqual(len(operations_of(result, alignment.OperationType.MATCH)), 1)
        self.assertEqual(len(operations_of(result, alignment.OperationType.DELETION)), 1)
        self.assertEqual(
            sorted(
                operation.source_index
                for operation in result.operations
                if operation.source_index is not None
            ),
            [0, 1],
        )

    def test_repetitions_across_pages_cannot_reuse_one_docling_occurrence(self) -> None:
        source = qr.tokenize_sources(
            (qr.TextSource("repeat", 1), qr.TextSource("repeat", 2))
        )
        target = tokens("repeat", page_no=1, block_id="#/texts/1")

        result = alignment.align_extraction(source, target, case_profile="unicode")

        self.assertEqual(len(operations_of(result, alignment.OperationType.MATCH)), 1)
        deletion = operations_of(result, alignment.OperationType.DELETION)
        self.assertEqual(len(deletion), 1)
        self.assertEqual(deletion[0].source_token.page_no, 2)

    def test_deletion_insertion_and_substitution_are_stable(self) -> None:
        cases = (
            ("alpha removed omega", "alpha omega", alignment.OperationType.DELETION),
            ("alpha omega", "alpha added omega", alignment.OperationType.INSERTION),
            ("alpha old omega", "alpha new omega", alignment.OperationType.SUBSTITUTION),
        )

        for source_text, target_text, expected in cases:
            with self.subTest(expected=expected):
                first = alignment.align_extraction(
                    tokens(source_text), tokens(target_text), case_profile="unicode"
                )
                second = alignment.align_extraction(
                    tokens(source_text), tokens(target_text), case_profile="unicode"
                )
                self.assertEqual(first, second)
                self.assertEqual(len(operations_of(first, expected)), 1)

    def test_pure_reorder_is_an_order_risk_without_hard_loss(self) -> None:
        result = alignment.align_extraction(
            tokens("one two three four"),
            tokens("three four one two"),
            case_profile="unicode",
        )

        risks = operations_of(result, alignment.OperationType.ORDER_RISK)
        self.assertTrue(risks)
        self.assertFalse(operations_of(result, alignment.OperationType.DELETION))
        self.assertFalse(operations_of(result, alignment.OperationType.INSERTION))
        self.assertTrue(
            all(operation.match_kind == alignment.MatchKind.REORDERED for operation in risks)
        )

    def test_scrambled_multicolumn_fixture_exercises_order_disagreement(self) -> None:
        pdf_text = qr.read_pdf_text(FIXTURES / "structure_layout.pdf")
        phrases = (
            "Left column first",
            "Left column second",
            "Right column third",
            "Right column fourth",
        )
        extracted = " ".join(pdf_text.pages)
        self.assertEqual(len(pdf_text.page_char_boxes[0]), len(pdf_text.pages[0]))
        self.assertTrue(all(box is not None for box in pdf_text.page_char_boxes[0]))
        positions = {phrase: extracted.index(phrase) for phrase in phrases}
        self.assertLess(positions[phrases[0]], positions[phrases[2]])
        self.assertLess(positions[phrases[2]], positions[phrases[1]])
        self.assertLess(positions[phrases[1]], positions[phrases[3]])
        source = qr.tokenize_pdf_pages(
            qr.PdfText("columns.pdf", (extracted,))
        )
        target = tokens(" ".join(phrases), page_no=1, block_id="spatial-order")

        result = alignment.align_extraction(source, target, case_profile="unicode")
        self.assertTrue(operations_of(result, alignment.OperationType.ORDER_RISK))


class ExplanationTests(unittest.TestCase):
    def test_identical_same_page_words_require_figure_region_overlap(self) -> None:
        source = tokens(
            "same same",
            page_no=1,
            character_boxes=word_boxes(0.0, 20.0),
        )
        figure = tokens(
            "same",
            page_no=1,
            block_id="#/pictures/1",
            spatial_regions=(
                qr.SpatialRegion(1, qr.SpatialBox(19.0, 9.0, 25.0, 12.0)),
            ),
        )

        result = alignment.align_extraction(
            source,
            (),
            case_profile="unicode",
            figure_tokens=figure,
        )

        deletions = operations_of(result, alignment.OperationType.DELETION)
        self.assertEqual(
            [operation.match_kind for operation in deletions],
            [alignment.MatchKind.UNEXPLAINED, alignment.MatchKind.FIGURE],
        )

    def test_page_and_text_without_geometry_are_not_spatially_verified(self) -> None:
        result = alignment.align_extraction(
            tokens("diagram", page_no=1),
            (),
            case_profile="unicode",
            figure_tokens=tokens("diagram", page_no=1, block_id="#/pictures/1"),
        )

        deletion = operations_of(result, alignment.OperationType.DELETION)[0]
        self.assertEqual(deletion.match_kind, alignment.MatchKind.UNEXPLAINED)
        self.assertIsNone(deletion.evidence_token)

    def test_one_figure_evidence_occurrence_cannot_explain_two_deletions(self) -> None:
        source = tokens(
            "diagram diagram",
            page_no=1,
            character_boxes=tuple(
                None if character == " " else qr.SpatialBox(index, 0, index + 0.8, 1)
                for index, character in enumerate("diagram diagram")
            ),
        )
        figure = tokens(
            "diagram",
            page_no=1,
            block_id="#/pictures/1",
            spatial_regions=(qr.SpatialRegion(1, qr.SpatialBox(0, 0, 7, 1)),),
        )

        result = alignment.align_extraction(
            source,
            (),
            case_profile="unicode",
            figure_tokens=figure,
        )

        deletions = operations_of(result, alignment.OperationType.DELETION)
        self.assertEqual(
            [operation.match_kind for operation in deletions],
            [alignment.MatchKind.FIGURE, alignment.MatchKind.UNEXPLAINED],
        )

    def test_figure_evidence_explains_only_one_same_page_occurrence(self) -> None:
        source = qr.tokenize_sources(
            (
                qr.TextSource(
                    "diagram",
                    1,
                    character_boxes=tuple(
                        qr.SpatialBox(index, 0, index + 0.8, 1) for index in range(7)
                    ),
                ),
                qr.TextSource(
                    "diagram",
                    2,
                    character_boxes=tuple(
                        qr.SpatialBox(index, 0, index + 0.8, 1) for index in range(7)
                    ),
                ),
            )
        )
        figure = tokens(
            "diagram",
            page_no=1,
            block_id="#/pictures/1",
            spatial_regions=(qr.SpatialRegion(1, qr.SpatialBox(0, 0, 7, 1)),),
        )

        result = alignment.align_extraction(
            source,
            (),
            case_profile="unicode",
            figure_tokens=figure,
        )

        deletions = operations_of(result, alignment.OperationType.DELETION)
        self.assertEqual(len(deletions), 2)
        self.assertEqual(
            [operation.match_kind for operation in deletions],
            [alignment.MatchKind.FIGURE, alignment.MatchKind.UNEXPLAINED],
        )
        self.assertIs(deletions[0].evidence_token.provenance, figure[0].provenance)

    def test_furniture_evidence_explains_only_one_same_page_occurrence(self) -> None:
        source = qr.tokenize_sources(
            (
                qr.TextSource(
                    "header",
                    1,
                    character_boxes=tuple(
                        qr.SpatialBox(index, 0, index + 0.8, 1) for index in range(6)
                    ),
                ),
                qr.TextSource(
                    "header",
                    2,
                    character_boxes=tuple(
                        qr.SpatialBox(index, 0, index + 0.8, 1) for index in range(6)
                    ),
                ),
            )
        )
        furniture = tokens(
            "header",
            page_no=2,
            block_id="#/texts/9",
            spatial_regions=(qr.SpatialRegion(2, qr.SpatialBox(0, 0, 6, 1)),),
        )

        result = alignment.align_extraction(
            source,
            (),
            case_profile="unicode",
            furniture_tokens=furniture,
        )

        deletions = operations_of(result, alignment.OperationType.DELETION)
        self.assertEqual(
            [operation.match_kind for operation in deletions],
            [alignment.MatchKind.UNEXPLAINED, alignment.MatchKind.FURNITURE],
        )


class TwoStageTests(unittest.TestCase):
    def test_extraction_and_serialization_failures_stay_in_separate_results(self) -> None:
        result = alignment.align_two_stage(
            tokens("pdf lost"),
            tokens("doc added", block_id="#/texts/2"),
            tokens("markdown extra", page_no=None),
            case_profile="unicode",
        )

        self.assertEqual(result.extraction.stage, alignment.AlignmentStage.EXTRACTION)
        self.assertEqual(result.serialization.stage, alignment.AlignmentStage.SERIALIZATION)
        self.assertNotEqual(result.extraction.operations, result.serialization.operations)
        self.assertTrue(
            any(
                operation.source_token.raw_text == "lost"
                for operation in result.extraction.operations
            )
        )
        self.assertTrue(
            any(
                operation.target_token.raw_text == "extra"
                for operation in result.serialization.operations
            )
        )

    def test_markdown_only_addition_has_offsets_but_unknown_page_and_provenance(self) -> None:
        target = qr.tokenize_markdown("source added")
        result = alignment.align_serialization(
            tokens("source", block_id="#/texts/1"),
            target,
            case_profile="unicode",
        )

        addition = operations_of(result, alignment.OperationType.INSERTION)[0]
        self.assertEqual(addition.target_token.raw_text, "added")
        self.assertEqual(addition.target_token.page_no, None)
        self.assertEqual(addition.target_token.provenance, ())
        self.assertEqual(
            "source added"[
                addition.target_token.source_span.start : addition.target_token.source_span.end
            ],
            "added",
        )

    def test_markdown_tokenizer_uses_visible_text_not_syntax_or_targets(self) -> None:
        markdown = (
            "# Heading\n"
            "1. numbered item\n"
            "[visible link](https://example.com/hidden-target)\n"
            "![hidden alt](report_artifacts/image_000001.png)\n"
            "[internal]: https://example.com/reference-target\n"
            "```python\ncode body\n```\n"
        )

        target = qr.tokenize_markdown(markdown)

        self.assertEqual(
            [token.normalized_text for token in target],
            ["heading", "numbered", "item", "visible", "link", "code", "body"],
        )
        self.assertTrue(all(token.page_no is None for token in target))

    def test_markdown_autolinks_remain_visible_with_exact_offsets(self) -> None:
        markdown = "Visit <https://example.com/path> and <user@example.com> now"

        target = qr.tokenize_markdown(markdown)

        self.assertEqual(
            [token.normalized_text for token in target],
            ["visit", "https", "example", "com", "path", "and", "user", "example", "com", "now"],
        )
        for token in target:
            self.assertEqual(
                markdown[token.source_span.start : token.source_span.end],
                token.raw_text,
            )

    def test_actual_html_tags_are_still_masked(self) -> None:
        target = qr.tokenize_markdown("before <span class='note'>inside</span> after")

        self.assertEqual(
            [token.normalized_text for token in target],
            ["before", "inside", "after"],
        )

    def test_quality_analysis_builds_both_stages_in_real_report_flow(self) -> None:
        provenance = SimpleNamespace(page_no=1, charspan=(0, 8))
        structure = qr.DocumentStructure(
            pages=1,
            tables=0,
            merged_cell_tables=0,
            figures=(),
            furniture_text="",
            content_sources=(
                qr.TextSource("document", 1, "#/texts/1", (provenance,)),
            ),
        )

        report = qr.analyze(
            qr.PdfText("sample.pdf", ("document",)),
            "document",
            structure,
            "quality",
            si.empty_report(),
        )

        self.assertIsNotNone(report.alignments)
        self.assertEqual(report.alignments.extraction.source_tokens[0].page_no, 1)
        self.assertEqual(
            report.alignments.serialization.source_tokens[0].provenance,
            (provenance,),
        )


class CaseProfileTests(unittest.TestCase):
    def test_unicode_alignment_matches_english_uppercase_i(self) -> None:
        result = alignment.align_extraction(
            tokens("RISK TITLE I"), tokens("risk title i"), case_profile="unicode"
        )

        self.assertTrue(
            all(operation.type == alignment.OperationType.MATCH for operation in result.operations)
        )

    def test_explicit_turkic_alignment_matches_both_i_pairs(self) -> None:
        result = alignment.align_extraction(
            tokens("I İ", case_profile="turkic"),
            tokens("ı i", case_profile="turkic"),
            case_profile="turkic",
        )

        self.assertTrue(
            all(operation.type == alignment.OperationType.MATCH for operation in result.operations)
        )

    def test_conflicting_case_profiles_are_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "case profile"):
            alignment.align_extraction(
                tokens("I", case_profile="unicode"),
                tokens("ı", case_profile="turkic"),
                case_profile="unicode",
            )


class AmbiguousHyphenTests(unittest.TestCase):
    def test_true_line_end_hyphenation_joins_only_with_local_context(self) -> None:
        source = tokens("before hyphen-\nation after")
        target = tokens("before hyphenation after")

        result = alignment.align_extraction(source, target, case_profile="unicode")

        middle = result.operations[1]
        self.assertEqual(middle.type, alignment.OperationType.MATCH)
        self.assertEqual(middle.match_kind, alignment.MatchKind.LINE_END_HYPHEN_JOIN)
        self.assertEqual(middle.hyphen_decisions, ("join",))

    def test_joined_candidate_without_context_is_not_accepted(self) -> None:
        result = alignment.align_extraction(
            tokens("hyphen-\nation"), tokens("hyphenation"), case_profile="unicode"
        )

        self.assertFalse(operations_of(result, alignment.OperationType.MATCH))

    def test_wrapped_genuine_compound_keeps_its_hyphen(self) -> None:
        result = alignment.align_extraction(
            tokens("before risk-\nbased after"),
            tokens("before risk-based after"),
            case_profile="unicode",
        )

        middle = result.operations[1]
        self.assertEqual(middle.type, alignment.OperationType.MATCH)
        self.assertEqual(middle.match_kind, alignment.MatchKind.NORMALIZED)
        self.assertEqual(middle.hyphen_decisions, ("keep",))

    def test_multiple_ambiguous_hyphens_choose_independent_forms_lazily(self) -> None:
        source = tokens("before alpha-\nbeta-\ngamma after")
        target = tokens("before alphabeta-gamma after")

        result = alignment.align_extraction(source, target, case_profile="unicode")

        middle = result.operations[1]
        self.assertEqual(middle.match_kind, alignment.MatchKind.LINE_END_HYPHEN_JOIN)
        self.assertEqual(middle.hyphen_decisions, ("join", "keep"))
        self.assertEqual(len(middle.source_token.line_end_hyphen_spans), 2)
        self.assertEqual(middle.source_token.line_end_parts, ("alpha", "beta", "gamma"))


class EvidenceAndBoundsTests(unittest.TestCase):
    def test_operation_retains_complete_token_evidence_and_bounded_context(self) -> None:
        first = SimpleNamespace(page_no=4, charspan=(2, 5))
        second = SimpleNamespace(page_no=5, charspan=(5, 8))
        source = tokens(
            "alpha raw omega",
            page_no=4,
            block_id="#/texts/7",
            provenance=(first, second),
        )
        target = tokens("alpha changed omega", page_no=4, block_id="markdown")

        result = alignment.align_extraction(source, target, case_profile="unicode")
        substitution = operations_of(result, alignment.OperationType.SUBSTITUTION)[0]

        self.assertEqual(substitution.source_index, 1)
        self.assertEqual(substitution.target_index, 1)
        self.assertEqual(substitution.source_token.raw_text, "raw")
        self.assertEqual(substitution.source_token.normalized_text, "raw")
        self.assertEqual(substitution.source_token.page_no, 4)
        self.assertEqual(substitution.source_token.block_id, "#/texts/7")
        self.assertEqual(substitution.source_token.provenance, (first, second))
        self.assertEqual(substitution.source_context, alignment.ContextRange(0, 3))
        self.assertEqual(substitution.target_context, alignment.ContextRange(0, 3))

    def test_docling_operation_retains_every_provenance_entry(self) -> None:
        first = SimpleNamespace(page_no=4, charspan=(0, 3))
        second = SimpleNamespace(page_no=5, charspan=(3, 7))
        docling = qr.tokenize_docling_items(
            (
                SimpleNamespace(
                    text="content",
                    self_ref="#/texts/8",
                    prov=(first, second),
                ),
            )
        )

        result = alignment.align_serialization(
            docling,
            qr.tokenize_markdown("content"),
            case_profile="unicode",
        )

        operation = result.operations[0]
        self.assertEqual(operation.source_token.block_id, "#/texts/8")
        self.assertEqual(operation.source_token.provenance, (first, second))

    def test_docling_tokens_align_on_their_charspan_pages(self) -> None:
        first = SimpleNamespace(page_no=1, charspan=(0, 7))
        second = SimpleNamespace(page_no=2, charspan=(8, 15))
        docling = qr.tokenize_docling_items(
            (
                SimpleNamespace(
                    text="pageone pagetwo",
                    self_ref="#/texts/8",
                    prov=(first, second),
                ),
            )
        )
        pdf = qr.tokenize_sources((qr.TextSource("pageone", 1), qr.TextSource("pagetwo", 2)))

        result = alignment.align_extraction(pdf, docling, case_profile="unicode")

        self.assertEqual([token.page_no for token in docling], [1, 2])
        self.assertEqual(docling[0].provenance, (first,))
        self.assertEqual(docling[1].provenance, (second,))
        self.assertEqual(len(operations_of(result, alignment.OperationType.MATCH)), 2)
        self.assertFalse(operations_of(result, alignment.OperationType.DELETION))
        self.assertFalse(operations_of(result, alignment.OperationType.INSERTION))

    def test_empty_sources_and_targets_are_stable(self) -> None:
        empty = alignment.align_extraction((), (), case_profile="unicode")
        only_source = alignment.align_extraction(
            tokens("source"), (), case_profile="unicode"
        )
        only_target = alignment.align_extraction(
            (), tokens("target"), case_profile="unicode"
        )

        self.assertEqual(empty.operations, ())
        self.assertEqual(only_source.operations[0].type, alignment.OperationType.DELETION)
        self.assertEqual(only_target.operations[0].type, alignment.OperationType.INSERTION)

    def test_highly_repeated_long_stream_is_not_affected_by_autojunk(self) -> None:
        source = tokens("echo " * 400 + "anchor")
        target = tokens("echo " * 399 + "anchor")

        result = alignment.align_extraction(source, target, case_profile="unicode")

        self.assertEqual(len(operations_of(result, alignment.OperationType.MATCH)), 400)
        self.assertEqual(len(operations_of(result, alignment.OperationType.DELETION)), 1)

    def test_100_and_500_page_streams_stay_within_generous_bounds(self) -> None:
        # These guardrails are deliberately much looser than observed timings;
        # docs/ALIGNMENT.md records measurements from the development machine.
        for page_count in (100, 500):
            with self.subTest(page_count=page_count):
                source = qr.tokenize_sources(
                    qr.TextSource("section echo echo value 42 end", page_no)
                    for page_no in range(1, page_count + 1)
                )
                target = qr.tokenize_sources(
                    qr.TextSource("section echo echo value 42 end", page_no)
                    for page_no in range(1, page_count + 1)
                )

                tracemalloc.start()
                started = time.perf_counter()
                result = alignment.align_extraction(
                    source, target, case_profile="unicode"
                )
                duration = time.perf_counter() - started
                _, peak = tracemalloc.get_traced_memory()
                tracemalloc.stop()

                self.assertEqual(len(result.operations), page_count * 6)
                self.assertLess(duration, 10.0)
                self.assertLess(peak, 128 * 1024 * 1024)

    def test_repeated_near_worst_case_serialization_stays_bounded(self) -> None:
        source = tokens("alpha " * 400)
        target = tokens("echo " * 400)

        tracemalloc.start()
        started = time.perf_counter()
        result = alignment.align_serialization(source, target, case_profile="unicode")
        duration = time.perf_counter() - started
        _, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()

        self.assertEqual(len(operations_of(result, alignment.OperationType.SUBSTITUTION)), 400)
        self.assertLess(duration, 15.0)
        self.assertLess(peak, 128 * 1024 * 1024)


if __name__ == "__main__":
    unittest.main()
