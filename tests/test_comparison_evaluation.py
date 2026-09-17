"""Original facts and error controls for the development adapter."""
import contextlib
from copy import deepcopy
from hashlib import sha256
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from development import evaluate_comparison as ev
from pdf_receipt import comparison as cp, quality_report as qr
from pdf_receipt.comparison_json import render_json


def fact(kind, **fields):
    return dict(id='original-fact', kind=kind, basis='independent', provenance='Original authored test expectation',
                side='target', page=None, **fields)


class EvaluationTests(unittest.TestCase):
    def test_checked_in_original_controls_pass_with_pinned_bytes(self):
        path=Path(__file__).parent/'fixtures/comparison_evaluation/manifest.json'
        data=ev.evaluate(ev.load_manifest(path),path.parent.resolve())
        self.assertEqual([case['status'] for case in data['cases']],['pass']*4)
        self.assertTrue(all(case['inputs_verified'] for case in data['cases']))

    def data(self, source, target):
        return json.loads(render_json(cp.build_comparison(qr.PdfText('original.pdf',(source,)),target,Path('original.md'))))

    def test_retained_deleted_repeated_and_moved_facts(self):
        for target, count in [('alpha beta gamma',1),('gamma',0),('alpha beta alpha beta gamma',2),('gamma alpha beta',1)]:
            with self.subTest(target=target):
                data=self.data('alpha beta gamma',target)
                check=fact('sequence_count',tokens=['alpha','beta'],count=count)
                self.assertEqual(ev.evaluate_fact(data,check)['status'],'pass')
        data=self.data('alpha beta gamma','gamma alpha beta')
        check=fact('sequence_order',before=['gamma'],after=['alpha','beta'])
        self.assertEqual(ev.evaluate_fact(data,check)['status'],'pass')
        check['before'],check['after']=check['after'],check['before']
        self.assertEqual(ev.evaluate_fact(data,check)['status'],'fail')

    def test_exact_operation_span_has_raw_evidence_and_does_not_hide_failure(self):
        data=self.data('alpha beta gamma','gamma')
        check=fact('operation_span',span=[0,10],operation='deletion',count=2)
        check.update(side='source',page=1,basis='regression')
        row=ev.evaluate_fact(data,check)
        self.assertEqual(row['status'],'pass')
        self.assertEqual([t['raw_text'] for t in row['observed']['tokens']],['alpha','beta'])
        check['operation']='match'
        self.assertEqual(ev.evaluate_fact(data,check)['status'],'fail')
        check['span']=[1,10]
        self.assertEqual(ev.evaluate_fact(data,check)['status'],'error')

    def test_ambiguous_order_and_unverified_source_are_errors(self):
        data=self.data('alpha','alpha alpha beta')
        self.assertEqual(ev.evaluate_fact(data,fact('sequence_order',before=['alpha'],after=['beta']))['status'],'error')
        check=fact('sequence_count',tokens=['absent'],count=0)
        check.update(side='source',page=1)
        self.assertEqual(ev.evaluate_fact(self.data('',''),check)['status'],'error')
        check['page']=2
        self.assertEqual(ev.evaluate_fact(data,check)['status'],'error')

    def test_occurrence_count_is_nonoverlapping_and_unicode_is_explicit(self):
        data=self.data('','echo echo echo caf&eacute; İ')
        self.assertEqual(ev.evaluate_fact(data,fact('sequence_count',tokens=['echo','echo'],count=1))['status'],'pass')
        self.assertEqual(ev.evaluate_fact(data,fact('sequence_count',tokens=['café','i\u0307'],count=1))['status'],'pass')

    def test_order_rejects_overlapping_anchor_occurrences(self):
        data = self.data('echo echo echo end', 'echo echo echo end')
        for side, page in [('source', 1), ('target', None)]:
            for before, after, ambiguous in [
                (['echo', 'echo'], ['end'], 'before'),
                (['end'], ['echo', 'echo'], 'after'),
            ]:
                with self.subTest(side=side, ambiguous=ambiguous):
                    check = fact('sequence_order', before=before, after=after)
                    check.update(side=side, page=page)
                    row = ev.evaluate_fact(data, check)
                    self.assertEqual(row['status'], 'error')
                    self.assertIn('Ambiguous ordering anchors', row['error'])
                    self.assertEqual(row['observed'][ambiguous], [[0, 1], [1, 2]])

    def make_manifest(self, root):
        pdf=Path(__file__).parent/'fixtures/formulas/formula_equations.pdf'
        md=root/'original.md'; md.write_text('alpha beta',encoding='utf-8')
        case=dict(id='original',dataset='Original test',revision='1',sample_id='formula-fixture',terms='Repository MIT original fixture',
                  provenance='Independently authored Markdown',category='controlled',
                  pdf={'path':str(pdf.resolve()),'sha256':sha256(pdf.read_bytes()).hexdigest()},
                  markdown={'path':md.name,'sha256':sha256(md.read_bytes()).hexdigest()},
                  facts=[fact('sequence_count',tokens=['alpha','beta'],count=1)])
        path=root/'manifest.json'
        path.write_text(json.dumps(dict(schema_version='1.0',case_profile='unicode',cases=[case])),encoding='utf-8')
        return path

    def test_hash_mismatch_blocks_comparison_and_preserves_fact_id(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder); path=self.make_manifest(root); manifest=ev.load_manifest(path)
            (root/'original.md').write_text('changed')
            with patch.object(cp,'read_comparison',side_effect=AssertionError('must not run')):
                data=ev.evaluate(manifest,root)
            self.assertEqual(data['cases'][0]['status'],'error')
            self.assertEqual(data['cases'][0]['facts'][0]['id'],'original-fact')
            self.assertFalse(data['cases'][0]['inputs_verified'])

    def test_change_during_comparison_invalidates_all_facts(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder); path=self.make_manifest(root); manifest=ev.load_manifest(path)
            original=cp.read_comparison
            def mutate(*args,**kwargs):
                result=original(*args,**kwargs)
                (root/'original.md').write_text('changed')
                return result
            with patch.object(cp,'read_comparison',side_effect=mutate): data=ev.evaluate(manifest,root)
            self.assertEqual(data['cases'][0]['facts'][0]['status'],'error')

    def test_failed_expectation_continues_and_cli_preserves_outputs(self):
        with tempfile.TemporaryDirectory() as folder, contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            root=Path(folder); path=self.make_manifest(root); manifest=ev.load_manifest(path)
            second=deepcopy(manifest['cases'][0]); second['id']='failed'; second['facts'][0]['count']=2
            manifest['cases'].insert(0,second); path.write_text(json.dumps(manifest))
            report=root/'report.json'
            self.assertEqual(ev.main([str(path),'--report',str(report)]),1)
            saved=report.read_bytes(); data=json.loads(saved)
            self.assertEqual([r['status'] for r in data['cases']],['fail','pass'])
            self.assertEqual(ev.main([str(path),'--report',str(report)]),1)
            self.assertEqual(saved,report.read_bytes())
            self.assertEqual(ev.main([str(path),'--report',str(root/'original.md')]),1)

    def test_schema_rejects_duplicate_unknown_and_invalid_facts(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder); path=self.make_manifest(root); original=ev.load_manifest(path)
            for edit in ('version','fact','duplicate','extra'):
                data=deepcopy(original)
                if edit=='version': data['schema_version']='9'
                if edit=='fact': data['cases'][0]['facts'][0]['count']=True
                if edit=='duplicate': data['cases']*=2
                if edit=='extra': data['cases'][0]['guess']=True
                path.write_text(json.dumps(data))
                with self.assertRaises(ValueError): ev.load_manifest(path)

    def test_cli_success_and_missing_input_error_are_distinct(self):
        with tempfile.TemporaryDirectory() as folder, contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            root=Path(folder); path=self.make_manifest(root)
            self.assertEqual(ev.main([str(path),'--report',str(root/'passed.json')]),0)
            (root/'original.md').unlink()
            self.assertEqual(ev.main([str(path),'--report',str(root/'error.json')]),1)
            row=json.loads((root/'error.json').read_text())['cases'][0]
            self.assertEqual(row['facts'][0]['status'],'error')

    def test_report_race_does_not_overwrite_and_write_failure_is_nonzero(self):
        with tempfile.TemporaryDirectory() as folder, contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            root=Path(folder); path=self.make_manifest(root); report=root/'report.json'
            evaluate=ev.evaluate
            def race(*args,**kwargs):
                data=evaluate(*args,**kwargs)
                report.write_text('preserve')
                return data
            with patch.object(ev,'evaluate',side_effect=race):
                self.assertEqual(ev.main([str(path),'--report',str(report)]),1)
            self.assertEqual(report.read_text(),'preserve')
            original=Path.open
            def failed(path,mode='r',*args,**kwargs):
                if mode=='x': raise OSError('write error')
                return original(path,mode,*args,**kwargs)
            with patch.object(Path,'open',failed):
                self.assertEqual(ev.main([str(path),'--report',str(root/'new.json')]),1)


if __name__=='__main__':
    unittest.main()
