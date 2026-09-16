"""Grouping preserves occurrence evidence and only changes presentation."""
from collections import Counter
from dataclasses import replace
from pathlib import Path
import unittest

from pdf_receipt import alignment as al, comparison as cp, quality_report as qr
from pdf_receipt.comparison_groups import group_differences


class ComparisonGroupTests(unittest.TestCase):
    def result(self, pages, markdown):
        return cp.compare_text(qr.PdfText('source.pdf', tuple(pages)), markdown)

    def test_size_ranking_and_stable_ties(self):
        result = self.result(['a keep b c stop d'], 'keep stop')
        groups = group_differences(result)
        self.assertEqual([[op.source_token.raw_text for op in g.operations] for g in groups],
                         [['b', 'c'], ['a'], ['d']])
        self.assertEqual(groups, group_differences(result))

    def test_split_page_passage_keeps_page_local_evidence(self):
        groups = group_differences(self.result(['one two', 'three four'], ''))
        self.assertEqual(len(groups), 2)
        self.assertEqual([[op.source_token.page_no for op in g.operations] for g in groups],
                         [[1, 1], [2, 2]])

    def test_repeated_occurrences_are_retained_once(self):
        result = self.result(['echo echo echo'], 'echo')
        operations = [op for g in group_differences(result) for op in g.operations]
        self.assertEqual(len(operations), 2)
        self.assertEqual(len({op.source_index for op in operations}), 2)

    def test_mixed_edits_and_movement_keep_original_types_and_objects(self):
        result = self.result(['a b c d e'], 'b a c x e extra')
        operations = [op for g in group_differences(result) for op in g.operations]
        expected = [op for op in result.operations if op.type != al.OperationType.MATCH]
        self.assertEqual(Counter(map(id, operations)), Counter(map(id, expected)))
        self.assertIn(al.OperationType.ORDER_RISK, {op.type for op in operations})
        for group in group_differences(result):
            self.assertEqual(len({op.type for op in group.operations}), 1)

    def test_group_cap_and_empty_result(self):
        groups = group_differences(self.result([' '.join(f'w{i}' for i in range(85))], ''))
        self.assertEqual([len(g.operations) for g in groups], [40, 40, 5])
        self.assertEqual(group_differences(self.result(['same'], 'same')), ())

    def test_discontinuous_target_positions_split_movement_groups(self):
        baseline = self.result(['a b c'], 'a b c')
        operations = tuple(replace(op, type=al.OperationType.ORDER_RISK,
                                   match_kind=al.MatchKind.REORDERED,
                                   target_index=index, target_token=baseline.target_tokens[index])
                           for op, index in zip(baseline.operations, [0, 2, 1]))
        groups = group_differences(replace(baseline, operations=operations))
        self.assertEqual([len(g.operations) for g in groups], [1, 1, 1])

    def test_excerpt_bound_preserves_full_raw_occurrence_details(self):
        word = 'a' * 900
        report = cp.render_report(qr.PdfText('source.pdf', (word,)), '', Path('sample.md'))
        self.assertIn('excerpt truncated at 800 characters', report)
        self.assertIn('<code>' + word + '</code>', report)
        self.assertIn('raw span [0, 900)', report)

    def test_multiline_raw_entity_evidence_and_movement_label(self):
        report = cp.render_report(qr.PdfText('source.pdf', ('',)),
                                  'caf&eacute;\r\nsecond', Path('sample.md'))
        self.assertIn('Markdown lines 1-2', report)
        self.assertIn('Markdown line 2', report)
        self.assertIn('caf&amp;eacute;', report)
        moved = cp.render_report(qr.PdfText('source.pdf', ('a b c',)), 'b a c', Path('sample.md'))
        self.assertIn('Suspected movement (order risk, not verified loss)', moved)

    def test_report_group_limit_keeps_counts_and_complete_selected_details(self):
        report = cp.render_report(qr.PdfText('source.pdf', ('a keep b c stop d',)),
                                  'keep stop', Path('sample.md'), issue_limit=1)
        self.assertIn('Showing 1 of 3 groups; omitted 2 groups', report)
        self.assertIn('Missing occurrences: 4', report)
        self.assertIn('2 of 4 difference operations', report)
        self.assertIn('Occurrence details', report)
        self.assertIn('raw span [7, 8)', report)
        self.assertIn('raw span [9, 10)', report)


if __name__ == '__main__':
    unittest.main()
