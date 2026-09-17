"""Offline endpoint comparison, independent of the Markdown producer."""

from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import dataclass
from html import escape
from pathlib import Path
import re
import os
import sys

from . import alignment as al
from . import quality_report as qr
from . import structural_integrity as si
from .quality_metrics import StageMetrics, summarize_alignment
from .markdown_evidence import parse_markdown
from .comparison_groups import DifferenceGroup, group_differences


@dataclass(frozen=True)
class ComparisonResult:
    pdf: qr.PdfText
    markdown: str
    markdown_path: Path
    alignment: al.AlignmentResult
    metrics: StageMetrics
    groups: tuple[DifferenceGroup, ...]
    images: tuple[tuple[int, str, str], ...]
    page_counts: tuple[tuple[tuple[str, int], ...], ...]
    issue_limit: int


def build_comparison(pdf: qr.PdfText, markdown: str, markdown_path: Path,
                     *, issue_limit: int = 50) -> ComparisonResult:
    if issue_limit < 1:
        raise ValueError("issue_limit must be positive")
    result = compare_text(pdf, markdown)
    pages = [Counter() for _ in pdf.pages]
    for op in result.operations:
        if op.source_token is not None:
            pages[op.source_token.page_no - 1][op.type.value] += 1
    return ComparisonResult(pdf, markdown, markdown_path, result,
                            summarize_alignment(result, issue_limit=0),
                            group_differences(result), tuple(image_checks(markdown, markdown_path)),
                            tuple(tuple(sorted(page.items())) for page in pages), issue_limit)


def compare_text(pdf: qr.PdfText, markdown: str) -> al.AlignmentResult:
    """Keep global occurrence accounting and original page/source offsets."""
    return al.align_direct(
        qr.tokenize_pdf_pages(pdf),
        parse_markdown(markdown, case_profile=pdf.case_profile).tokens,
        case_profile=pdf.case_profile,
    )


def image_checks(markdown: str, markdown_path: Path) -> list[tuple[int, str, str]]:
    """Inspect Markdown/reference/HTML images without accessing remote targets."""
    checks = []
    for image in parse_markdown(markdown).images:
        status = "not checked (remote or unsupported target)"
        try:
            if si._target_kind(image.target) == "local":
                path, error = si._resolve_local_target(
                    image.target, markdown_path=markdown_path,
                    output_root=markdown_path.parent,
                )
                status = error or si._inspect_local_link(path)
                if status is None:
                    if si._long_path(path).stat().st_size == 0:
                        status = "empty image"
                    else:
                        si._decode_image(path)
                        status = "decodable image (content not compared with PDF)"
        except si._InvalidImageError:
            status = "invalid image"
        except (OSError, ValueError) as exc:
            status = f"could not inspect image: {exc}"
        checks.append((image.line, image.target, status))
    return checks


def _code(text: str) -> str:
    return "<code>" + escape(text).replace("|", "&#124;").replace("\n", "&#10;") + "</code>"


def _line_number(markdown: str, offset: int) -> int:
    return len(re.findall(r"\r\n|\r|\n", markdown[:offset])) + 1


def _evidence(token: al.TokenEvidence | None, markdown: str, *, source: bool) -> str:
    if token is None:
        return "No corresponding occurrence (page unknown)."
    span = token.source_span
    line = _line_number(markdown, span.start)
    location = f"PDF page {token.page_no}" if source else f"Markdown line {line}"
    return (f"{location}, raw span [{span.start}, {span.end}): "
            f"{_code(token.raw_text)}; normalized {_code(token.normalized_text)}")


def _excerpt(tokens: tuple[al.TokenEvidence, ...]) -> str:
    """A bounded token excerpt; exact raw spellings remain in occurrence details."""
    text = " ".join(token.raw_text for token in tokens)
    return _code(text[:800]) + (" (excerpt truncated at 800 characters)" if len(text) > 800 else "")


