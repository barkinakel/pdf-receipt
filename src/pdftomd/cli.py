"""Command line interface: arguments, progress messages, exit codes."""

from __future__ import annotations

import argparse
import os
import sys
import time
from dataclasses import dataclass
from pathlib import Path

from .converter import (
    DoclingRuntime,
    OutputPaths,
    convert_pdf,
    create_docling_runtime,
    plan_output_paths,
    validate_pdf,
)


def configure_console() -> None:
    """Keep accented status messages readable in Windows terminals."""
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(encoding="utf-8", errors="replace")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="pdftomd",
        description="Converts one or more PDF files to Markdown and JSON.",
    )
    parser.add_argument(
        "pdfs",
        metavar="PDF",
        nargs="*",
        type=Path,
        help="PDF files to convert; defaults to PDFs in the launch folder",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        help=(
            "Output folder. For a single PDF this is the target folder itself; "
            "for several PDFs it is the common root the document folders go into."
        ),
    )

    profiles = parser.add_mutually_exclusive_group()
    profiles.add_argument(
        "--fast",
        dest="profile",
        action="store_const",
        const="fast",
        help="Skips OCR and the table model so digital PDFs convert faster.",
    )
    profiles.add_argument(
        "--quality",
        dest="profile",
        action="store_const",
        const="quality",
        help="Enables OCR and the table model (default).",
    )
    parser.set_defaults(profile="quality")

    parser.add_argument(
        "--formula",
        action="store_true",
        help=(
            "Enables the extra model that turns formulas into LaTeX. The first "
            "run may download the model and slow the conversion down."
        ),
    )
    parser.add_argument(
        "--no-report",
        dest="report",
        action="store_false",
        help=(
            "Skips the quality report (<name>_report.md). The report compares "
            "the PDF text layer with the Markdown and lists what went missing."
        ),
    )
    parser.set_defaults(report=True)
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Skips confirmation when several PDFs are found automatically.",
    )
    parser.add_argument(
        "--no-open",
        dest="open_output",
        action="store_false",
        help="Does not open the output folder when the conversion finishes.",
    )
    parser.set_defaults(open_output=True)
    return parser.parse_args(argv)


def _automatic_input_folder() -> Path:
    launch_dir = os.environ.get("PDFTOMD_LAUNCH_DIR")
    folder = Path(launch_dir).expanduser() if launch_dir else Path.cwd()
    return folder.resolve()


def _find_pdfs(folder: Path) -> list[Path]:
    """Find direct PDF children without relying on platform-specific glob casing."""
    if not folder.is_dir():
        return []
    pdfs = (
        path.resolve()
        for path in folder.iterdir()
        if path.is_file() and path.suffix.casefold() == ".pdf"
    )
    return sorted(pdfs, key=lambda path: (path.name.casefold(), path.name))


def _print_discovered_pdfs(folder: Path, pdfs: list[Path]) -> None:
    noun = "PDF file" if len(pdfs) == 1 else "PDF files"
    print(f"Found {len(pdfs)} {noun} in: {folder}")
    for pdf_path in pdfs:
        print(f"  {pdf_path.name}")


def _confirm_discovered_batch(pdfs: list[Path], assume_yes: bool) -> bool:
    if len(pdfs) <= 1 or assume_yes or not sys.stdin.isatty():
        return True
    try:
        answer = input("Convert these files? Type yes to continue: ")
    except EOFError:
        return False
    return answer.strip().casefold() == "yes"


def open_output_folder(path: Path) -> None:
    """Open a folder in Windows Explorer."""
    startfile = getattr(os, "startfile", None)
    if startfile is None:
        raise OSError("Opening the output folder is only supported on Windows.")
    startfile(str(path))


@dataclass(frozen=True)
class Job:
    """One PDF waiting to be converted, numbered for the progress messages."""

    position: int
    pdf_path: Path
    output: OutputPaths


