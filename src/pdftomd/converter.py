"""Turn PDF files into Markdown and Docling JSON.

This module does the conversion itself and prints nothing; `cli` decides
what the user gets to see.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from . import quality_report

Profile = Literal["fast", "quality"]


@dataclass(frozen=True)
class OutputPaths:
    """All output paths belonging to one source PDF."""

    directory: Path
    markdown: Path
    json: Path
    artifacts: Path
    report: Path


@dataclass(frozen=True)
class DoclingRuntime:
    """Objects and settings shared by every conversion in one command."""

    converter: Any
    referenced_image_mode: Any
    profile: Profile = "quality"
    report: bool = True


@dataclass(frozen=True)
class ConversionResult:
    """What one finished conversion produced."""

    output: OutputPaths
    report_summary: str | None = None
    report_error: str | None = None


def long_path(path: Path) -> Path:
    """Return the Windows extended-length form of an absolute path.

    Docling writes images under long file names, so in deep folders the total
    path passes 260 characters and saving used to fail silently. The `\\\\?\\`
    prefix lifts that limit. Off Windows the path is returned unchanged.
    """
    if os.name != "nt":
        return path

    text = str(path)
    if not path.is_absolute() or text.startswith("\\\\?\\"):
        return path
    if text.startswith("\\\\"):
        return Path("\\\\?\\UNC\\" + text.lstrip("\\"))
    return Path("\\\\?\\" + text)


def validate_pdf(path: Path) -> Path:
    pdf_path = path.expanduser().resolve()
    if not long_path(pdf_path).is_file():
        raise ValueError(f"File not found: {pdf_path}")
    if pdf_path.suffix.lower() != ".pdf":
        raise ValueError(f"Expected a PDF file: {pdf_path}")
    return pdf_path


def _output_paths(pdf_path: Path, directory: Path) -> OutputPaths:
    return OutputPaths(
        directory=directory,
        markdown=directory / f"{pdf_path.stem}.md",
        json=directory / f"{pdf_path.stem}.json",
        artifacts=directory / f"{pdf_path.stem}_artifacts",
        report=directory / f"{pdf_path.stem}_report.md",
    )


def plan_output_paths(
    pdf_paths: list[Path], requested_output: Path | None
) -> tuple[list[OutputPaths], Path]:
    """Return per-document paths and the folder to open when work finishes."""
    if not pdf_paths:
        raise ValueError("At least one PDF file is required.")

    resolved_pdfs = [path.expanduser().resolve() for path in pdf_paths]
    resolved_output = requested_output.expanduser().resolve() if requested_output else None

    if len(resolved_pdfs) == 1:
        pdf_path = resolved_pdfs[0]
        directory = resolved_output or pdf_path.parent / f"{pdf_path.stem}_markdown"
        return [_output_paths(pdf_path, directory)], directory

    batch_root = resolved_output or resolved_pdfs[0].parent / "pdfmd_output"
    stem_counts: dict[str, int] = {}
    outputs: list[OutputPaths] = []

    for pdf_path in resolved_pdfs:
        key = pdf_path.stem.casefold()
        stem_counts[key] = stem_counts.get(key, 0) + 1
        occurrence = stem_counts[key]
        base_name = f"{pdf_path.stem}_markdown"
        directory_name = base_name if occurrence == 1 else f"{base_name}_{occurrence}"
        outputs.append(_output_paths(pdf_path, batch_root / directory_name))

    return outputs, batch_root


def configure_pipeline_options(options: Any, profile: Profile, formula: bool) -> Any:
    """Apply the selected profile to a Docling PdfPipelineOptions instance."""
    is_quality = profile == "quality"
    options.do_ocr = is_quality
    options.do_table_structure = is_quality
    options.generate_picture_images = True
    options.do_formula_enrichment = formula
    return options


def create_docling_runtime(
    profile: Profile, formula: bool, report: bool = True
) -> DoclingRuntime:
    # Hugging Face's Xet download path can hang on some Windows installs, and
    # plain HTTP downloading is the more reliable choice for local use.
    os.environ.setdefault("HF_HUB_DISABLE_XET", "1")
    os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")
    os.environ.setdefault("HF_HUB_DOWNLOAD_TIMEOUT", "120")

    try:
        from docling.datamodel.base_models import InputFormat
        from docling.datamodel.pipeline_options import PdfPipelineOptions
        from docling.document_converter import DocumentConverter, PdfFormatOption
        from docling_core.types.doc import ImageRefMode
    except ImportError as exc:
        raise RuntimeError(
            "Docling is not installed. Run `install.bat` first, or use "
            "`python -m pip install -r requirements.txt`."
        ) from exc

    options = configure_pipeline_options(PdfPipelineOptions(), profile, formula)
    converter = DocumentConverter(
        format_options={
            InputFormat.PDF: PdfFormatOption(pipeline_options=options),
        }
    )
    return DoclingRuntime(
        converter=converter,
        referenced_image_mode=ImageRefMode.REFERENCED,
        profile=profile,
        report=report,
    )


def normalize_artifact_links(markdown_path: Path, artifacts_name: str) -> None:
    """Rewrite Windows backslashes inside artifact links to forward slashes.

    Docling writes image links as `folder\\file.png`, which some Markdown
    viewers cannot resolve. Only links pointing into the artifacts folder are
    touched, so the backslashes inside formulas survive.
    """
    pattern = re.compile(r"\]\(" + re.escape(artifacts_name) + r"([^)]*)\)")
    text = markdown_path.read_text(encoding="utf-8")
    fixed = pattern.sub(
        lambda match: "](" + artifacts_name + match.group(1).replace("\\", "/") + ")",
        text,
    )
    if fixed != text:
        markdown_path.write_text(fixed, encoding="utf-8")


def write_quality_report(
    pdf_path: Path,
    markdown_path: Path,
    document: Any,
    output: OutputPaths,
    profile: Profile,
) -> str:
    """Measure what the conversion lost, save the report, return the summary."""
    structure = quality_report.describe_document(document)
    pdf_text = quality_report.read_pdf_text(pdf_path, structure.figures)
    report = quality_report.analyze(
        pdf_text, markdown_path.read_text(encoding="utf-8"), structure, profile
    )
    long_path(output.report).write_text(
        quality_report.render_markdown(report), encoding="utf-8"
    )
    return quality_report.render_console(report)


def convert_pdf(
    runtime: DoclingRuntime,
    pdf_path: Path,
    output: OutputPaths,
) -> ConversionResult:
    """Convert one PDF and export Markdown/JSON from the same Docling result."""
    markdown_path = long_path(output.markdown)
    long_path(output.directory).mkdir(parents=True, exist_ok=True)
    relative_artifacts = Path(output.artifacts.name)

    result = runtime.converter.convert(long_path(pdf_path))
    result.document.save_as_markdown(
        markdown_path,
        artifacts_dir=relative_artifacts,
        image_mode=runtime.referenced_image_mode,
    )
    result.document.save_as_json(
        long_path(output.json),
        artifacts_dir=relative_artifacts,
        image_mode=runtime.referenced_image_mode,
    )
    normalize_artifact_links(markdown_path, output.artifacts.name)

    if not runtime.report:
        return ConversionResult(output)

    # A broken report never fails the conversion; it only raises a warning.
    try:
        summary = write_quality_report(
            pdf_path, markdown_path, result.document, output, runtime.profile
        )
    except Exception as exc:
        return ConversionResult(output, report_error=str(exc))
    return ConversionResult(output, report_summary=summary)
