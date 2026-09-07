"""Build conversion evidence and render the currently public quality report.

Analysis retains separate PDF-to-Docling and Docling-to-Markdown alignments.
Rendering exposes occurrence-accounted Quality Report v2 metrics while retaining
the legacy v1 coverage only as historical diagnostic data. Reading
(`read_pdf_text`) stays separate from pure analysis so the same logic can run on
hand-built evidence in unit tests.
"""

from __future__ import annotations

import re
import unicodedata
from collections import Counter
from dataclasses import dataclass, field
from math import isfinite
from pathlib import Path
from typing import Any, Iterable, Literal

from . import alignment
from . import quality_metrics

IMAGE_LINK = re.compile(r"!\[[^\]]*\]\([^)]*\)")
TRAILING_DIGITS = re.compile(r"\d+$")

# Punctuation is otherwise outside the comparison contract. Hyphens are the
# exception because removing one would make a true compound compare equal to
# two separate words. Presentation variants used as intra-word hyphens share a
# stable ASCII representation.
HYPHENS = frozenset("-‐‑‒–−")
HYPHEN_TRANSLATION = str.maketrans({character: "-" for character in HYPHENS})
TURKIC_CASE_TRANSLATION = str.maketrans({"I": "ı", "İ": "i"})
PDFIUM_HYPHENATION_MARKER = "\ufffe"

CaseProfile = Literal["unicode", "turkic"]
ProvenanceStatus = Literal[
    "none",
    "single_entry",
    "span_mapped",
    "span_ambiguous",
    "span_unmapped",
    "multiple_unmapped",
]
CASE_PROFILES = frozenset(("unicode", "turkic"))
REPORT_VERSION = 2

FIGURE = "figure"
FURNITURE = "furniture"
FOOTNOTE = "footnote"
UNEXPLAINED = "unexplained"


def _provenance_tuple(provenance: Any | Iterable[Any] | None) -> tuple[Any, ...]:
    if provenance is None:
        return ()
    if isinstance(provenance, tuple):
        return provenance
    if isinstance(provenance, list):
        return tuple(provenance)
    return (provenance,)


@dataclass(frozen=True)
class SourceSpan:
    """Half-open character offsets into a token's original source string."""

    start: int
    end: int


@dataclass(frozen=True)
class SpatialBox:
    """A rectangle in bottom-left-origin PDF page coordinates."""

    left: float
    bottom: float
    right: float
    top: float

    def __post_init__(self) -> None:
        values = (self.left, self.bottom, self.right, self.top)
        if not all(isfinite(value) for value in values):
            raise ValueError("spatial box coordinates must be finite")
        if self.left > self.right or self.bottom > self.top:
            raise ValueError("spatial box coordinates must be ordered")

    def contains_center(self, other: "SpatialBox") -> bool:
        x = (other.left + other.right) / 2
        y = (other.bottom + other.top) / 2
        return self.left <= x <= self.right and self.bottom <= y <= self.top


@dataclass(frozen=True)
class SpatialRegion:
    """One page-qualified region, normalized to PDF bottom-left coordinates."""

    page_no: int
    box: SpatialBox


@dataclass(frozen=True)
class Token:
    """One comparison token with the evidence needed to trace it to source."""

    raw_text: str
    normalized_text: str
    source_span: SourceSpan
    page_no: int | None
    block_id: str | None = None
    provenance: tuple[Any, ...] = field(default=(), compare=False, repr=False)
    all_provenance: tuple[Any, ...] = field(default=(), compare=False, repr=False)
    provenance_status: ProvenanceStatus = "none"
    bounding_boxes: tuple[SpatialBox, ...] = ()
    spatial_regions: tuple[SpatialRegion, ...] = ()
    semantic_role: str | None = None
    case_profile: CaseProfile = "unicode"
    joined_normalized_text: str | None = None
    line_end_hyphen_spans: tuple[SourceSpan, ...] = ()
    line_end_parts: tuple[str, ...] = ()

    @property
    def comparison_forms(self) -> tuple[str, ...]:
        """Conservative form followed by an optional all-joined candidate."""
        if (
            self.joined_normalized_text is None
            or self.joined_normalized_text == self.normalized_text
        ):
            return (self.normalized_text,)
        return (self.normalized_text, self.joined_normalized_text)

    def hyphen_decisions_for(
        self, candidate: str
    ) -> tuple[alignment.HyphenDecision, ...] | None:
        """Resolve each ambiguous separator lazily against one candidate."""
        if not self.line_end_parts or not candidate.startswith(self.line_end_parts[0]):
            return None
        memo: dict[
            tuple[int, int], tuple[alignment.HyphenDecision, ...] | None
        ] = {}

        def resolve(
            part_index: int, offset: int
        ) -> tuple[alignment.HyphenDecision, ...] | None:
            state = (part_index, offset)
            if state in memo:
                return memo[state]
            if part_index == len(self.line_end_parts):
                result = () if offset == len(candidate) else None
                memo[state] = result
                return result

            part = self.line_end_parts[part_index]
            for separator, decision in (("-", "keep"), ("", "join")):
                expected = separator + part
                if candidate.startswith(expected, offset):
                    remainder = resolve(part_index + 1, offset + len(expected))
                    if remainder is not None:
                        result = (decision, *remainder)
                        memo[state] = result
                        return result
            memo[state] = None
            return None

        return resolve(1, len(self.line_end_parts[0]))


