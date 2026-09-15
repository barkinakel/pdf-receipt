from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from pdf_receipt import converter, manifest
from tests.test_cli import fake_convert, run_main, touch_pdf


class ManifestTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.pdf = self.root / "source.pdf"
        self.pdf.write_bytes(b"source one")
        self.output = converter.plan_output_paths([self.pdf], self.root / "output")[0][0]
        self.output.directory.mkdir()
        self.options = manifest.settings("quality", False, 1.0, True)
        self.output.markdown.write_text("# Heading\n", encoding="utf-8")
        self.output.json.write_text(json.dumps({"schema_name": "DoclingDocument", "name": "test"}), encoding="utf-8")
        self.output.report.write_text("Quality Report v2\n", encoding="utf-8")
        self.version_patch = patch("pdf_receipt.manifest.versions", return_value={
            "application": "test", "docling": "test"})
        self.version_patch.start()
        self.addCleanup(self.version_patch.stop)

    def record(self) -> None:
        manifest.complete(self.output, manifest.source_identity(self.pdf), self.options)

    def reusable(self) -> bool:
        return manifest.reusable(self.pdf, self.output, self.options)

    def test_complete_record_contains_identity_settings_and_expected_paths(self) -> None:
        self.record()
        self.assertTrue(self.reusable())
        payload = json.loads(manifest.manifest_path(self.output).read_text())
        self.assertTrue(payload["complete"])
        self.assertEqual(payload["source"]["size"], len(b"source one"))
        self.assertEqual(len(payload["source"]["sha256"]), 64)
        self.assertEqual(payload["settings"], self.options)
        self.assertEqual(payload["outputs"]["paths"]["artifacts"], "source_artifacts")
        self.assertEqual(payload["outputs"]["paths"]["report"], "source_report.md")

    def test_source_hash_detects_same_size_and_timestamp_change(self) -> None:
        self.record()
        timestamp = self.pdf.stat().st_mtime_ns
        self.pdf.write_bytes(b"source two")
        os.utime(self.pdf, ns=(timestamp, timestamp))
        self.assertFalse(self.reusable())

    def test_each_setting_and_version_change_requires_conversion(self) -> None:
        self.record()
        for key, value in (("profile", "fast"), ("formula", True),
                           ("image_scale", 1.5), ("report", False)):
            with self.subTest(setting=key):
                self.assertFalse(manifest.reusable(
                    self.pdf, self.output, {**self.options, key: value}))
        with patch("pdf_receipt.manifest.versions", return_value={"application": "new"}):
            self.assertFalse(self.reusable())

    def test_missing_corrupt_old_incomplete_and_wrong_shape_records_are_misses(self) -> None:
        self.assertFalse(self.reusable())
        self.record()
        path = manifest.manifest_path(self.output)
        original = json.loads(path.read_text())
        for payload in ("broken", "[]", "null", "{}",
                        json.dumps({**original, "complete": False}),
                        json.dumps({**original, "manifest_version": 0})):
            with self.subTest(payload=payload):
                path.write_text(payload)
                self.assertFalse(self.reusable())

    def test_each_required_export_is_hashed_and_must_exist(self) -> None:
        for path in (self.output.markdown, self.output.json, self.output.report):
            original = path.read_bytes()
            for replacement in (b"", b"x" * len(original), None):
                with self.subTest(path=path.name, replacement=replacement):
                    self.record()
                    if replacement is None:
                        path.unlink()
                    else:
                        path.write_bytes(replacement)
                    self.assertFalse(self.reusable())
                    path.write_bytes(original)

    def test_no_report_allows_absent_report_and_empty_markdown(self) -> None:
        self.options["report"] = False
        self.output.report.unlink()
        self.output.markdown.write_text("")
        self.record()
        self.assertTrue(self.reusable())

    def test_images_are_decoded_hashed_and_unrelated_files_are_untouched(self) -> None:
        from PIL import Image

        self.output.artifacts.mkdir()
        image = self.output.artifacts / "picture.png"
        Image.new("RGB", (3, 2), "red").save(image)
        self.output.markdown.write_text("![Image](source_artifacts/picture.png)")
        unrelated = self.output.artifacts / "notes.txt"
        unrelated.write_text("user notes")
        self.record()
        self.assertTrue(self.reusable())
        payload = json.loads(manifest.manifest_path(self.output).read_text())
        self.assertEqual(payload["outputs"]["artifact_paths"], ["source_artifacts/picture.png"])
        self.assertEqual(payload["outputs"]["files"]["source_artifacts/picture.png"]["size"],
                         image.stat().st_size)
        image.write_bytes(b"invalid image")
        self.assertFalse(self.reusable())
        self.assertEqual(unrelated.read_text(), "user notes")

    def test_json_only_images_are_required_and_outside_root_targets_are_rejected(self) -> None:
        for target in ("source_artifacts/missing.png", "../outside.png", "https://example.com/a.png"):
            with self.subTest(target=target):
                self.output.json.write_text(json.dumps({"schema_name": "DoclingDocument", "name": "test",
                    "pictures": [{"self_ref": "#/pictures/0", "label": "picture",
                                  "image": {"uri": target, "mimetype": "image/png", "dpi": 72,
                                            "size": {"width": 1, "height": 1}}}]}))
                with self.assertRaises(Exception):
                    self.record()

    def test_broken_local_markdown_link_prevents_completion(self) -> None:
        self.output.markdown.write_text("[Local](missing.txt)")
        with self.assertRaises(ValueError):
            self.record()

    def test_windows_json_image_paths_are_verified_without_rewriting_json(self) -> None:
        from PIL import Image

        self.output.artifacts.mkdir()
        Image.new("RGB", (1, 1), "blue").save(self.output.artifacts / "picture.png")
        payload = {"schema_name": "DoclingDocument", "name": "test",
                   "pictures": [{"self_ref": "#/pictures/0", "label": "picture",
                                 "image": {"uri": "source_artifacts\\picture.png",
                                           "mimetype": "image/png", "dpi": 72,
                                           "size": {"width": 1, "height": 1}}}]}
        self.output.json.write_text(json.dumps(payload))
        original = self.output.json.read_bytes()
        self.record()
        self.assertTrue(self.reusable())
        self.assertEqual(self.output.json.read_bytes(), original)
        (self.output.artifacts / "picture.png").unlink()
        self.assertFalse(self.reusable())

    def test_failed_atomic_replace_leaves_previous_record_and_no_temporary_file(self) -> None:
        self.record()
        original = manifest.manifest_path(self.output).read_bytes()
        with patch("pdf_receipt.manifest.os.replace", side_effect=OSError("locked")):
            with self.assertRaises(OSError):
                manifest.atomic_write(self.output, {"complete": False})
        self.assertEqual(manifest.manifest_path(self.output).read_bytes(), original)
        self.assertEqual(list(self.output.directory.glob(".pdf-receipt-*.tmp")), [])

    def test_active_lock_prevents_reuse_and_a_second_writer(self) -> None:
        self.record()
        with manifest.conversion_lock(self.output):
            self.assertFalse(self.reusable())
            with self.assertRaisesRegex(RuntimeError, "Conversion lock exists"):
                with manifest.conversion_lock(self.output):
                    self.fail("Second writer was allowed")
        self.assertTrue(self.reusable())

    def test_reuse_holds_lock_through_output_verification(self) -> None:
        self.record()
        real_inventory = manifest.inventory
        def inspect(output, report):
            with self.assertRaises(RuntimeError):
                with manifest.conversion_lock(output):
                    self.fail("Writer entered during verification")
            return real_inventory(output, report)
        with patch("pdf_receipt.manifest.inventory", side_effect=inspect):
            self.assertTrue(self.reusable())

    def runtime(self, report: bool = True) -> converter.DoclingRuntime:
        document = Mock()
        document.save_as_markdown.side_effect = lambda path, **_: path.write_text("# New\n")
        document.save_as_json.side_effect = lambda path, **_: path.write_text(
            json.dumps({"schema_name": "DoclingDocument", "name": "test"}))
        engine = Mock()
        engine.convert.return_value = SimpleNamespace(document=document)
        return converter.DoclingRuntime(engine, "referenced", report=report)

    def test_interrupted_reconversion_invalidates_previously_complete_outputs(self) -> None:
        self.record()
        runtime = self.runtime()
        runtime.converter.convert.side_effect = KeyboardInterrupt()
        with self.assertRaises(KeyboardInterrupt):
            converter.convert_pdf(runtime, self.pdf, self.output)
        self.assertFalse(self.reusable())
        self.assertFalse(manifest.lock_path(self.output).exists())

    def test_report_failure_is_nonfatal_and_never_reuses_an_old_report(self) -> None:
        self.record()
        with patch("pdf_receipt.converter.write_quality_report", side_effect=ValueError("failed")):
            result = converter.convert_pdf(self.runtime(), self.pdf, self.output)
        self.assertEqual(result.report_error, "failed")
        self.assertIsNotNone(result.manifest_error)
        self.assertFalse(self.reusable())

    def test_successful_conversion_completes_last_and_preserves_extra_files(self) -> None:
        self.options["report"] = False
        extra = self.output.directory / "notes.txt"
        extra.write_text("keep")
        result = converter.convert_pdf(self.runtime(report=False), self.pdf, self.output)
        self.assertIsNone(result.manifest_error)
        self.assertTrue(self.reusable())
        self.assertEqual(extra.read_text(), "keep")

    def test_failed_invalidation_does_not_start_conversion_or_change_outputs(self) -> None:
        self.record()
        runtime = self.runtime()
        original = self.output.markdown.read_bytes()
        with patch("pdf_receipt.manifest.atomic_write", side_effect=OSError("locked")):
            with self.assertRaises(OSError):
                converter.convert_pdf(runtime, self.pdf, self.output)
        runtime.converter.convert.assert_not_called()
        self.assertEqual(self.output.markdown.read_bytes(), original)
        self.assertTrue(self.reusable())

    def test_source_changed_during_conversion_never_gets_completion(self) -> None:
        runtime = self.runtime(report=False)
        document = runtime.converter.convert.return_value.document
        def change_source(path):
            self.pdf.write_bytes(b"changed source")
            return SimpleNamespace(document=document)
        runtime.converter.convert.side_effect = change_source
        result = converter.convert_pdf(runtime, self.pdf, self.output)
        self.assertIn("Source changed", result.manifest_error)
        self.assertFalse(self.reusable())

    def test_failed_json_export_keeps_record_incomplete(self) -> None:
        self.record()
        runtime = self.runtime()
        runtime.converter.convert.return_value.document.save_as_json.side_effect = OSError("disk full")
        with self.assertRaises(OSError):
            converter.convert_pdf(runtime, self.pdf, self.output)
        self.assertFalse(self.reusable())

    def test_completion_write_failure_warns_and_preserves_incomplete_record(self) -> None:
        real_write = manifest.atomic_write
        def fail_completion(output, payload):
            if payload["complete"]:
                raise OSError("disk full")
            real_write(output, payload)
        with patch("pdf_receipt.manifest.atomic_write", side_effect=fail_completion):
            result = converter.convert_pdf(self.runtime(report=False), self.pdf, self.output)
        self.assertEqual(result.manifest_error, "disk full")
        self.assertFalse(self.reusable())


