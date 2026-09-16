"""Versioned evidence, shared computation and multi-output file protection."""
import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from pdf_receipt import comparison as cp, quality_report as qr
from pdf_receipt.comparison_json import render_json


class ComparisonJsonTests(unittest.TestCase):
    def test_complete_evidence_and_bounded_groups_agree_with_markdown(self):
        result = cp.build_comparison(qr.PdfText('source.pdf', ('a keep b c stop d', '')),
                                     'keep stop', Path('sample.md'), issue_limit=1)
        data = json.loads(render_json(result))
        self.assertEqual(data['schema_version'], '1.0')
        self.assertEqual(data['counts']['missing'], 4)
        self.assertEqual(data['rates']['loss'], {'numerator': 4, 'denominator': 6, 'value': 4/6})
        self.assertEqual(data['coverage']['unverified_pages'], [2])
        self.assertEqual(data['truncation']['groups_omitted'], 2)
        self.assertEqual(data['truncation']['operations_omitted'], 0)
        self.assertEqual(len(data['operations']), 6)
        self.assertIn('Missing occurrences: 4', cp.render_markdown(result))
        self.assertEqual(data['displayed_groups'][0]['operation_indexes'], [2, 3])
        self.assertEqual(render_json(result), render_json(result))

    def test_unicode_raw_positions_images_and_empty_denominators(self):
        result = cp.build_comparison(qr.PdfText('source.pdf', ('',)),
                                     'caf&eacute;\r\nİ ![x](absent.png)', Path('sample.md'))
        data = json.loads(render_json(result))
        self.assertIsNone(data['rates']['accepted_transfer']['value'])
        self.assertEqual(data['target_tokens'][0]['raw_text'], 'caf&eacute;')
        self.assertEqual(data['target_tokens'][1]['line'], 2)
        self.assertEqual(data['target_tokens'][1]['raw_text'], 'İ')
        self.assertIsNone(data['target_tokens'][1]['page'])
        self.assertEqual(data['images'][0]['status'], 'missing_local_target')

    def inputs(self, root):
        pdf = Path(__file__).parent / 'fixtures/formulas/formula_equations.pdf'
        md = root / 'input.md'
        md.write_text('original summary', encoding='utf-8')
        return pdf, md

    def test_empty_target_rate_and_operation_references(self):
        result = cp.build_comparison(qr.PdfText('source.pdf', ('one one',)), '', Path('sample.md'))
        data = json.loads(render_json(result))
        self.assertIsNone(data['rates']['addition']['value'])
        self.assertEqual(data['target_tokens'], [])
        self.assertEqual([op['source_index'] for op in data['operations']], [0, 1])
        self.assertTrue(all(op['target_index'] is None for op in data['operations']))

    def test_partial_write_is_reported_and_other_output_survives(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            pdf, md = self.inputs(root)
            original_open = Path.open
            class PartialWriter:
                def __init__(self, handle):
                    self.handle = handle
                def __enter__(self):
                    return self
                def __exit__(self, *args):
                    self.handle.close()
                def write(self, text):
                    self.handle.write(text[:5])
                    raise OSError('disk full')
            def partial_open(path, mode='r', *args, **kwargs):
                handle = original_open(path, mode, *args, **kwargs)
                return PartialWriter(handle) if mode == 'x' and path.suffix == '.json' else handle
            errors = io.StringIO()
            with patch.object(Path, 'open', partial_open), contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(errors):
                self.assertEqual(cp.main([str(pdf), str(md), '--json-report', str(root/'report.json')]), 1)
            self.assertEqual(len((root/'report.json').read_text()), 5)
            self.assertTrue((root/'input_comparison.md').exists())
            self.assertIn('partial file may remain', errors.getvalue())

    def test_cli_computes_once_and_both_outputs_are_valid(self):
        with tempfile.TemporaryDirectory() as folder, contextlib.redirect_stdout(io.StringIO()):
            root = Path(folder)
            pdf, md = self.inputs(root)
            with patch.object(cp, 'compare_text', wraps=cp.compare_text) as compare, patch.object(cp, 'image_checks', wraps=cp.image_checks) as images:
                self.assertEqual(cp.main([str(pdf), str(md), '--json-report', str(root/'report.json')]), 0)
            self.assertEqual(compare.call_count, 1)
            self.assertEqual(images.call_count, 1)
            self.assertEqual(json.loads((root/'report.json').read_text(encoding='utf-8'))['schema_version'], '1.0')
            self.assertTrue((root/'input_comparison.md').exists())

    def test_collisions_and_missing_parent_fail_before_any_write(self):
        with tempfile.TemporaryDirectory() as folder, contextlib.redirect_stderr(io.StringIO()):
            root = Path(folder)
            pdf, md = self.inputs(root)
            report = root/'input_comparison.md'
            for target in (md, pdf, report, root/'missing/report.json'):
                self.assertEqual(cp.main([str(pdf), str(md), '--json-report', str(target)]), 1)
                self.assertFalse(report.exists())
            existing = root/'existing.json'
            existing.write_text('preserve', encoding='utf-8')
            self.assertEqual(cp.main([str(pdf), str(md), '--json-report', str(existing)]), 1)
            self.assertEqual(existing.read_text(), 'preserve')

    def test_each_write_failure_preserves_the_other_success(self):
        for failed_suffix in ('.md', '.json'):
            with self.subTest(failed_suffix=failed_suffix), tempfile.TemporaryDirectory() as folder:
                root = Path(folder)
                pdf, md = self.inputs(root)
                original_open = Path.open
                def failing_open(path, mode='r', *args, **kwargs):
                    if mode == 'x' and path.suffix == failed_suffix:
                        raise OSError('simulated write failure')
                    return original_open(path, mode, *args, **kwargs)
                errors = io.StringIO()
                with patch.object(Path, 'open', failing_open), contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(errors):
                    self.assertEqual(cp.main([str(pdf), str(md), '--json-report', str(root/'report.json')]), 1)
                self.assertIn('Other completed outputs are retained', errors.getvalue())
                retained = root / ('report.json' if failed_suffix == '.md' else 'input_comparison.md')
                self.assertTrue(retained.exists())
                self.assertEqual(md.read_text(), 'original summary')

    def test_file_appearing_after_preflight_is_not_overwritten(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            pdf, md = self.inputs(root)
            target = root/'report.json'
            build = cp.build_comparison
            def concurrent_output(*args, **kwargs):
                result = build(*args, **kwargs)
                target.write_text('external result', encoding='utf-8')
                return result
            with patch.object(cp, 'build_comparison', side_effect=concurrent_output), contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(cp.main([str(pdf), str(md), '--json-report', str(target)]), 1)
            self.assertEqual(target.read_text(), 'external result')
            self.assertTrue((root/'input_comparison.md').exists())


if __name__ == '__main__':
    unittest.main()