def _group_report(comparison: ComparisonResult) -> list[str]:
    result, markdown, issue_limit = comparison.alignment, comparison.markdown, comparison.issue_limit
    groups = comparison.groups
    selected = groups[:issue_limit]
    total = sum(len(group.operations) for group in groups)
    shown = sum(len(group.operations) for group in selected)
    lines = ["## Grouped differences", "",
             f"Showing {len(selected)} of {len(groups)} groups; omitted {len(groups) - len(selected)} groups. "
             f"Details cover {shown} of {total} difference operations; omitted {total - shown} operations.", "",
             "Size-based priority: descending operation count, ties in original alignment order. "
             "This is not semantic importance or model confidence. Groups contain at most 40 "
             "same-kind adjacent operations and split at page boundaries or endpoint discontinuities. "
             "Context uses up to three neighboring tokens on each side; excerpts are capped at 800 characters. "
             "Increase --issue-limit in a new report to see omitted groups. Raw occurrence details "
             "for every displayed group remain complete. Spans are zero-based, half-open character offsets.", ""]
    labels = {al.OperationType.DELETION: "Missing text (text-layer evidence)",
              al.OperationType.INSERTION: "Added text",
              al.OperationType.SUBSTITUTION: "Substituted text",
              al.OperationType.ORDER_RISK: "Suspected movement (order risk, not verified loss)"}
    for number, group in enumerate(selected, 1):
        operations = group.operations
        lines += [f"### {number}. {labels[operations[0].type]} — {len(operations)} operations", ""]
        for source, label, stream in ((True, "PDF", result.source_tokens),
                                      (False, "Markdown", result.target_tokens)):
            tokens = tuple(op.source_token if source else op.target_token for op in operations)
            present = tuple(token for token in tokens if token is not None)
            if present:
                first, last = present[0], present[-1]
                location = (f"PDF page {first.page_no}" if source else
                            f"Markdown lines {_line_number(markdown, first.source_span.start)}"
                            f"-{_line_number(markdown, last.source_span.end)}")
                lines.append(f"- {location}, raw span [{first.source_span.start}, {last.source_span.end}): " + _excerpt(present))
                context = stream[max(0, first.index - 3):last.index + 4]
                if source:
                    context = tuple(t for t in context if t.page_no == first.page_no)
                lines.append(f"- {label} context: " + _excerpt(context))
            else:
                lines.append(f"- {label}: No corresponding occurrence (page unknown).")
                bounds = operations[0].source_context if source else operations[0].target_context
                context = stream[bounds.start:bounds.end]
                lines.append(f"- {label} context (alignment gap, not a corresponding occurrence): " + _excerpt(context))
        lines += ["", "<details>", "<summary>Occurrence details</summary>", ""]
        for offset, op in enumerate(operations, group.first_operation):
            lines += [f"- Operation {offset}: {op.type.value}; source occurrence {op.source_index}; "
                      f"target occurrence {op.target_index}",
                      "  - " + _evidence(op.source_token, markdown, source=True),
                      "  - " + _evidence(op.target_token, markdown, source=False)]
        lines += ["", "</details>", ""]
    return lines


def render_report(pdf: qr.PdfText, markdown: str, markdown_path: Path,
                  *, issue_limit: int = 50) -> str:
    return render_markdown(build_comparison(pdf, markdown, markdown_path, issue_limit=issue_limit))