@dataclass(frozen=True)
class TextSource:
    """A block of source text and its page/Docling identity, when known."""

    text: str
    page_no: int | None
    block_id: str | None = None
    provenance: tuple[Any, ...] = field(default=(), compare=False, repr=False)
    character_boxes: tuple[SpatialBox | None, ...] = ()
    spatial_regions: tuple[SpatialRegion, ...] = ()
    map_provenance_spans: bool = False
    semantic_role: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "provenance", _provenance_tuple(self.provenance))
        object.__setattr__(self, "character_boxes", tuple(self.character_boxes))
        object.__setattr__(self, "spatial_regions", tuple(self.spatial_regions))


def normalize_token(
    raw_text: str,
    *,
    case_profile: CaseProfile = "unicode",
) -> str:
    """Normalize one logical token deterministically for comparison.

    NFKC expands compatibility glyphs such as typographic ligatures and
    full-width forms. The default profile applies locale-free Unicode case
    folding, preserving English `I`/`i` behavior. A document explicitly marked
    `turkic` maps `İ`/`i` and `I`/`ı` as separate case pairs. No automatic
    language guess is made because a single canonical form cannot satisfy both.
    """
    if case_profile not in CASE_PROFILES:
        raise ValueError(f"Unknown case profile: {case_profile!r}")
    compatible = unicodedata.normalize("NFKC", raw_text)
    case_ready = (
        compatible.translate(TURKIC_CASE_TRANSLATION)
        if case_profile == "turkic"
        else compatible
    )
    return case_ready.casefold().translate(HYPHEN_TRANSLATION)


def _is_word_start(character: str) -> bool:
    return unicodedata.category(character)[:1] in {"L", "N"}


def _is_word_continuation(character: str) -> bool:
    return unicodedata.category(character)[:1] in {"L", "M", "N"}


def _line_end_continuation(text: str, hyphen_at: int) -> int | None:
    """Return the next word offset after a hyphen/newline, if there is one."""
    cursor = hyphen_at + 1
    if text.startswith("\r\n", cursor):
        cursor += 2
    elif cursor < len(text) and text[cursor] in "\r\n":
        cursor += 1
    else:
        return None

    while cursor < len(text) and text[cursor] in " \t":
        cursor += 1
    return cursor if cursor < len(text) and _is_word_start(text[cursor]) else None


def _valid_charspan(provenance: Any, text_length: int) -> tuple[int, int] | None:
    charspan = getattr(provenance, "charspan", None)
    if not isinstance(charspan, (tuple, list)) or len(charspan) != 2:
        return None
    start, end = charspan
    if not isinstance(start, int) or not isinstance(end, int):
        return None
    if start < 0 or start >= end or end > text_length:
        return None
    return start, end


def _token_provenance(
    provenance: tuple[Any, ...],
    token_span: SourceSpan,
    text_length: int,
    fallback_page: int | None,
    map_spans: bool,
) -> tuple[int | None, tuple[Any, ...], ProvenanceStatus]:
    """Choose only provenance that overlaps a token, without inventing a page."""
    if not provenance:
        return fallback_page, (), "none"
    if not map_spans:
        status: ProvenanceStatus = (
            "single_entry" if len(provenance) == 1 else "multiple_unmapped"
        )
        return fallback_page, provenance, status

    valid = tuple(
        (entry, span)
        for entry in provenance
        if (span := _valid_charspan(entry, text_length)) is not None
    )
    if not valid:
        if len(provenance) == 1:
            page = getattr(provenance[0], "page_no", fallback_page)
            return page, provenance, "single_entry"
        return None, provenance, "multiple_unmapped"

    overlapping = tuple(
        entry
        for entry, (start, end) in valid
        if start < token_span.end and token_span.start < end
    )
    if not overlapping:
        return None, provenance, "span_unmapped"

    pages = {getattr(entry, "page_no", None) for entry in overlapping}
    if len(pages) == 1:
        return next(iter(pages)), overlapping, "span_mapped"
    return None, overlapping, "span_ambiguous"


