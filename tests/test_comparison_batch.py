"""Explicit pair planning, failure isolation and batch report protection."""
import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from pdf_receipt import cli, comparison as cp, comparison_batch as batch


class BatchTests(unittest.TestCase):
    def setup_files(self, root):
        pdf = Path(__file__).parent / 'fixtures/formulas/formula_equations.pdf'
        for folder in ('one', 'two'):
            (root/folder).mkdir()
            (root/folder/'same.pdf').write_bytes(pdf.read_bytes())
            (root/folder/'same.md').write_text('İstanbul summary', encoding='utf-8')
        (root/'out').mkdir()
        return [{'id': folder, 'pdf': f'{folder}/same.pdf', 'markdown': f'{folder}/same.md'} for folder in ('one','two')]

    def manifest(self, root, pairs):
        path = root/'pairs.json'
        path.write_text(json.dumps({'schema_version':'1.0','pairs':pairs}), encoding='utf-8')
        return path

    def run_cli(self, manifest, root):
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            return cli.main(['compare-batch',str(manifest),'--output-dir',str(root/'out')])

    def test_duplicate_stems_paths_and_single_pair_consistency(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder); pairs=self.setup_files(root)
            manifest=self.manifest(root,pairs)
            with patch('pdf_receipt.cli.create_docling_runtime',side_effect=AssertionError('no models')):
                self.assertEqual(self.run_cli(manifest,root),0)
            data=json.loads((root/'out/batch_summary.json').read_text(encoding='utf-8'))
            self.assertEqual(data['totals'],{'pairs':2,'succeeded':2,'failed':0})
            self.assertTrue(all(row['has_differences'] for row in data['pairs']))
            result=cp.read_comparison(root/'one/same.pdf',root/'one/same.md')
            self.assertEqual((root/'out/pair-one.md').read_text(encoding='utf-8'),cp.render_markdown(result))
            self.assertEqual([p.id for p in batch.load_pairs(manifest)],['one','two'])

    def test_missing_and_invalid_markdown_do_not_stop_other_pairs(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder); pairs=self.setup_files(root)
            (root/'two/same.md').write_bytes(b'\xff')
            pairs.insert(0,{'id':'missing','pdf':'absent.pdf','markdown':'one/same.md'})
            self.assertEqual(self.run_cli(self.manifest(root,pairs),root),1)
            data=json.loads((root/'out/batch_summary.json').read_text())
            self.assertEqual([r['status'] for r in data['pairs']],['failed','success','failed'])
            self.assertIsNone(data['pairs'][0]['has_differences'])

    def test_duplicate_ids_pairs_and_existing_outputs_stop_before_writes(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder); pairs=self.setup_files(root)
            cases=[pairs+[dict(pairs[0],id='ONE')], pairs+[dict(pairs[0],id='third')]]
            for items in cases:
                self.assertEqual(self.run_cli(self.manifest(root,items),root),1)
                self.assertEqual(list((root/'out').iterdir()),[])
            protected=root/'out/pair-two.json'; protected.write_text('keep')
            self.assertEqual(self.run_cli(self.manifest(root,pairs),root),1)
            self.assertEqual(list((root/'out').iterdir()),[protected])
            self.assertEqual(protected.read_text(),'keep')

    def test_input_output_collision_even_with_missing_input_is_protected(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder); pairs=self.setup_files(root)
            pairs[1]['markdown']='out/pair-one.md'
            self.assertEqual(self.run_cli(self.manifest(root,pairs),root),1)
            self.assertFalse((root/'out/pair-one.md').exists())

    def test_write_failure_keeps_other_pairs_and_successful_report(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder); pairs=self.setup_files(root); manifest=self.manifest(root,pairs)
            original=Path.open
            def failing(path,mode='r',*args,**kwargs):
                if mode=='x' and path.name=='pair-one.json': raise OSError('disk error')
                return original(path,mode,*args,**kwargs)
            with patch.object(Path,'open',failing): self.assertEqual(self.run_cli(manifest,root),1)
            data=json.loads((root/'out/batch_summary.json').read_text())
            self.assertEqual([r['status'] for r in data['pairs']],['failed','success'])
            self.assertTrue((root/'out/pair-one.md').exists())

    def test_schema_rejects_unknown_fields_duplicate_keys_and_empty_lists(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder); path=root/'pairs.json'
            for text in ('{"schema_version":"2.0","pairs":[]}', '{"schema_version":"1.0","pairs":[]}',
                         '{"schema_version":"1.0","pairs":[],"pairs":[]}'):
                path.write_text(text)
                with self.assertRaises(ValueError): batch.load_pairs(path)

    def test_racing_output_is_preserved_and_later_pair_continues(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder); pairs=self.setup_files(root); manifest=self.manifest(root,pairs)
            original=cp.read_comparison
            def racing(*args,**kwargs):
                result=original(*args,**kwargs)
                if args[0].parent.name=='one':
                    (root/'out/pair-one.json').write_text('concurrent result')
                return result
            with patch.object(cp,'read_comparison',side_effect=racing):
                self.assertEqual(self.run_cli(manifest,root),1)
            self.assertEqual((root/'out/pair-one.json').read_text(),'concurrent result')
            self.assertTrue((root/'out/pair-two.json').exists())

    def test_deterministic_summaries_and_no_change_success(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder); pairs=self.setup_files(root)
            result=cp.read_comparison(root/'one/same.pdf',root/'one/same.md')
            (root/'one/same.md').write_text('\n'.join(result.pdf.pages),encoding='utf-8')
            manifest=self.manifest(root,pairs[:1])
            self.assertEqual(self.run_cli(manifest,root),0)
            first=(root/'out/batch_summary.json').read_bytes()
            (root/'second-out').mkdir()
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(batch.main([str(manifest),'--output-dir',str(root/'second-out')]),0)
            self.assertEqual(first,(root/'second-out/batch_summary.json').read_bytes())
            self.assertFalse(json.loads(first)['pairs'][0]['has_differences'])

    @unittest.skipUnless(__import__('os').name=='nt','Windows path syntax')
    def test_windows_backslashes_and_unicode_paths(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder); pairs=self.setup_files(root)
            (root/'one').rename(root/'örnek')
            pairs[0].update(pdf='örnek\\same.pdf',markdown='örnek\\same.md')
            self.assertEqual(self.run_cli(self.manifest(root,pairs),root),0)

    def test_unverified_is_success_and_summary_write_failure_returns_failure(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder); pairs=self.setup_files(root)
            scan=Path(__file__).parent/'fixtures/scanned_page.pdf'
            (root/'one/same.pdf').write_bytes(scan.read_bytes())
            original=Path.open
            def failing(path,mode='r',*args,**kwargs):
                if mode=='x' and path.name=='batch_summary.md': raise OSError('summary error')
                return original(path,mode,*args,**kwargs)
            with patch.object(Path,'open',failing):
                self.assertEqual(self.run_cli(self.manifest(root,pairs),root),1)
            data=json.loads((root/'out/batch_summary.json').read_text())
            self.assertEqual(data['pairs'][0]['status'],'success')
            self.assertEqual(data['pairs'][0]['unverified_pages'],[1])


if __name__=='__main__':
    unittest.main()
