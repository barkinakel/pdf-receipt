"""Compare a converted document against its source PDF and report what was lost.

Measures how much of the conversion survived: every word in the PDF text layer
is looked up in the Markdown, and the ones that are missing are grouped by the
reason they went missing.

Reading (`read_pdf_text`) is kept apart from measuring (`analyze`); the
measuring side never touches a file, so it can also run on text built by hand.
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# The alphabet covers the languages the source PDFs are written in, so Turkish
# and other accented letters belong here even though the tool speaks English.
WORD = re.compile(r"[0-9A-Za-zÀ-ÖØ-öø-ÿĞğİıŞşÇçÖöÜü]{3,}")
IMAGE_LINK = re.compile(r"!\[[^\]]*\]\([^)]*\)")
TRAILING_DIGITS = re.compile(r"\d+$")

FIGURE = "figure"
FURNITURE = "furniture"
FOOTNOTE = "footnote"
UNEXPLAINED = "unexplained"


@dataclass(frozen=True)
class Figure:
    """One extracted picture and where it sits on its PDF page."""

    page_no: int
    left: float
    bottom: float
    right: float
    top: float


@dataclass(frozen=True)
class DocumentStructure:
    """The parts of a converted document the report needs.

    Kept free of Docling types so the report logic can be driven by hand in
    the tests.
    """

    pages: int
    tables: int
    merged_cell_tables: int
    figures: tuple[Figure, ...]
    furniture_text: str


@dataclass(frozen=True)
class PdfText:
    """Everything read out of the source PDF, in one pass."""

    name: str
    pages: tuple[str, ...]
    figure_text: str = ""


@dataclass(frozen=True)
class PageIssue:
    page_no: int
    missing: int
    total: int
    samples: tuple[str, ...]


@dataclass(frozen=True)
class QualityReport:
    pdf_name: str
    profile: str
    pages: int
    tables: int
    merged_cell_tables: int
    pictures: int
    words_in_pdf: int
    words_matched: int
    in_figures: int
    in_furniture: int
    footnote_glued: int
    unexplained: int
    pages_without_text_layer: tuple[int, ...]
    worst_pages: tuple[PageIssue, ...]

    @property
    def coverage(self) -> float:
        """Share of PDF words that reached the Markdown, as a percentage."""
        if not self.words_in_pdf:
            return 0.0
        return 100.0 * self.words_matched / self.words_in_pdf

    @property
    def words_missing(self) -> int:
        return self.words_in_pdf - self.words_matched

    @property
    def explained(self) -> int:
        """Missing words whose reason we know, so they need no investigation."""
        return self.in_figures + self.in_furniture + self.footnote_glued


def _count(value: int, singular: str) -> str:
    """Format a count with its noun, so 1 page never reads as "1 pages"."""
    return f"1 {singular}" if value == 1 else f"{value:,} {singular}s"


def _words(text: str) -> Counter:
    return Counter(match.group().casefold() for match in WORD.finditer(text))


def read_pdf_text(pdf_path: Path, figures: tuple[Figure, ...] = ()) -> PdfText:
    """Read every page's text layer, plus the text drawn inside the figures.

    Text inside a figure stays in the PNG file, so it never shows up in the
    Markdown; reading it separately keeps it from being counted as lost.
    """
    try:
        import pypdfium2 as pdfium
    except ImportError as exc:  # pragma: no cover - docling installs this already
        raise RuntimeError(
            "pypdfium2 is not installed, so the quality report cannot be produced."
        ) from exc

    document = pdfium.PdfDocument(str(pdf_path))
    try:
        text_pages = [page.get_textpage() for page in document]
        pages = tuple(textpage.get_text_range() for textpage in text_pages)
        inside_figures = [
            text_pages[figure.page_no - 1].get_text_bounded(
                left=figure.left,
                bottom=figure.bottom,
                right=figure.right,
                top=figure.top,
            )
            for figure in figures
            if 0 < figure.page_no <= len(text_pages)
        ]
    finally:
        document.close()

    return PdfText(pdf_path.name, pages, "\n".join(inside_figures))


@dataclass
class _Tally:
    """Running totals while the pages are being compared."""

    words_in_pdf: int = 0
    words_matched: int = 0
    counts: Counter = field(default_factory=Counter)


def _classify(
    word: str,
    figure_words: Counter,
    furniture_words: Counter,
    markdown_words: Counter,
) -> str:
    """Say why a word from the PDF never made it into the Markdown."""
    if word in figure_words:
        return FIGURE
    if word in furniture_words:
        return FURNITURE
    if TRAILING_DIGITS.search(word) and TRAILING_DIGITS.sub("", word) in markdown_words:
        # In the PDF text layer a word like `likelihood55` carries the footnote
        # number glued to it; the conversion splits them apart.
        return FOOTNOTE
    return UNEXPLAINED


def analyze(
    pdf_text: PdfText,
    markdown_text: str,
    structure: DocumentStructure,
    profile: str,
) -> QualityReport:
    """Measure how much of the PDF text layer reached the Markdown."""
    markdown_words = _words(IMAGE_LINK.sub(" ", markdown_text))
    figure_words = _words(pdf_text.figure_text)
    furniture_words = _words(structure.furniture_text)

    tally = _Tally()
    scanned_pages: list[int] = []
    issues: list[PageIssue] = []

    for page_no, page_text in enumerate(pdf_text.pages, start=1):
        page_words = _words(page_text)
        if not page_words:
            scanned_pages.append(page_no)
            continue

        page_total = sum(page_words.values())
        missing = page_words - markdown_words
        tally.words_in_pdf += page_total
        tally.words_matched += page_total - sum(missing.values())

        unexplained = Counter()
        for word, count in missing.items():
            reason = _classify(word, figure_words, furniture_words, markdown_words)
            tally.counts[reason] += count
            if reason == UNEXPLAINED:
                unexplained[word] += count

        if unexplained:
            issues.append(
                PageIssue(
                    page_no=page_no,
                    missing=sum(unexplained.values()),
                    total=page_total,
                    samples=tuple(word for word, _ in unexplained.most_common(6)),
                )
            )

    issues.sort(key=lambda issue: (issue.missing / issue.total, issue.missing), reverse=True)

    return QualityReport(
        pdf_name=pdf_text.name,
        profile=profile,
        pages=structure.pages,
        tables=structure.tables,
        merged_cell_tables=structure.merged_cell_tables,
        pictures=len(structure.figures),
        words_in_pdf=tally.words_in_pdf,
        words_matched=tally.words_matched,
        in_figures=tally.counts[FIGURE],
        in_furniture=tally.counts[FURNITURE],
        footnote_glued=tally.counts[FOOTNOTE],
        unexplained=tally.counts[UNEXPLAINED],
        pages_without_text_layer=tuple(scanned_pages),
        worst_pages=tuple(issues[:5]),
    )


def render_console(report: QualityReport) -> str:
    """One line for the terminal, plus a warning line when it matters."""
    if not report.words_in_pdf:
        lines = [
            "Quality: the PDF has no text layer (scanned document),"
            " coverage cannot be measured"
        ]
    else:
        lines = [
            f"Quality: {report.coverage:.1f}% word coverage"
            f" | {_count(report.tables, 'table')},"
            f" {_count(report.pictures, 'image')}"
        ]

    scanned = len(report.pages_without_text_layer)
    if scanned and report.profile == "fast":
        lines.append(
            f"WARNING: {_count(scanned, 'page')} without a text layer, and --fast"
            " turned OCR off; those pages may have come out empty."
            " Try again with --quality."
        )
    elif scanned:
        lines.append(
            f"Note: {_count(scanned, 'page')} without a text layer, read with OCR;"
            " coverage cannot be measured for them."
        )
    return "\n".join(lines)


def _coverage_section(report: QualityReport) -> list[str]:
    if not report.words_in_pdf:
        return [
            "The PDF text layer is empty, so the document looks fully scanned. The",
            "text came from OCR and there is nothing to compare it against, which",
            "means coverage cannot be measured.",
            "",
        ]

    return [
        f"The PDF text layer holds **{report.words_in_pdf:,}** words;"
        f" **{report.coverage:.2f}%** of them reached the Markdown.",
        "",
        "| Where it ended up | Words |",
        "|---|---|",
        f"| Reached the Markdown | {report.words_matched:,} |",
        f"| Left inside figures (kept in the PNG files) | {report.in_figures:,} |",
        f"| Page header/footer (dropped on purpose) | {report.in_furniture:,} |",
        f"| Glued to a footnote number (not really lost) | {report.footnote_glued:,} |",
        f"| Unexplained | {report.unexplained:,} |",
        "",
        f"Missing in total: {report.words_missing:,} words,"
        f" {report.explained:,} of which have a known reason.",
        "",
    ]


def _scanned_pages_section(report: QualityReport) -> list[str]:
    if not report.pages_without_text_layer:
        return []

    shown = report.pages_without_text_layer[:20]
    listed = ", ".join(str(page_no) for page_no in shown)
    if len(report.pages_without_text_layer) > len(shown):
        listed += " ..."

    lines = [
        "## Pages without a text layer",
        "",
        f"{_count(len(report.pages_without_text_layer), 'page')}"
        f" {'looks' if len(report.pages_without_text_layer) == 1 else 'look'}"
        f" scanned: {listed}",
        "",
    ]
    if report.profile == "fast":
        lines += [
            "**Warning:** the `--fast` profile turns OCR off, so these pages most"
            " likely came out empty. Convert them again with `--quality`.",
            "",
        ]
    else:
        lines += [
            "These pages were read with OCR. There is no text layer to compare"
            " them against, so this report cannot verify them; check them by eye.",
            "",
        ]
    return lines


def _worst_pages_section(report: QualityReport) -> list[str]:
    if not report.worst_pages:
        return []

    lines = [
        "## Pages with the most unexplained loss",
        "",
        "| Page | Missing | Words on page | Examples |",
        "|---|---|---|---|",
    ]
    lines += [
        f"| {issue.page_no} | {issue.missing} | {issue.total} |"
        f" {', '.join(issue.samples)} |"
        for issue in report.worst_pages
    ]
    lines.append("")
    return lines


def _format_limits_section(report: QualityReport) -> list[str]:
    lines = [
        "## What Markdown cannot carry",
        "",
        "These are not conversion errors, they are limits of the format:",
        "",
        "- Italic and bold emphasis becomes plain text.",
        "- Superscript footnote numbers drop into the line.",
        "- Text drawn inside a figure does not come out as text; it stays in the PNG.",
    ]
    if report.merged_cell_tables:
        contain = "contains" if report.merged_cell_tables == 1 else "contain"
        lines.append(
            f"- {_count(report.merged_cell_tables, 'table')} {contain} merged cells;"
            " Markdown repeats the value in every column it spans, while the real"
            " structure stays in the `.json` file."
        )
    lines.append("")
    return lines


def render_markdown(report: QualityReport) -> str:
    """The detailed report written next to the Markdown output."""
    lines = [
        f"# Quality report: {report.pdf_name}",
        "",
        f"Profile: `{report.profile}` | {_count(report.pages, 'page')} |"
        f" {_count(report.tables, 'table')} | {_count(report.pictures, 'image')}",
        "",
        "## Word coverage",
        "",
        *_coverage_section(report),
        *_scanned_pages_section(report),
        *_worst_pages_section(report),
        *_format_limits_section(report),
    ]
    return "\n".join(lines)


def _first_figure(picture: Any) -> Figure | None:
    for prov in picture.prov or []:
        box = prov.bbox
        return Figure(
            page_no=prov.page_no,
            left=min(box.l, box.r),
            bottom=min(box.t, box.b),
            right=max(box.l, box.r),
            top=max(box.t, box.b),
        )
    return None


def _is_furniture(item: Any) -> bool:
    """True for page headers and footers, which Docling drops on purpose."""
    layer = getattr(item, "content_layer", None)
    return getattr(layer, "value", layer) == "furniture"


def _has_merged_cells(table: Any) -> bool:
    return any(
        (cell.col_span or 1) > 1 or (cell.row_span or 1) > 1
        for cell in table.data.table_cells
    )


def describe_document(document: Any) -> DocumentStructure:
    """Pull the structural facts the report needs out of a DoclingDocument."""
    figures = (_first_figure(picture) for picture in document.pictures)

    return DocumentStructure(
        pages=len(document.pages),
        tables=len(document.tables),
        merged_cell_tables=sum(
            1 for table in document.tables if _has_merged_cells(table)
        ),
        figures=tuple(figure for figure in figures if figure is not None),
        furniture_text="\n".join(
            item.text for item in document.texts if _is_furniture(item)
        ),
    )