def tokenize(
    text: str,
    *,
    page_no: int | None,
    block_id: str | None = None,
    provenance: Any | Iterable[Any] | None = None,
    case_profile: CaseProfile = "unicode",
    character_boxes: Iterable[SpatialBox | None] = (),
    spatial_regions: Iterable[SpatialRegion] = (),
    map_provenance_spans: bool = False,
    semantic_role: str | None = None,
) -> tuple[Token, ...]:
    """Tokenize Unicode letters/numbers while preserving their source evidence.

    A line-ending hyphen is ambiguous: it can be discretionary hyphenation or a
    real compound wrapped by layout. The primary normalized form conservatively
    keeps the hyphen. The all-joined compatibility form and normalized parts
    retain enough evidence for alignment to resolve every separator
    independently. An intra-line hyphen is never ambiguous.
    """
    tokens: list[Token] = []
    cursor = 0
    provenance_entries = _provenance_tuple(provenance)
    character_box_entries = tuple(character_boxes)
    if character_box_entries and len(character_box_entries) != len(text):
        character_box_entries = ()
    region_entries = tuple(spatial_regions)

    while cursor < len(text):
        if not _is_word_start(text[cursor]):
            cursor += 1
            continue

        start = cursor
        segment_parts: list[str] = []
        line_end_parts: list[str] = []
        line_end_hyphens: list[SourceSpan] = []

        while True:
            part_start = cursor
            cursor += 1
            while cursor < len(text) and _is_word_continuation(text[cursor]):
                cursor += 1
            word_part = text[part_start:cursor]
            segment_parts.append(word_part)

            # PDFium represents a removed line-end hyphen with U+FFFE between
            # the two word pieces. It is source evidence, not a word boundary.
            if (
                cursor + 1 < len(text)
                and text[cursor] == PDFIUM_HYPHENATION_MARKER
                and _is_word_start(text[cursor + 1])
            ):
                line_end_parts.append("".join(segment_parts))
                segment_parts = []
                line_end_hyphens.append(SourceSpan(cursor, cursor + 1))
                cursor += 1
                continue

            if cursor >= len(text) or text[cursor] not in HYPHENS:
                break

            continuation = _line_end_continuation(text, cursor)
            if continuation is not None:
                line_end_parts.append("".join(segment_parts))
                segment_parts = []
                line_end_hyphens.append(SourceSpan(cursor, continuation))
                cursor = continuation
                continue

            if cursor + 1 < len(text) and _is_word_start(text[cursor + 1]):
                segment_parts.append("-")
                cursor += 1
                continue
            break

        raw_text = text[start:cursor]
        normalized_line_end_parts = tuple(
            normalize_token(part, case_profile=case_profile)
            for part in (*line_end_parts, "".join(segment_parts))
        )
        normalized_text = "-".join(normalized_line_end_parts)
        joined_normalized_text = (
            "".join(normalized_line_end_parts)
            if line_end_hyphens
            else None
        )
        source_span = SourceSpan(start, cursor)
        token_page, token_provenance, provenance_status = _token_provenance(
            provenance_entries,
            source_span,
            len(text),
            page_no,
            map_provenance_spans,
        )
        token_regions = tuple(
            region
            for region in region_entries
            if token_page is None or region.page_no == token_page
        )
        tokens.append(
            Token(
                raw_text=raw_text,
                normalized_text=normalized_text,
                source_span=source_span,
                page_no=token_page,
                block_id=block_id,
                provenance=token_provenance,
                all_provenance=provenance_entries,
                provenance_status=provenance_status,
                bounding_boxes=tuple(
                    box
                    for box in character_box_entries[start:cursor]
                    if box is not None
                ),
                spatial_regions=token_regions,
                semantic_role=semantic_role,
                case_profile=case_profile,
                joined_normalized_text=joined_normalized_text,
                line_end_hyphen_spans=tuple(line_end_hyphens),
                line_end_parts=(
                    normalized_line_end_parts if line_end_hyphens else ()
                ),
            )
        )

    return tuple(tokens)


def tokenize_sources(
    sources: Iterable[TextSource],
    *,
    case_profile: CaseProfile = "unicode",
) -> tuple[Token, ...]:
    """Tokenize attributed blocks without flattening page or provenance data."""
    return tuple(
        token
        for source in sources
        for token in tokenize(
            source.text,
            page_no=source.page_no,
            block_id=source.block_id,
            provenance=source.provenance,
            case_profile=case_profile,
            character_boxes=source.character_boxes,
            spatial_regions=source.spatial_regions,
            map_provenance_spans=source.map_provenance_spans,
            semantic_role=source.semantic_role,
        )
    )


@dataclass(frozen=True)
class Figure:
    """One extracted picture and where it sits on its PDF page."""

    page_no: int
    left: float
    bottom: float
    right: float
    top: float
    block_id: str | None = None
    provenance: tuple[Any, ...] = field(default=(), compare=False, repr=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "provenance", _provenance_tuple(self.provenance))


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
    furniture_sources: tuple[TextSource, ...] = ()
    content_sources: tuple[TextSource, ...] = ()
    table_repeat_sources: tuple[TextSource, ...] = ()


@dataclass(frozen=True)
class PdfText:
    """Everything read out of the source PDF, in one pass."""

    name: str
    pages: tuple[str, ...]
    figure_text: str = ""
    figure_sources: tuple[TextSource, ...] = ()
    case_profile: CaseProfile = "unicode"
    page_char_boxes: tuple[tuple[SpatialBox | None, ...], ...] = ()


def tokenize_pdf_pages(pdf_text: PdfText) -> tuple[Token, ...]:
    """Tokenize PDF text-layer pages without losing their page boundary."""
    return tokenize_sources(
        (
            TextSource(
                page,
                page_no,
                block_id=f"pdf-page:{page_no}",
                character_boxes=(
                    pdf_text.page_char_boxes[page_no - 1]
                    if page_no <= len(pdf_text.page_char_boxes)
                    else ()
                ),
            )
            for page_no, page in enumerate(pdf_text.pages, start=1)
        ),
        case_profile=pdf_text.case_profile,
    )