def render_markdown(comparison: ComparisonResult) -> str:
    pdf, markdown_path = comparison.pdf, comparison.markdown_path
    result, metrics = comparison.alignment, comparison.metrics
    pages = {page: Counter(dict(counts)) for page, counts in enumerate(comparison.page_counts, 1)}
    unverified = [str(page) for page, count in pages.items() if not sum(count.values())]

    def rate(numerator: int, denominator: int) -> str:
        return f"{numerator}/{denominator} ({numerator / denominator:.2%})" if denominator else "n/a (empty denominator)"

    lines = [
        "# PDF-to-Markdown comparison", "",
        f"PDF: {_code(pdf.name)}; Markdown: {_code(markdown_path.name)}", "",
        "This compares existing endpoints, regardless of the conversion tool. "
        "It does not locate the processing stage responsible for differences.", "",
        "**Evidence limits:** the PDF text layer is not ground truth. Reading order "
        "may be wrong. OCR, visual layout, table structure, equation meaning and "
        "image fidelity are not verified. Rates describe available text only, "
        "not full-document accuracy.", "",
        "Pages without comparable text (unverified): " + (", ".join(unverified) or "none"), "",
        f"Case profile: {_code(result.case_profile)}. Ordered lookahead: {result.lookahead_tokens} tokens. "
        "Matching is globally one-to-one; distant moves may appear as loss/addition. "
        "No figure, furniture or footnote explanations are assumed.", "",
        "## Text accounting", "",
        f"- Source tokens: {metrics.source_token_count}",
        f"- Markdown tokens: {metrics.target_token_count}",
        f"- Accepted matches: {metrics.matched_source_count} "
        f"(normalized: {metrics.normalized_match_count}; contextual hyphen: {metrics.contextual_hyphen_match_count})",
        f"- Missing occurrences: {metrics.unexplained_deletion_count}",
        f"- Added occurrences: {metrics.unexpected_insertion_count} (includes surplus repetitions)",
        f"- Substitutions: {metrics.substitution_count}",
        f"- Order risks: {metrics.order_risk_count}",
        f"- Accepted transfer / source: {rate(metrics.matched_source_count, metrics.source_token_count)}",
        f"- Missing + substitutions / source: {rate(metrics.unexplained_loss_numerator, metrics.source_token_count)}",
        f"- Added + substitutions / Markdown: {rate(metrics.unexpected_addition_numerator, metrics.target_token_count)}", "",
        "Source = matches + missing + substitutions + order risks. "
        "Markdown = matches + added + substitutions + order risks.", "",
        "## Source page accounting", "",
        "| Page | Source tokens | Matches | Missing | Substitutions | Order risks |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for page, count in pages.items():
        lines.append(f"| {page} | {sum(count.values())} | {count['match']} | "
                     f"{count['deletion']} | {count['substitution']} | {count['order_risk']} |")
    lines += ["", "Target-only additions are not assigned to PDF pages.", ""]
    lines += _group_report(comparison)
    lines += ["## Image references and Markdown limits", "",
              "Inline/reference Markdown images and HTML img src targets are checked, relative to the Markdown directory. "
              "Remote targets are never fetched; paths outside that directory are not opened. "
              "A decodable file does not establish preservation of a PDF image.", "",
              "Text parsing uses CommonMark with pipe tables, reference links, nested formatting "
              "and decoded entities, preserving original raw spans. Code content stays literal; "
              "image alt text, destinations, definitions and HTML comments are excluded. HTML "
              "tables contribute text only; math remains lexical text. CSS, JavaScript, extensions "
              "such as footnotes, and image srcset are not interpreted. See docs/COMPARISON.md.", ""]
    checks = comparison.images
    lines.extend(f"- Line {line}: {_code(target)} — {_code(status)}" for line, target, status in checks)
    if not checks:
        lines.append("No supported image references found; this does not prove there are no images.")
    return "\n".join(lines) + "\n"


def _positive(value: str) -> int:
    number = int(value)
    if number < 1:
        raise argparse.ArgumentTypeError("must be a positive integer")
    return number


def validate_inputs(pdf_path: Path, markdown_path: Path) -> None:
    if pdf_path.suffix.lower() != ".pdf" or not si._long_path(pdf_path).is_file():
        raise ValueError("PDF input must be an existing .pdf file")
    if markdown_path.suffix.lower() not in {".md", ".markdown"} or not si._long_path(markdown_path).is_file():
        raise ValueError("Markdown input must be an existing .md or .markdown file")


def read_comparison(pdf_path: Path, markdown_path: Path, *, case_profile: qr.CaseProfile = "unicode",
                    issue_limit: int = 50) -> ComparisonResult:
    validate_inputs(pdf_path, markdown_path)
    with si._long_path(markdown_path).open(encoding="utf-8-sig", newline="") as handle:
        markdown = handle.read()
    pdf = qr.read_pdf_text(si._long_path(pdf_path), case_profile=case_profile)
    return build_comparison(pdf, markdown, markdown_path, issue_limit=issue_limit)


@dataclass(frozen=True)
class ReportWrite:
    kind: str
    path: Path
    error: str | None


def write_reports(outputs: list[tuple[str, Path]], reports: list[str]) -> tuple[ReportWrite, ...]:
    """Attempt each exclusive write independently, preserving partial successes."""
    if len(outputs) != len(reports):
        raise ValueError("Every report target must have rendered content")
    results = []
    for (kind, path), report in zip(outputs, reports):
        try:
            with si._long_path(path).open("x", encoding="utf-8", newline="\n") as handle:
                handle.write(report)
            label = "Comparison report" if kind == "Markdown" else f"Comparison {kind} report"
            print(f"{label}: {path}")
            results.append(ReportWrite(kind, path, None))
        except Exception as exc:
            results.append(ReportWrite(kind, path, str(exc)))
            print(f"Comparison {kind} report failed: {path}: {exc}. "
                  "Other completed outputs are retained; a partial file may remain at this path.", file=sys.stderr)
    return tuple(results)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="pdf-receipt compare", description=(
        "Compare an existing PDF and UTF-8 Markdown from any producer, offline and without models. "
        "CommonMark and pipe tables are supported; HTML tables provide text, math stays lexical. "
        "Inline/reference images and HTML img src are checked locally. "
        "Differences return exit 0; input/write errors return exit 1. Inputs are never modified."))
    parser.add_argument("pdf", type=Path)
    parser.add_argument("markdown", type=Path)
    parser.add_argument("--report", type=Path, help="New report path; default: <Markdown stem>_comparison.md. Never overwrite.")
    parser.add_argument("--json-report", type=Path, help="Also write versioned JSON with complete occurrence evidence to this new path. Markdown is still written; any write failure returns exit 1 and successful outputs remain.")
    parser.add_argument("--case-profile", choices=("unicode", "turkic"), default="unicode")
    parser.add_argument("--issue-limit", type=_positive, default=50, help="Maximum difference groups (default: 50), largest first; up to 40 operations per group. Counts stay complete; shown groups include all occurrence details.")
    args = parser.parse_args(argv)
    try:
        pdf_path = args.pdf.expanduser().resolve()
        markdown_path = args.markdown.expanduser().resolve()
        validate_inputs(pdf_path, markdown_path)
        output = (args.report.expanduser() if args.report else
                  markdown_path.with_name(markdown_path.stem + "_comparison.md")).absolute()
        outputs = [("Markdown", output)]
        if args.json_report is not None:
            outputs.append(("JSON", args.json_report.expanduser().absolute()))
        resolved = {pdf_path, markdown_path}
        for _, path in outputs:
            if path.resolve() in resolved or os.path.lexists(si._long_path(path)):
                raise FileExistsError(f"Report target already exists or collides with another path: {path}")
            if not si._long_path(path.parent).is_dir():
                raise FileNotFoundError(f"Report parent directory does not exist: {path.parent}")
            resolved.add(path.resolve())
        comparison = read_comparison(pdf_path, markdown_path, case_profile=args.case_profile, issue_limit=args.issue_limit)
        reports = [render_markdown(comparison)]
        if args.json_report is not None:
            from .comparison_json import render_json
            reports.append(render_json(comparison))
        written = write_reports(outputs, reports)
        return 1 if any(item.error is not None for item in written) else 0
    except Exception as exc:
        print(f"Comparison failed: {exc}", file=sys.stderr)
        return 1