class SkipExistingCliTests(unittest.TestCase):
    def test_all_skipped_avoids_loading_models_and_opens_results(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            pdfs = [touch_pdf(Path(temp) / name) for name in ("one.pdf", "two.pdf")]
            with patch("pdf_receipt.cli.manifest.reusable", return_value=True):
                run = run_main(["--skip-existing", *map(str, pdfs)])
            self.assertEqual(run.exit_code, 0)
            run.runtime.assert_not_called()
            run.convert.assert_not_called()
            self.assertIn("0 converted, 2 skipped, 0 failed", run.stdout.getvalue())
            run.open_folder.assert_called_once()

    def test_mixed_batch_reports_converted_skipped_and_failed(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            pdfs = [touch_pdf(Path(temp) / name) for name in ("one.pdf", "two.pdf", "bad.pdf")]
            with patch("pdf_receipt.cli.manifest.reusable", side_effect=[True, False, False]):
                run = run_main(["--skip-existing", *map(str, pdfs)],
                               convert_stub=fake_convert(frozenset({"bad.pdf"})))
            self.assertEqual(run.exit_code, 1)
            self.assertEqual(run.convert.call_count, 2)
            run.runtime.assert_called_once()
            self.assertIn("1 converted, 1 skipped, 1 failed", run.stdout.getvalue())

    def test_default_always_converts_without_consulting_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            pdf = touch_pdf(Path(temp) / "one.pdf")
            with patch("pdf_receipt.cli.manifest.reusable") as reuse:
                run = run_main([str(pdf)])
            reuse.assert_not_called()
            run.convert.assert_called_once()


if __name__ == "__main__":
    unittest.main()