FENCE_LINE = re.compile(r"(?m)^[ \t]*(?:`{3,}|~{3,})[^\r\n]*")
MARKDOWN_IMAGE = re.compile(
    r"!\[[^\]]*\]\((?:[^()\r\n]|\([^()\r\n]*\))*\)"
)
INLINE_LINK = re.compile(
    r"(?<!!)\[([^\]]+)\]\((?:[^()\r\n]|\([^()\r\n]*\))*\)"
)
REFERENCE_LINK = re.compile(r"(?<!!)\[([^\]]+)\]\[[^\]]*\]")
REFERENCE_DEFINITION = re.compile(r"(?m)^[ \t]{0,3}\[[^\]]+\]:[^\r\n]*")
ORDERED_LIST_MARKER = re.compile(r"(?m)^[ \t]{0,3}\d+[.)](?=[ \t])")
HTML_TAG = re.compile(r"<[/!?A-Za-z][^>]*>")
AUTOLINK = re.compile(
    r"<(?:[A-Za-z][A-Za-z0-9+.-]{1,31}:[^<>\s]+|"
    r"[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@"
    r"[A-Za-z0-9](?:[A-Za-z0-9.-]*[A-Za-z0-9])?)>"
)


def _masked_markdown_text(markdown_text: str) -> str:
    """Mask non-visible Markdown syntax while preserving original offsets."""
    characters = list(markdown_text)

    def mask(start: int, end: int) -> None:
        for index in range(start, end):
            if characters[index] not in "\r\n":
                characters[index] = " "

    for match in FENCE_LINE.finditer(markdown_text):
        mask(*match.span())
    for match in REFERENCE_DEFINITION.finditer(markdown_text):
        mask(*match.span())
    for match in ORDERED_LIST_MARKER.finditer(markdown_text):
        mask(*match.span())
    for match in MARKDOWN_IMAGE.finditer(markdown_text):
        mask(*match.span())
    for pattern in (INLINE_LINK, REFERENCE_LINK):
        for match in pattern.finditer(markdown_text):
            full_start, full_end = match.span()
            label_start, label_end = match.span(1)
            mask(full_start, label_start)
            mask(label_end, full_end)
    for match in HTML_TAG.finditer(markdown_text):
        if AUTOLINK.fullmatch(match.group(0)):
            mask(match.start(), match.start() + 1)
            mask(match.end() - 1, match.end())
        else:
            mask(*match.span())
    return "".join(characters)


def tokenize_markdown(
    markdown_text: str,
    *,
    case_profile: CaseProfile = "unicode",
) -> tuple[Token, ...]:
    """Tokenize visible Markdown text and retain Markdown source offsets."""
    return tokenize(
        _masked_markdown_text(markdown_text),
        page_no=None,
        block_id="markdown",
        case_profile=case_profile,
    )


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
    alignments: alignment.TwoStageAlignment = field(compare=False, repr=False)
    report_version: int = REPORT_VERSION

    @property
    def extraction_metrics(self) -> quality_metrics.StageMetrics:
        return quality_metrics.summarize_alignment(self.alignments.extraction)

    @property
    def serialization_metrics(self) -> quality_metrics.StageMetrics:
        return quality_metrics.summarize_alignment(self.alignments.serialization)

    @property
    def legacy_coverage(self) -> float:
        """The retained v1 bag-of-words percentage, not v2 accuracy."""
        if not self.words_in_pdf:
            return 0.0
        return 100.0 * self.words_matched / self.words_in_pdf

    @property
    def coverage(self) -> float:
        """Compatibility alias for :attr:`legacy_coverage`."""
        return self.legacy_coverage

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


def _legacy_word_counts(
    text: str,
    page_no: int | None = None,
    case_profile: CaseProfile = "unicode",
) -> Counter[str]:
    """Legacy v1 tally backed by evidence-rich tokens."""
    return Counter(
        token.normalized_text
        for token in tokenize(text, page_no=page_no, case_profile=case_profile)
    )


def _pdfium_character_boxes(textpage: Any, text: str) -> tuple[SpatialBox | None, ...]:
    """Read PDFium character boxes only when offsets map exactly to its text."""
    try:
        count = int(textpage.count_chars())
    except Exception:
        return ()
    if count != len(text):
        return ()

    boxes: list[SpatialBox | None] = []
    for index in range(count):
        try:
            left, bottom, right, top = textpage.get_charbox(index)
            boxes.append(
                SpatialBox(
                    min(float(left), float(right)),
                    min(float(bottom), float(top)),
                    max(float(left), float(right)),
                    max(float(bottom), float(top)),
                )
            )
        except (IndexError, TypeError, ValueError, RuntimeError):
            boxes.append(None)
    return tuple(boxes)


def read_pdf_text(
    pdf_path: Path,
    figures: tuple[Figure, ...] = (),
    *,
    case_profile: CaseProfile = "unicode",
) -> PdfText:
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
        page_char_boxes = tuple(
            _pdfium_character_boxes(textpage, text)
            for textpage, text in zip(text_pages, pages)
        )
        figure_sources = [
            TextSource(
                text=text_pages[figure.page_no - 1].get_text_bounded(
                    left=figure.left,
                    bottom=figure.bottom,
                    right=figure.right,
                    top=figure.top,
                ),
                page_no=figure.page_no,
                block_id=figure.block_id or f"figure:{index}",
                provenance=_provenance_tuple(figure.provenance) or (figure,),
                spatial_regions=(
                    SpatialRegion(
                        figure.page_no,
                        SpatialBox(
                            figure.left,
                            figure.bottom,
                            figure.right,
                            figure.top,
                        ),
                    ),
                ),
            )
            for index, figure in enumerate(figures, start=1)
            if 0 < figure.page_no <= len(text_pages)
        ]
    finally:
        document.close()

    return PdfText(
        pdf_path.name,
        pages,
        "\n".join(source.text for source in figure_sources),
        tuple(figure_sources),
        case_profile,
        page_char_boxes,
    )