def _prepare_jobs(
    input_paths: list[Path], outputs: list[OutputPaths]
) -> tuple[list[Job], list[tuple[Path, str]]]:
    """Split the inputs into convertible jobs and inputs that are already broken."""
    jobs: list[Job] = []
    failures: list[tuple[Path, str]] = []

    for position, (input_path, output) in enumerate(zip(input_paths, outputs), start=1):
        try:
            jobs.append(Job(position, validate_pdf(input_path), output))
        except ValueError as exc:
            failures.append((input_path, str(exc)))
    return jobs, failures


def _convert_one(runtime: DoclingRuntime, job: Job, total: int) -> OutputPaths:
    """Convert a single document, printing progress as it goes."""
    prefix = f"[{job.position}/{total}] " if total > 1 else ""
    started = time.monotonic()
    print(
        f"{prefix}Converting: {job.pdf_path.name}"
        " (may take a few minutes depending on the page count)",
        flush=True,
    )

    result = convert_pdf(runtime, job.pdf_path, job.output)
    if result.report_summary:
        print(result.report_summary, flush=True)
    if result.report_error:
        print(
            f"Warning: could not produce the quality report: {result.report_error}",
            file=sys.stderr,
        )

    elapsed = int(time.monotonic() - started)
    print(f"{prefix}Done ({elapsed} s): {result.output.directory}", flush=True)
    if total == 1:
        print(f"Markdown: {result.output.markdown}")
    return result.output


def _print_batch_summary(
    successes: list[tuple[Path, OutputPaths]], failures: list[tuple[Path, str]]
) -> None:
    print(f"\nSummary: {len(successes)} succeeded, {len(failures)} failed.")
    for pdf_path, output in successes:
        print(f"  ✓ {pdf_path.name} → {output.directory}")
    for pdf_path, error in failures:
        print(f"  ✗ {pdf_path.name}: {error}", file=sys.stderr)


def _open_when_done(
    successes: list[tuple[Path, OutputPaths]], folder_to_open: Path, single: bool
) -> None:
    """Show the results in Explorer; failing to do so is not a conversion error."""
    target = successes[0][1].directory if single else folder_to_open
    try:
        open_output_folder(target)
    except OSError as exc:
        print(f"Warning: could not open the output folder: {exc}", file=sys.stderr)


def main(argv: list[str] | None = None) -> int:
    configure_console()
    args = parse_args(argv)

    if args.pdfs:
        input_paths = [path.expanduser().resolve() for path in args.pdfs]
    else:
        input_folder = _automatic_input_folder()
        input_paths = _find_pdfs(input_folder)
        if not input_paths:
            print(f"No PDF files found in: {input_folder}", file=sys.stderr)
            return 1
        _print_discovered_pdfs(input_folder, input_paths)
        if not _confirm_discovered_batch(input_paths, args.yes):
            print("Cancelled.")
            return 0

    outputs, folder_to_open = plan_output_paths(input_paths, args.output)
    total = len(input_paths)
    jobs, failures = _prepare_jobs(input_paths, outputs)
    successes: list[tuple[Path, OutputPaths]] = []

    if not jobs:
        if total > 1:
            _print_batch_summary(successes, failures)
        else:
            print(f"Error: {failures[0][1]}", file=sys.stderr)
        return 1

    print(
        f"Loading models ({args.profile} profile)."
        " This step can take a while on the first run...",
        flush=True,
    )
    try:
        runtime = create_docling_runtime(args.profile, args.formula, args.report)
    except Exception as exc:
        print(f"Could not start the converter: {exc}", file=sys.stderr)
        return 1

    try:
        for job in jobs:
            try:
                successes.append((job.pdf_path, _convert_one(runtime, job, total)))
            except Exception as exc:
                failures.append((job.pdf_path, str(exc)))
                if total == 1:
                    print(f"Conversion failed: {exc}", file=sys.stderr)
    except KeyboardInterrupt:
        print("\nCancelled.", file=sys.stderr)
        return 130

    if total > 1:
        _print_batch_summary(successes, failures)
    if args.open_output and successes:
        _open_when_done(successes, folder_to_open, single=total == 1)

    return 1 if failures else 0
