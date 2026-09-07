from __future__ import annotations

import os
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from dataclasses import dataclass
from io import StringIO
from pathlib import Path
from unittest.mock import Mock, patch

from pdftomd import cli, converter


class ArgumentTests(unittest.TestCase):
    def test_defaults_to_quality_report_and_open_output(self) -> None:
        args = cli.parse_args(["document.pdf"])

        self.assertEqual(args.profile, "quality")
        self.assertFalse(args.formula)
        self.assertTrue(args.report)
        self.assertTrue(args.open_output)
        self.assertFalse(args.yes)
        self.assertEqual(args.pdfs, [Path("document.pdf")])

    def test_pdf_paths_are_optional(self) -> None:
        args = cli.parse_args([])

        self.assertEqual(args.pdfs, [])

    def test_yes_flag_is_available(self) -> None:
        args = cli.parse_args(["--yes"])

        self.assertTrue(args.yes)

    def test_switches_can_be_turned_off(self) -> None:
        args = cli.parse_args(["--fast", "--formula", "--no-report", "--no-open", "a.pdf"])

        self.assertEqual(args.profile, "fast")
        self.assertTrue(args.formula)
        self.assertFalse(args.report)
        self.assertFalse(args.open_output)

    def test_fast_and_quality_are_mutually_exclusive(self) -> None:
        with redirect_stderr(StringIO()), self.assertRaises(SystemExit):
            cli.parse_args(["--fast", "--quality", "document.pdf"])


def fake_convert(
    failing_names: frozenset[str] = frozenset(),
    summary: str | None = None,
    report_error: str | None = None,
):
    """Build a convert_pdf stub that creates folders and can fail by file name."""

    def _convert(
        _runtime: converter.DoclingRuntime,
        pdf_path: Path,
        output: converter.OutputPaths,
    ) -> converter.ConversionResult:
        if pdf_path.name in failing_names:
            raise RuntimeError("sample failure")
        output.directory.mkdir(parents=True, exist_ok=True)
        return converter.ConversionResult(output, summary, report_error)

    return _convert


@dataclass
class Run:
    """What one patched `main()` call did."""

    exit_code: int
    runtime: Mock
    convert: Mock
    open_folder: Mock
    prompt: Mock
    stdout: StringIO
    stderr: StringIO


def touch_pdf(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.touch()
    return path


def run_main(
    argv,
    convert_stub=None,
    runtime=None,
    open_side_effect=None,
    *,
    stdin_isatty=False,
    input_answer="",
) -> Run:
    """Run main with Docling and Explorer replaced, capturing the output."""
    runtime = runtime or converter.DoclingRuntime(Mock(), "referenced", "quality", False)
    stdout, stderr = StringIO(), StringIO()
    stdin = Mock()
    stdin.isatty.return_value = stdin_isatty
    with (
        patch("pdftomd.cli.configure_console"),
        patch("pdftomd.cli.sys.stdin", stdin),
        patch("builtins.input", return_value=input_answer) as input_mock,
        patch("pdftomd.cli.create_docling_runtime", return_value=runtime) as runtime_mock,
        patch(
            "pdftomd.cli.convert_pdf", side_effect=convert_stub or fake_convert()
        ) as convert_mock,
        patch("pdftomd.cli.open_output_folder", side_effect=open_side_effect) as open_mock,
        redirect_stdout(stdout),
        redirect_stderr(stderr),
    ):
        exit_code = cli.main(argv)
    return Run(
        exit_code,
        runtime_mock,
        convert_mock,
        open_mock,
        input_mock,
        stdout,
        stderr,
    )


class FolderDiscoveryTests(unittest.TestCase):
    def test_finds_pdf_extensions_case_insensitively_and_sorts_by_name(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir).resolve()
            upper = touch_pdf(root / "Zulu.PDF")
            lower = touch_pdf(root / "alpha.pdf")
            touch_pdf(root / "notes.txt")

            found = cli._find_pdfs(root)

            self.assertEqual(found, [lower, upper])

    def test_ignores_pdfs_in_subfolders(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir).resolve()
            top_level = touch_pdf(root / "top.pdf")
            touch_pdf(root / "nested" / "hidden.pdf")

            found = cli._find_pdfs(root)

            self.assertEqual(found, [top_level])

    def test_launch_directory_environment_variable_takes_precedence(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir).resolve()
            with (
                patch.dict(os.environ, {"PDFTOMD_LAUNCH_DIR": str(root)}),
                patch("pdftomd.cli.Path.cwd", return_value=root.parent),
            ):
                folder = cli._automatic_input_folder()

            self.assertEqual(folder, root)

    def test_current_directory_is_the_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir).resolve()
            with (
                patch.dict(os.environ, {}, clear=True),
                patch("pdftomd.cli.Path.cwd", return_value=root),
            ):
                folder = cli._automatic_input_folder()

            self.assertEqual(folder, root)