@dataclass
class _LegacyTally:
    """Running totals while the pages are being compared."""

    words_in_pdf: int = 0
    words_matched: int = 0
    counts: Counter = field(default_factory=Counter)


def _legacy_classify(
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
    """Build two-stage evidence while retaining the rendered v1 measurement."""
    case_profile = pdf_text.case_profile
    markdown_words = _legacy_word_counts(
        IMAGE_LINK.sub(" ", markdown_text), case_profile=case_profile
    )
    figure_words = Counter(
        token.normalized_text
        for token in (
            tokenize_sources(pdf_text.figure_sources, case_profile=case_profile)
            if pdf_text.figure_sources
            else tokenize(
                pdf_text.figure_text,
                page_no=None,
                case_profile=case_profile,
            )
        )
    )
    furniture_words = Counter(
        token.normalized_text
        for token in (
            tokenize_sources(structure.furniture_sources, case_profile=case_profile)
            if structure.furniture_sources
            else tokenize(
                structure.furniture_text,
                page_no=None,
                case_profile=case_profile,
            )
        )
    )

    tally = _LegacyTally()
    scanned_pages: list[int] = []
    issues: list[PageIssue] = []

    for page_no, page_text in enumerate(pdf_text.pages, start=1):
        page_words = _legacy_word_counts(page_text, page_no, case_profile)
        if not page_words:
            scanned_pages.append(page_no)
            continue

        page_total = sum(page_words.values())
        missing = page_words - markdown_words
        tally.words_in_pdf += page_total
        tally.words_matched += page_total - sum(missing.values())

        unexplained = Counter()
        for word, count in missing.items():
            reason = _legacy_classify(
                word, figure_words, furniture_words, markdown_words
            )
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

    pdf_tokens = tokenize_pdf_pages(pdf_text)
    docling_tokens = tokenize_sources(
        structure.content_sources, case_profile=case_profile
    )
    markdown_tokens = tokenize_markdown(markdown_text, case_profile=case_profile)
    figure_tokens = tokenize_sources(
        pdf_text.figure_sources, case_profile=case_profile
    )
    furniture_tokens = tokenize_sources(
        structure.furniture_sources, case_profile=case_profile
    )
    table_repeat_tokens = tokenize_sources(
        structure.table_repeat_sources, case_profile=case_profile
    )
    alignments = alignment.align_two_stage(
        pdf_tokens,
        docling_tokens,
        markdown_tokens,
        case_profile=case_profile,
        figure_tokens=figure_tokens,
        furniture_tokens=furniture_tokens,
        table_repeat_tokens=table_repeat_tokens,
    )

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
        alignments=alignments,
    )


def render_console(report: QualityReport) -> str:
    """Render a concise two-stage v2 summary without an accuracy claim."""
    extraction = report.extraction_metrics
    serialization = report.serialization_metrics
    lines = [
        "Quality Report v2"
        f" | Extraction: transfer {_console_rate(extraction)};"
        f" unexplained {extraction.unexplained_loss_numerator};"
        f" order risks {extraction.order_risk_count}"
        f" | Serialization: transfer {_console_rate(serialization)};"
        f" unexpected {serialization.unexpected_addition_numerator};"
        f" order risks {serialization.order_risk_count}",
        "Structure: not evaluated in this milestone.",
    ]

    scanned = len(report.pages_without_text_layer)
    if scanned and report.profile == "fast":
        verb = "is" if scanned == 1 else "are"
        pronoun = "it" if scanned == 1 else "they"
        lines.append(
            f"WARNING: {_count(scanned, 'page')} without a text layer {verb}"
            f" unverified; --fast turned OCR off, so {pronoun} may have come out"
            " empty. Coverage"
            " cannot be measured. Try again with --quality."
        )
    elif scanned:
        pronoun = "it" if scanned == 1 else "them"
        lines.append(
            f"Unverified: {_count(scanned, 'page')} without a text layer; PDF"
            " text-layer agreement cannot verify OCR output and coverage cannot"
            f" be measured for {pronoun}."
        )
    return "\n".join(lines)


def _console_rate(metrics: quality_metrics.StageMetrics) -> str:
    rate = metrics.normalized_exact_transfer_rate
    if rate is None:
        return "n/a (no source tokens)"
    return f"{rate:.1%} ({metrics.matched_source_count}/{metrics.source_token_count})"


def _rate_cell(rate: float | None, numerator: int, denominator: int) -> str:
    if rate is None:
        return "n/a (zero denominator)"
    return f"{rate:.2%} ({numerator:,}/{denominator:,})"


def _stage_metrics_section(
    title: str, metrics: quality_metrics.StageMetrics
) -> list[str]:
    return [
        f"## {title}",
        "",
        "| Measure | Value |",
        "|---|---:|",
        f"| Source tokens | {metrics.source_token_count:,} |",
        f"| Target tokens | {metrics.target_token_count:,} |",
        f"| Normalized matches | {metrics.normalized_match_count:,} |",
        f"| Contextual line-end-hyphen matches | {metrics.contextual_hyphen_match_count:,} |",
        f"| Explained deletions | {metrics.explained_deletion_count:,} |",
        f"| Unexplained deletions | {metrics.unexplained_deletion_count:,} |",
        f"| Substitutions | {metrics.substitution_count:,} |",
        f"| Reading-order risks | {metrics.order_risk_count:,} |",
        f"| Explained additions | {metrics.explained_addition_count:,} |",
        f"| Unexpected insertions | {metrics.unexpected_insertion_count:,} |",
        "| Normalized exact-transfer rate | "
        f"{_rate_cell(metrics.normalized_exact_transfer_rate, metrics.matched_source_count, metrics.source_token_count)} |",
        "| Accounted-for loss rate | "
        f"{_rate_cell(metrics.accounted_for_loss_rate, metrics.explained_deletion_count, metrics.source_token_count)} |",
        "| Unexplained-loss rate | "
        f"{_rate_cell(metrics.unexplained_loss_rate, metrics.unexplained_loss_numerator, metrics.source_token_count)} |",
        "| Unexpected-addition rate | "
        f"{_rate_cell(metrics.unexpected_addition_rate, metrics.unexpected_addition_numerator, metrics.target_token_count)} |",
        "",
        "Source accounting: "
        f"**{metrics.source_token_count:,} = {metrics.matched_source_count:,} accepted matches"
        f" + {metrics.explained_deletion_count:,} explained deletions"
        f" + {metrics.unexplained_deletion_count:,} unexplained deletions"
        f" + {metrics.substitution_count:,} substitutions"
        f" + {metrics.order_risk_count:,} order risks**.",
        "",
        "Target accounting: "
        f"**{metrics.target_token_count:,} = {metrics.matched_source_count:,} accepted matches"
        f" + {metrics.explained_addition_count:,} explained additions"
        f" + {metrics.unexpected_insertion_count:,} unexpected insertions"
        f" + {metrics.substitution_count:,} substitutions"
        f" + {metrics.order_risk_count:,} order risks**.",
        "",
        "Contextual line-end-hyphen matches are accepted transfers but retain"
        " their distinct reason. Substitutions count once as source loss and once"
        " as a target addition. Order risks are neither matches nor losses.",
        "",
        *_representative_issues(metrics),
    ]


def _inline_code(value: str) -> str:
    fence = "``" if "`" in value else "`"
    return f"{fence}{value}{fence}"


def _provenance_description(entries: tuple[Any, ...]) -> str:
    if not entries:
        return "unknown"
    descriptions: list[str] = []
    for entry in entries[:2]:
        parts: list[str] = []
        page_no = getattr(entry, "page_no", None)
        charspan = getattr(entry, "charspan", None)
        if page_no is not None:
            parts.append(f"page={page_no}")
        if charspan is not None:
            parts.append(f"charspan={charspan}")
        descriptions.append(", ".join(parts) if parts else type(entry).__name__)
    if len(entries) > 2:
        descriptions.append(f"+{len(entries) - 2} more")
    return "; ".join(descriptions)


def _token_description(token: alignment.TokenEvidence | None) -> str:
    if token is None:
        return "none"
    details = [f"occurrence #{token.index}", f"raw {_inline_code(token.raw_text)}"]
    if token.normalized_text != token.raw_text:
        details.append(f"normalized {_inline_code(token.normalized_text)}")
    details.append(f"page {token.page_no if token.page_no is not None else 'unknown'}")
    details.append(
        f"block {_inline_code(token.block_id) if token.block_id is not None else 'unknown'}"
    )
    details.append(f"provenance {_provenance_description(token.provenance)}")
    return "; ".join(details)


def _context_description(tokens: tuple[alignment.TokenEvidence, ...]) -> str:
    if not tokens:
        return "(empty)"
    return " · ".join(
        f"#{token.index} {_inline_code(token.raw_text)}" for token in tokens
    )


def _reason_description(operation: alignment.AlignmentOperation) -> str:
    descriptions = {
        alignment.MatchKind.FIGURE: "spatially verified figure text",
        alignment.MatchKind.FURNITURE: "spatially verified page furniture",
        alignment.MatchKind.FOOTNOTE: "typed Docling footnote with provenance",
        alignment.MatchKind.TABLE_REPETITION: (
            "locally anchored merged-table-cell serialization repetition"
        ),
        alignment.MatchKind.UNEXPLAINED: "no sufficient explanation evidence",
        alignment.MatchKind.ADDED: "unexpected target occurrence",
        alignment.MatchKind.DIFFERENT: "source and target occurrences differ",
        alignment.MatchKind.REORDERED: "possible reading-order disagreement",
    }
    return descriptions.get(operation.match_kind, operation.match_kind.value)