class AutomaticInputFlowTests(unittest.TestCase):
    def test_empty_folder_returns_one_before_building_the_converter(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir).resolve()
            with patch.dict(os.environ, {"PDFTOMD_LAUNCH_DIR": str(root)}):
                run = run_main([])

            self.assertEqual(run.exit_code, 1)
            self.assertIn("No PDF files found", run.stderr.getvalue())
            self.assertIn(str(root), run.stderr.getvalue())
            run.runtime.assert_not_called()
            run.convert.assert_not_called()

    def test_one_discovered_pdf_uses_singular_message_without_prompting(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir).resolve()
            pdf = touch_pdf(root / "one.pdf")
            with patch.dict(os.environ, {"PDFTOMD_LAUNCH_DIR": str(root)}):
                run = run_main([], stdin_isatty=True)

            self.assertEqual(run.exit_code, 0)
            self.assertIn(f"Found 1 PDF file in: {root}", run.stdout.getvalue())
            self.assertNotIn("1 PDF files", run.stdout.getvalue())
            self.assertEqual(run.convert.call_args.args[1], pdf)
            run.prompt.assert_not_called()
            run.open_folder.assert_called_once_with(root / "one_markdown")

    def test_accepting_confirmation_converts_all_discovered_pdfs(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir).resolve()
            first = touch_pdf(root / "alpha.pdf")
            second = touch_pdf(root / "beta.PDF")
            with patch.dict(os.environ, {"PDFTOMD_LAUNCH_DIR": str(root)}):
                run = run_main([], stdin_isatty=True, input_answer="yes")

            self.assertEqual(run.exit_code, 0)
            self.assertEqual(
                [call.args[1] for call in run.convert.call_args_list],
                [first, second],
            )
            run.prompt.assert_called_once()
            self.assertIn(f"Found 2 PDF files in: {root}", run.stdout.getvalue())
            self.assertIn("alpha.pdf", run.stdout.getvalue())
            self.assertIn("beta.PDF", run.stdout.getvalue())

    def test_rejecting_confirmation_cancels_without_loading_models(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir).resolve()
            touch_pdf(root / "one.pdf")
            touch_pdf(root / "two.pdf")
            with patch.dict(os.environ, {"PDFTOMD_LAUNCH_DIR": str(root)}):
                run = run_main([], stdin_isatty=True, input_answer="no")

            self.assertEqual(run.exit_code, 0)
            self.assertIn("Cancelled", run.stdout.getvalue())
            run.runtime.assert_not_called()
            run.convert.assert_not_called()

    def test_yes_skips_the_confirmation_prompt(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir).resolve()
            touch_pdf(root / "one.pdf")
            touch_pdf(root / "two.pdf")
            with patch.dict(os.environ, {"PDFTOMD_LAUNCH_DIR": str(root)}):
                run = run_main(["--yes"], stdin_isatty=True, input_answer="no")

            self.assertEqual(run.exit_code, 0)
            self.assertEqual(run.convert.call_count, 2)
            run.prompt.assert_not_called()

    def test_noninteractive_stdin_proceeds_without_confirmation(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir).resolve()
            touch_pdf(root / "one.pdf")
            touch_pdf(root / "two.pdf")
            with patch.dict(os.environ, {"PDFTOMD_LAUNCH_DIR": str(root)}):
                run = run_main([])

            self.assertEqual(run.exit_code, 0)
            self.assertEqual(run.convert.call_count, 2)
            run.prompt.assert_not_called()

    def test_explicit_paths_win_over_folder_discovery(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir).resolve()
            launch_folder = root / "launch"
            explicit = touch_pdf(root / "chosen" / "explicit.pdf")
            touch_pdf(launch_folder / "automatic.pdf")
            with patch.dict(
                os.environ, {"PDFTOMD_LAUNCH_DIR": str(launch_folder)}
            ):
                run = run_main([str(explicit)], stdin_isatty=True)

            self.assertEqual(run.exit_code, 0)
            run.convert.assert_called_once()
            self.assertEqual(run.convert.call_args.args[1], explicit)
            run.prompt.assert_not_called()
            self.assertNotIn("automatic.pdf", run.stdout.getvalue())


class MainFlowTests(unittest.TestCase):
    def test_single_pdf_opens_its_own_output_folder(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir).resolve()
            pdf = touch_pdf(root / "one.pdf")

            run = run_main([str(pdf)])

            self.assertEqual(run.exit_code, 0)
            run.open_folder.assert_called_once_with(root / "one_markdown")

    def test_batch_continues_after_failure_and_opens_common_root(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir).resolve()
            pdfs = [
                touch_pdf(root / "one.pdf"),
                touch_pdf(root / "bad.pdf"),
                touch_pdf(root / "three.pdf"),
            ]
            runtime = converter.DoclingRuntime(Mock(), "referenced", "quality", False)

            run = run_main(
                [str(path) for path in pdfs],
                convert_stub=fake_convert(frozenset({"bad.pdf"})),
                runtime=runtime,
            )

            self.assertEqual(run.exit_code, 1)
            self.assertEqual(run.convert.call_count, 3)
            run.open_folder.assert_called_once_with(root / "pdfmd_output")
            # A single DocumentConverter instance is reused for every document.
            run.runtime.assert_called_once_with("quality", False, True)
            self.assertEqual(
                {call.args[0] for call in run.convert.call_args_list}, {runtime}
            )

    def test_only_failures_return_one_and_skip_opening(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            pdf = touch_pdf(Path(temp_dir).resolve() / "one.pdf")

            run = run_main([str(pdf)], convert_stub=fake_convert(frozenset({"one.pdf"})))

            self.assertEqual(run.exit_code, 1)
            run.open_folder.assert_not_called()

    def test_missing_file_fails_before_the_converter_is_built(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            missing = Path(temp_dir).resolve() / "missing.pdf"

            run = run_main([str(missing)])

            self.assertEqual(run.exit_code, 1)
            run.runtime.assert_not_called()
            run.convert.assert_not_called()
            run.open_folder.assert_not_called()

    def test_batch_skips_invalid_input_and_converts_the_rest(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir).resolve()
            good = touch_pdf(root / "one.pdf")
            not_a_pdf = touch_pdf(root / "notes.txt")

            run = run_main([str(good), str(not_a_pdf)])

            self.assertEqual(run.exit_code, 1)
            self.assertEqual(run.convert.call_count, 1)
            self.assertEqual(run.convert.call_args.args[1], good)

    def test_no_open_skips_explorer(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            pdf = touch_pdf(Path(temp_dir).resolve() / "one.pdf")

            run = run_main(["--no-open", str(pdf)])

            self.assertEqual(run.exit_code, 0)
            run.open_folder.assert_not_called()

    def test_flags_reach_the_runtime(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            pdf = touch_pdf(Path(temp_dir).resolve() / "one.pdf")

            run = run_main(["--fast", "--formula", "--no-report", str(pdf)])

            self.assertEqual(run.exit_code, 0)
            run.runtime.assert_called_once_with("fast", True, False)

    def test_open_failure_is_only_a_warning(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            pdf = touch_pdf(Path(temp_dir).resolve() / "one.pdf")

            run = run_main([str(pdf)], open_side_effect=OSError("no Explorer here"))

            self.assertEqual(run.exit_code, 0)
            self.assertIn("Warning", run.stderr.getvalue())


class ReportOutputTests(unittest.TestCase):
    def test_report_summary_is_printed(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            pdf = touch_pdf(Path(temp_dir).resolve() / "one.pdf")

            run = run_main(
                [str(pdf)],
                convert_stub=fake_convert(summary="Quality: 98.7% word coverage"),
            )

            self.assertEqual(run.exit_code, 0)
            self.assertIn("98.7% word coverage", run.stdout.getvalue())

    def test_report_error_is_a_warning_not_a_failure(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            pdf = touch_pdf(Path(temp_dir).resolve() / "one.pdf")

            run = run_main(
                [str(pdf)], convert_stub=fake_convert(report_error="cannot read the PDF")
            )

            self.assertEqual(run.exit_code, 0)
            self.assertIn("could not produce the quality report", run.stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