def _representative_issues(metrics: quality_metrics.StageMetrics) -> list[str]:
    lines = ["### Representative issues", ""]
    if not metrics.representative_issues:
        return [*lines, "None.", ""]
    for number, issue in enumerate(metrics.representative_issues, start=1):
        operation = issue.operation
        lines.extend(
            (
                f"{number}. **{operation.stage.value} · {operation.type.value}"
                f" · {operation.match_kind.value}**",
                f"   - Source: {_token_description(operation.source_token)}",
                f"   - Target: {_token_description(operation.target_token)}",
                f"   - Source context: {_context_description(issue.source_context)}",
                f"   - Target context: {_context_description(issue.target_context)}",
                f"   - Reason: {_reason_description(operation)}.",
            )
        )
        if operation.evidence_token is not None:
            lines.append(
                f"   - Explanation evidence: {_token_description(operation.evidence_token)}"
            )
    lines.append("")
    return lines


def _scanned_pages_section(report: QualityReport) -> list[str]:
    if not report.pages_without_text_layer:
        return []

    shown = report.pages_without_text_layer[:20]
    listed = ", ".join(str(page_no) for page_no in shown)
    if len(report.pages_without_text_layer) > len(shown):
        listed += " ..."

    lines = [
        "## Unverified pages",
        "",
        f"{_count(len(report.pages_without_text_layer), 'page')}"
        f" {'looks' if len(report.pages_without_text_layer) == 1 else 'look'}"
        f" scanned: {listed}",
        "",
        "These pages have no independent text-layer reference. Text-layer"
        " agreement cannot verify their OCR output, and coverage cannot be"
        " measured for them.",
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
    """Render the occurrence-accounted, two-stage Quality Report v2."""
    lines = [
        f"# Quality Report v2: {report.pdf_name}",
        "",
        f"Profile: `{report.profile}` | {_count(report.pages, 'page')} |"
        f" {_count(report.tables, 'table')} | {_count(report.pictures, 'image')}",
        "",
        "This report measures agreement with the PDF text layer; it is not"
        " verified document accuracy. Extraction and serialization are reported"
        " separately so a successful later stage cannot hide an earlier loss.",
        "",
        *_stage_metrics_section(
            "Extraction: PDF text layer → Docling", report.extraction_metrics
        ),
        *_stage_metrics_section(
            "Serialization: Docling → Markdown", report.serialization_metrics
        ),
        *_scanned_pages_section(report),
        "## Structural integrity",
        "",
        "Heading, list, table, link, and artifact integrity are not evaluated in"
        " this milestone.",
        "",
        *_format_limits_section(report),
        "## Legacy diagnostic",
        "",
        f"Historical v1 bag-of-words coverage: **{report.legacy_coverage:.2f}%**.",
        "This compatibility value is not a v2 headline metric and is not verified"
        " conversion accuracy. It can overstate transfer because its historical"
        " accounting differs from the occurrence-based stages above.",
        "",
    ]
    return "\n".join(lines)


def _page_heights(document: Any) -> dict[int, float]:
    heights: dict[int, float] = {}
    pages = getattr(document, "pages", {})
    values = pages.items() if hasattr(pages, "items") else enumerate(pages, start=1)
    for page_number, page in values:
        size = getattr(page, "size", None)
        height = getattr(size, "height", None)
        if isinstance(height, (int, float)) and isfinite(height) and height > 0:
            heights[int(page_number)] = float(height)
    return heights


def _docling_spatial_region(
    provenance: Any, page_heights: dict[int, float]
) -> SpatialRegion | None:
    page_no = getattr(provenance, "page_no", None)
    box = getattr(provenance, "bbox", None)
    if not isinstance(page_no, int) or box is None:
        return None
    try:
        left, right = sorted((float(box.l), float(box.r)))
        first_y, second_y = float(box.t), float(box.b)
    except (AttributeError, TypeError, ValueError):
        return None

    origin = getattr(box, "coord_origin", None)
    if origin is None:
        return None
    origin_value = str(getattr(origin, "value", origin)).upper()
    if "TOPLEFT" in origin_value or "TOP_LEFT" in origin_value:
        height = page_heights.get(page_no)
        if height is None:
            return None
        bottom = height - max(first_y, second_y)
        top = height - min(first_y, second_y)
    elif "BOTTOMLEFT" in origin_value or "BOTTOM_LEFT" in origin_value:
        bottom, top = sorted((first_y, second_y))
    else:
        return None
    try:
        return SpatialRegion(page_no, SpatialBox(left, bottom, right, top))
    except ValueError:
        return None


def _provenance_regions(
    provenance: tuple[Any, ...], page_heights: dict[int, float]
) -> tuple[SpatialRegion, ...]:
    return tuple(
        region
        for entry in provenance
        if (region := _docling_spatial_region(entry, page_heights)) is not None
    )


def _first_figure(
    picture: Any, page_heights: dict[int, float]
) -> Figure | None:
    provenance = tuple(picture.prov or ())
    for prov in provenance:
        region = _docling_spatial_region(prov, page_heights)
        if region is None:
            continue
        box = region.box
        return Figure(
            page_no=region.page_no,
            left=box.left,
            bottom=box.bottom,
            right=box.right,
            top=box.top,
            block_id=_docling_block_id(picture),
            provenance=provenance,
        )
    return None


def _is_furniture(item: Any) -> bool:
    """True for page headers and footers, which Docling drops on purpose."""
    layer = getattr(item, "content_layer", None)
    return getattr(layer, "value", layer) == "furniture"


def _docling_block_id(item: Any) -> str | None:
    identity = getattr(item, "self_ref", None)
    if identity is None:
        identity = getattr(item, "id", None)
    return str(identity) if identity is not None else None


def _docling_semantic_role(item: Any) -> str | None:
    label = getattr(item, "label", None)
    value = getattr(label, "value", label)
    return str(value).casefold() if value is not None else None


def _docling_text_source(
    item: Any, page_heights: dict[int, float] | None = None
) -> TextSource:
    provenance = tuple(getattr(item, "prov", None) or ())
    return TextSource(
        text=item.text,
        page_no=(
            getattr(provenance[0], "page_no", None)
            if len(provenance) == 1
            else None
        ),
        block_id=_docling_block_id(item),
        provenance=provenance,
        spatial_regions=_provenance_regions(provenance, page_heights or {}),
        map_provenance_spans=True,
        semantic_role=_docling_semantic_role(item),
    )


def _docling_table_sources(table: Any) -> tuple[TextSource, ...]:
    provenance = tuple(getattr(table, "prov", None) or ())
    table_id = _docling_block_id(table) or "table"
    cells = getattr(getattr(table, "data", None), "table_cells", ())
    return tuple(
        TextSource(
            text=cell.text,
            page_no=(
                getattr(provenance[0], "page_no", None)
                if len(provenance) == 1
                else None
            ),
            block_id=f"{table_id}/cells/{index}",
            provenance=provenance,
            map_provenance_spans=False,
            semantic_role="table_cell",
        )
        for index, cell in enumerate(cells)
        if isinstance(getattr(cell, "text", None), str) and cell.text
    )


def _docling_table_repeat_sources(table: Any) -> tuple[TextSource, ...]:
    """Create one evidence slot per extra merged-cell serialization copy."""
    provenance = tuple(getattr(table, "prov", None) or ())
    table_id = _docling_block_id(table) or "table"
    cells = getattr(getattr(table, "data", None), "table_cells", ())
    sources: list[TextSource] = []
    for index, cell in enumerate(cells):
        text = getattr(cell, "text", None)
        if not isinstance(text, str) or not text:
            continue
        row_span = max(1, int(getattr(cell, "row_span", 1) or 1))
        col_span = max(1, int(getattr(cell, "col_span", 1) or 1))
        for _ in range(row_span * col_span - 1):
            sources.append(
                TextSource(
                    text=text,
                    page_no=(
                        getattr(provenance[0], "page_no", None)
                        if len(provenance) == 1
                        else None
                    ),
                    block_id=f"{table_id}/cells/{index}",
                    provenance=provenance,
                    map_provenance_spans=False,
                    semantic_role="table_repeat",
                )
            )
    return tuple(sources)


def _docling_content_sources(
    document: Any, page_heights: dict[int, float] | None = None
) -> tuple[TextSource, ...]:
    """Read body text and table cells in Docling's document order."""
    iterate_items = getattr(document, "iterate_items", None)
    sources: list[TextSource] = []
    if callable(iterate_items):
        for item, _level in iterate_items():
            if _is_furniture(item):
                continue
            if isinstance(getattr(item, "text", None), str):
                sources.append(_docling_text_source(item, page_heights))
            elif hasattr(getattr(item, "data", None), "table_cells"):
                sources.extend(_docling_table_sources(item))
        return tuple(sources)

    sources.extend(
        _docling_text_source(item, page_heights)
        for item in getattr(document, "texts", ())
        if not _is_furniture(item) and isinstance(getattr(item, "text", None), str)
    )
    for table in getattr(document, "tables", ()):
        sources.extend(_docling_table_sources(table))
    return tuple(sources)


def tokenize_docling_items(
    items: Iterable[Any],
    *,
    case_profile: CaseProfile = "unicode",
) -> tuple[Token, ...]:
    """Tokenize Docling items by overlapping item-relative provenance spans."""
    return tokenize_sources(
        (
            _docling_text_source(item)
            for item in items
            if isinstance(getattr(item, "text", None), str)
        ),
        case_profile=case_profile,
    )


def _has_merged_cells(table: Any) -> bool:
    return any(
        (cell.col_span or 1) > 1 or (cell.row_span or 1) > 1
        for cell in table.data.table_cells
    )


def describe_document(document: Any) -> DocumentStructure:
    """Pull the structural facts the report needs out of a DoclingDocument."""
    page_heights = _page_heights(document)
    figures = (_first_figure(picture, page_heights) for picture in document.pictures)
    furniture_sources = tuple(
        _docling_text_source(item, page_heights)
        for item in document.texts
        if _is_furniture(item)
    )
    table_repeat_sources = tuple(
        source
        for table in document.tables
        for source in _docling_table_repeat_sources(table)
    )

    return DocumentStructure(
        pages=len(document.pages),
        tables=len(document.tables),
        merged_cell_tables=sum(
            1 for table in document.tables if _has_merged_cells(table)
        ),
        figures=tuple(figure for figure in figures if figure is not None),
        furniture_text="\n".join(source.text for source in furniture_sources),
        furniture_sources=furniture_sources,
        content_sources=_docling_content_sources(document, page_heights),
        table_repeat_sources=table_repeat_sources,
    )
