"""Check Docling-to-Markdown structure and local output artifacts.

The parser intentionally covers the GitHub-Flavoured Markdown subset emitted by
Docling.  It is not a general CommonMark validator.  Expected facts come from
the DoclingDocument while actual facts come from the Markdown file, keeping
this check on the serialization side of the quality report.
"""

from __future__ import annotations

import html
import os
import re
import unicodedata
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from pathlib import Path, PureWindowsPath
from typing import Any, Iterable, Literal
from urllib.parse import unquote, urlsplit


Category = Literal["heading", "list", "table", "link", "artifact"]

FENCE = re.compile(r"^[ \t]*(?P<marker>`{3,}|~{3,})(?P<info>.*)$")
HEADING = re.compile(r"^[ \t]{0,3}(#{1,6})[ \t]+(.+?)\s*$")
LIST_ITEM = re.compile(
    r"^(?P<indent>[ \t]*)(?P<marker>[-+*]|\d+[.)])[ \t]+(?P<text>.*)$"
)
TABLE_SEPARATOR_CELL = re.compile(r"^:?-+:?$")
ESCAPED_MARKDOWN = re.compile(r"\\([\\`*_{}\[\]()#+\-.!|>])")
EXTERNAL_SCHEMES = frozenset(("http", "https", "mailto"))


@dataclass(frozen=True)
class CountComparison:
    expected: int
    actual: int

    def as_tuple(self) -> tuple[int, int]:
        """Return expected then actual for compact assertions and rendering."""
        return self.expected, self.actual


@dataclass(frozen=True)
class HeadingRecord:
    level: int
    text: str
    line: int | None = field(default=None, compare=False)


@dataclass(frozen=True)
class ListItemRecord:
    depth: int
    ordered: bool
    text: str
    line: int | None = field(default=None, compare=False)


@dataclass(frozen=True)
class TableRecord:
    rows: tuple[tuple[str, ...], ...]
    line: int | None = field(default=None, compare=False)


@dataclass(frozen=True)
class LinkRecord:
    target: str
    line: int | None = field(default=None, compare=False)


@dataclass(frozen=True)
class StructuralExpectation:
    headings: tuple[HeadingRecord, ...]
    list_count: int
    list_items: tuple[ListItemRecord, ...]
    tables: tuple[TableRecord, ...]
    links: tuple[LinkRecord, ...]
    picture_count: int


@dataclass(frozen=True)
class MarkdownStructure:
    headings: tuple[HeadingRecord, ...]
    list_count: int
    list_items: tuple[ListItemRecord, ...]
    tables: tuple[TableRecord, ...]
    links: tuple[LinkRecord, ...]
    images: tuple[LinkRecord, ...]


@dataclass(frozen=True)
class IntegrityIssue:
    category: Category
    code: str
    expected: str
    actual: str
    location: str


@dataclass(frozen=True)
class ArtifactCheck:
    target: str
    status: str
    size_bytes: int | None = None
    format: str | None = None
    width: int | None = None
    height: int | None = None


@dataclass(frozen=True)
class StructuralIntegrityReport:
    headings: CountComparison
    lists: CountComparison
    list_items: CountComparison
    tables: CountComparison
    table_cells: CountComparison
    links: CountComparison
    images: CountComparison
    issues: tuple[IntegrityIssue, ...]
    artifacts: tuple[ArtifactCheck, ...]

    @property
    def passed(self) -> bool:
        return not self.issues

    @property
    def valid_image_count(self) -> int:
        return sum(artifact.status == "valid" for artifact in self.artifacts)

    @property
    def stale_artifact_count(self) -> int:
        return sum(artifact.status == "stale" for artifact in self.artifacts)


def empty_report() -> StructuralIntegrityReport:
    """Return an evaluated, empty structure for hand-built report tests."""
    zero = CountComparison(0, 0)
    return StructuralIntegrityReport(
        headings=zero,
        lists=zero,
        list_items=zero,
        tables=zero,
        table_cells=zero,
        links=zero,
        images=zero,
        issues=(),
        artifacts=(),
    )


def _value(value: Any) -> Any:
    return getattr(value, "value", value)


def _label(item: Any) -> str | None:
    value = _value(getattr(item, "label", None))
    return str(value).casefold() if value is not None else None


def _canonical_text(value: Any) -> str:
    if value is None:
        return ""
    return " ".join(str(value).replace("\r", " ").replace("\n", " ").split())


def _canonical_target(value: Any) -> str:
    return str(value).strip().replace("\\", "/")


def _document_items(document: Any) -> tuple[tuple[Any, int], ...]:
    iterate_items = getattr(document, "iterate_items", None)
    if not callable(iterate_items):
        return ()
    try:
        return tuple(iterate_items(with_groups=True))
    except TypeError:
        return tuple(iterate_items())


def _table_cell_text(cell: Any, document: Any) -> str:
    text = getattr(cell, "text", None)
    if text is None:
        reference = getattr(cell, "ref", None)
        resolve = getattr(reference, "resolve", None)
        if callable(resolve):
            try:
                text = getattr(resolve(doc=document), "text", "")
            except TypeError:
                text = getattr(resolve(document), "text", "")
    return _canonical_text(text)


def inspect_document(document: Any) -> StructuralExpectation:
    """Extract Markdown-relevant structural expectations without Docling imports."""
    headings: list[HeadingRecord] = []
    list_items: list[ListItemRecord] = []
    tables: list[TableRecord] = []
    links: list[LinkRecord] = []
    list_count = 0
    picture_count = 0
    active_list_levels: list[int] = []
    inferred_list_active = False

    for item, raw_level in _document_items(document):
        level = int(raw_level or 0)
        item_label = _label(item)

        if item_label == "list":
            active_list_levels = [value for value in active_list_levels if value < level]
            active_list_levels.append(level)
            list_count += 1
            inferred_list_active = True
            continue

        active_list_levels = [value for value in active_list_levels if value < level]

        if item_label == "title":
            headings.append(HeadingRecord(1, _canonical_text(getattr(item, "text", ""))))
        elif item_label == "section_header":
            heading_level = int(getattr(item, "level", 1) or 1) + 1
            headings.append(
                HeadingRecord(heading_level, _canonical_text(getattr(item, "text", "")))
            )

        if item_label == "picture":
            picture_count += 1

        if item_label == "list_item":
            if not active_list_levels and not inferred_list_active:
                list_count += 1
                inferred_list_active = True
            depth = max(0, len(active_list_levels) - 1)
            marker = str(getattr(item, "marker", "") or "")
            ordered = bool(getattr(item, "enumerated", False)) or bool(
                re.fullmatch(r"\d+[.)]", marker)
            )
            list_items.append(
                ListItemRecord(
                    depth,
                    ordered,
                    _canonical_text(getattr(item, "text", "")),
                )
            )
        elif item_label != "list":
            inferred_list_active = False

        data = getattr(item, "data", None)
        grid = getattr(data, "grid", None)
        if item_label == "table" or grid is not None:
            rows = tuple(
                tuple(_table_cell_text(cell, document) for cell in row)
                for row in (grid or ())
            )
            tables.append(TableRecord(rows))

        hyperlink = getattr(item, "hyperlink", None)
        if hyperlink is not None:
            links.append(LinkRecord(_canonical_target(hyperlink)))

    return StructuralExpectation(
        headings=tuple(headings),
        list_count=list_count,
        list_items=tuple(list_items),
        tables=tuple(tables),
        links=tuple(links),
        picture_count=picture_count,
    )


def _active_lines(markdown: str) -> list[str | None]:
    lines: list[str | None] = []
    fence_character: str | None = None
    fence_length = 0
    for line in markdown.splitlines():
        match = FENCE.match(line)
        if fence_character is None:
            if match is None:
                lines.append(line)
                continue
            marker = match.group("marker")
            fence_character = marker[0]
            fence_length = len(marker)
            lines.append(None)
            continue

        lines.append(None)
        stripped = line.strip(" \t")
        if (
            len(stripped) >= fence_length
            and stripped
            and all(character == fence_character for character in stripped)
        ):
            fence_character = None
            fence_length = 0
    return lines


def _find_unescaped(text: str, character: str, start: int) -> int | None:
    escaped = False
    for index in range(start, len(text)):
        current = text[index]
        if escaped:
            escaped = False
        elif current == "\\":
            escaped = True
        elif current == character:
            return index
    return None


def _is_escaped(text: str, index: int) -> bool:
    backslashes = 0
    cursor = index - 1
    while cursor >= 0 and text[cursor] == "\\":
        backslashes += 1
        cursor -= 1
    return backslashes % 2 == 1


def _find_label_end(text: str, start: int) -> int | None:
    depth = 1
    cursor = start
    while cursor < len(text):
        if _is_escaped(text, cursor):
            cursor += 1
            continue
        if text[cursor] == "[":
            depth += 1
        elif text[cursor] == "]":
            depth -= 1
            if depth == 0:
                return cursor
        cursor += 1
    return None


def _find_code_span_end(text: str, start: int) -> tuple[int, int] | None:
    run = len(text[start:]) - len(text[start:].lstrip("`"))
    cursor = start + run
    while cursor < len(text):
        if text[cursor] != "`" or _is_escaped(text, cursor):
            cursor += 1
            continue
        closing_run = len(text[cursor:]) - len(text[cursor:].lstrip("`"))
        if closing_run == run:
            return cursor, run
        cursor += closing_run
    return None


def _destination(content: str) -> str:
    value = content.strip()
    if value.startswith("<"):
        end = _find_unescaped(value, ">", 1)
        if end is not None:
            return ESCAPED_MARKDOWN.sub(r"\1", value[1:end])

    # Docling writes referenced local paths with literal spaces rather than the
    # angle brackets CommonMark normally requires.  It does not emit optional
    # link titles, so the complete balanced-parenthesis content is the target.
    return ESCAPED_MARKDOWN.sub(r"\1", value)


def _inline_links(text: str) -> tuple[tuple[int, int, bool, str, str], ...]:
    links: list[tuple[int, int, bool, str, str]] = []
    index = 0
    while index < len(text):
        if text[index] == "`" and not _is_escaped(text, index):
            closing = _find_code_span_end(text, index)
            if closing is None:
                index += 1
            else:
                index = closing[0] + closing[1]
            continue

        is_image = text.startswith("![", index)
        if not is_image and text[index] != "[":
            index += 1
            continue
        if _is_escaped(text, index):
            index += 1
            continue

        label_start = index + (2 if is_image else 1)
        label_end = _find_label_end(text, label_start)
        if label_end is None or label_end + 1 >= len(text) or text[label_end + 1] != "(":
            index += 1
            continue

        cursor = label_end + 2
        depth = 1
        escaped = False
        while cursor < len(text):
            character = text[cursor]
            if escaped:
                escaped = False
            elif character == "\\":
                escaped = True
            elif character == "(":
                depth += 1
            elif character == ")":
                depth -= 1
                if depth == 0:
                    break
            cursor += 1
        if depth:
            index += 1
            continue

        label = text[label_start:label_end]
        target = _destination(text[label_end + 2 : cursor])
        links.append((index, cursor + 1, is_image, label, target))
        index = cursor + 1
    return tuple(links)


def _is_punctuation(character: str) -> bool:
    return bool(character) and unicodedata.category(character).startswith("P")


def _delimiter_flanking(
    text: str, start: int, length: int, *, underscore: bool
) -> tuple[bool, bool]:
    previous = text[start - 1] if start else ""
    following_index = start + length
    following = text[following_index] if following_index < len(text) else ""
    previous_space = not previous or previous.isspace()
    following_space = not following or following.isspace()
    previous_punctuation = _is_punctuation(previous)
    following_punctuation = _is_punctuation(following)
    left_flanking = not following_space and (
        not following_punctuation or previous_space or previous_punctuation
    )
    right_flanking = not previous_space and (
        not previous_punctuation or following_space or following_punctuation
    )
    if not underscore:
        return left_flanking, right_flanking
    can_open = left_flanking and (not right_flanking or previous_punctuation)
    can_close = right_flanking and (not left_flanking or following_punctuation)
    return can_open, can_close


def _strip_paired_delimiter(text: str, delimiter: str) -> str:
    positions: list[int] = []
    index = 0
    character = delimiter[0]
    length = len(delimiter)
    while index <= len(text) - length:
        if not text.startswith(delimiter, index) or _is_escaped(text, index):
            index += 1
            continue
        before_same = index > 0 and text[index - 1] == character
        after_index = index + length
        after_same = after_index < len(text) and text[after_index] == character
        if before_same or after_same:
            index += 1
            continue
        positions.append(index)
        index += length

    stack: list[int] = []
    removed: set[int] = set()
    underscore = character == "_"
    for position in positions:
        can_open, can_close = _delimiter_flanking(
            text, position, length, underscore=underscore
        )
        if can_close and stack:
            opener = stack.pop()
            removed.update(range(opener, opener + length))
            removed.update(range(position, position + length))
        elif can_open:
            stack.append(position)
    return "".join(
        character for index, character in enumerate(text) if index not in removed
    )


def _strip_emphasis(text: str) -> str:
    result = text
    for delimiter in ("***", "___", "**", "__", "~~", "*", "_"):
        result = _strip_paired_delimiter(result, delimiter)
    return result


def _strip_inline_markup(text: str) -> str:
    pieces: list[str] = []
    plain_start = 0
    index = 0
    while index < len(text):
        if text[index] != "`" or _is_escaped(text, index):
            index += 1
            continue
        closing = _find_code_span_end(text, index)
        if closing is None:
            index += 1
            continue
        closing_start, run = closing
        pieces.append(_strip_emphasis(text[plain_start:index]))
        content = re.sub(r"[\r\n]+", " ", text[index + run : closing_start])
        if content.startswith(" ") and content.endswith(" ") and content.strip():
            content = content[1:-1]
        pieces.append(content)
        index = closing_start + run
        plain_start = index
    pieces.append(_strip_emphasis(text[plain_start:]))
    return "".join(pieces)


def _visible_inline_text(text: str) -> str:
    pieces: list[str] = []
    cursor = 0
    for start, end, is_image, label, _target in _inline_links(text):
        pieces.append(text[cursor:start])
        if not is_image:
            pieces.append(label)
        cursor = end
    pieces.append(text[cursor:])
    visible = "".join(pieces)
    visible = _strip_inline_markup(visible)
    visible = ESCAPED_MARKDOWN.sub(r"\1", visible)
    return _canonical_text(html.unescape(visible))


def _split_table_row(line: str) -> tuple[str, ...]:
    value = line.strip()
    if value.startswith("|"):
        value = value[1:]
    if value.endswith("|") and not value.endswith("\\|"):
        value = value[:-1]

    cells: list[str] = []
    current: list[str] = []
    escaped = False
    for character in value:
        if escaped:
            current.append(character)
            escaped = False
        elif character == "\\":
            current.append(character)
            escaped = True
        elif character == "|":
            cells.append(_visible_inline_text("".join(current)))
            current = []
        else:
            current.append(character)
    cells.append(_visible_inline_text("".join(current)))
    return tuple(cells)


def _is_table_row(line: str | None) -> bool:
    if line is None:
        return False
    stripped = line.strip()
    return stripped.startswith("|") and stripped.endswith("|")


def _is_table_separator(line: str | None) -> bool:
    return _is_table_row(line) and all(
        TABLE_SEPARATOR_CELL.fullmatch(cell.replace(" ", "")) is not None
        for cell in _split_table_row(line or "")
    )


def _parse_tables(lines: list[str | None]) -> tuple[list[TableRecord], set[int]]:
    tables: list[TableRecord] = []
    consumed: set[int] = set()
    index = 0
    while index + 1 < len(lines):
        if not _is_table_row(lines[index]) or not _is_table_separator(lines[index + 1]):
            index += 1
            continue
        rows = [_split_table_row(lines[index] or "")]
        consumed.update((index, index + 1))
        cursor = index + 2
        while cursor < len(lines) and _is_table_row(lines[cursor]):
            rows.append(_split_table_row(lines[cursor] or ""))
            consumed.add(cursor)
            cursor += 1
        tables.append(TableRecord(tuple(rows), line=index + 1))
        index = cursor
    return tables, consumed


def parse_markdown(markdown: str) -> MarkdownStructure:
    """Parse structural facts from Docling's generated Markdown dialect."""
    lines = _active_lines(markdown)
    tables, table_lines = _parse_tables(lines)
    headings: list[HeadingRecord] = []
    list_items: list[ListItemRecord] = []
    links: list[LinkRecord] = []
    images: list[LinkRecord] = []
    list_count = 0
    active_lists: dict[int, bool] = {}
    current_item_index: int | None = None
    current_indent = 0
    hard_break_continuation = False

    for index, line in enumerate(lines):
        if line is None:
            active_lists.clear()
            current_item_index = None
            hard_break_continuation = False
            continue

        for _start, _end, is_image, _label_text, target in _inline_links(line):
            record = LinkRecord(_canonical_target(target), line=index + 1)
            (images if is_image else links).append(record)

        if index in table_lines:
            active_lists.clear()
            current_item_index = None
            hard_break_continuation = False
            continue

        if not line.strip():
            if current_item_index is not None and active_lists:
                hard_break_continuation = False
            continue

        heading_match = HEADING.match(line)
        if heading_match is not None:
            content = re.sub(r"[ \t]+#+[ \t]*$", "", heading_match.group(2))
            headings.append(
                HeadingRecord(
                    len(heading_match.group(1)),
                    _visible_inline_text(content),
                    line=index + 1,
                )
            )
            active_lists.clear()
            current_item_index = None
            hard_break_continuation = False
            continue

        list_match = LIST_ITEM.match(line)
        if list_match is None:
            indentation = len(line[: len(line) - len(line.lstrip(" \t"))].expandtabs(4))
            is_continuation = hard_break_continuation or (
                current_item_index is not None
                and indentation > current_indent
            )
            if current_item_index is not None and active_lists and is_continuation:
                item = list_items[current_item_index]
                continuation = _visible_inline_text(line.strip())
                list_items[current_item_index] = ListItemRecord(
                    item.depth,
                    item.ordered,
                    _canonical_text(f"{item.text} {continuation}"),
                    line=item.line,
                )
                hard_break_continuation = line.endswith("  ")
                continue
            active_lists.clear()
            current_item_index = None
            hard_break_continuation = False
            continue

        indent = len(list_match.group("indent").expandtabs(4))
        depth = indent // 4
        ordered = list_match.group("marker")[0].isdigit()
        for active_depth in tuple(active_lists):
            if active_depth > depth:
                del active_lists[active_depth]
        if depth not in active_lists or active_lists[depth] != ordered:
            list_count += 1
            active_lists[depth] = ordered
        list_items.append(
            ListItemRecord(
                depth,
                ordered,
                _visible_inline_text(list_match.group("text")),
                line=index + 1,
            )
        )
        current_item_index = len(list_items) - 1
        current_indent = indent
        hard_break_continuation = list_match.group("text").endswith("  ")

    return MarkdownStructure(
        headings=tuple(headings),
        list_count=list_count,
        list_items=tuple(list_items),
        tables=tuple(tables),
        links=tuple(links),
        images=tuple(images),
    )


def _location(record: Any, fallback: str) -> str:
    line = getattr(record, "line", None)
    return f"Markdown line {line}" if line is not None else fallback


def _describe(record: Any) -> str:
    if isinstance(record, HeadingRecord):
        return f"level {record.level}: {record.text}"
    if isinstance(record, ListItemRecord):
        kind = "ordered" if record.ordered else "unordered"
        return f"depth {record.depth}, {kind}: {record.text}"
    if isinstance(record, LinkRecord):
        return record.target
    return str(record)


def _compare_ordered(
    expected: tuple[Any, ...],
    actual: tuple[Any, ...],
    *,
    category: Category,
    changed_code: str,
    missing_code: str,
    unexpected_code: str,
    fallback: str,
) -> list[IntegrityIssue]:
    issues: list[IntegrityIssue] = []
    matcher = SequenceMatcher(a=expected, b=actual, autojunk=False)
    for opcode, expected_start, expected_end, actual_start, actual_end in matcher.get_opcodes():
        if opcode == "equal":
            continue
        expected_slice = expected[expected_start:expected_end]
        actual_slice = actual[actual_start:actual_end]
        paired = min(len(expected_slice), len(actual_slice)) if opcode == "replace" else 0
        for offset in range(paired):
            expected_record = expected_slice[offset]
            actual_record = actual_slice[offset]
            issues.append(
                IntegrityIssue(
                    category,
                    changed_code,
                    _describe(expected_record),
                    _describe(actual_record),
                    _location(actual_record, fallback),
                )
            )
        for record in expected_slice[paired:]:
            issues.append(
                IntegrityIssue(
                    category,
                    missing_code,
                    _describe(record),
                    "missing",
                    fallback,
                )
            )
        for record in actual_slice[paired:]:
            issues.append(
                IntegrityIssue(
                    category,
                    unexpected_code,
                    "none",
                    _describe(record),
                    _location(record, fallback),
                )
            )
    return issues


def _count_issues(
    *,
    category: Category,
    expected: int,
    actual: int,
    missing_code: str,
    unexpected_code: str,
    noun: str,
) -> list[IntegrityIssue]:
    if expected == actual:
        return []
    if expected > actual:
        return [
            IntegrityIssue(
                category,
                missing_code,
                str(expected),
                str(actual),
                f"{noun} count",
            )
        ]
    return [
        IntegrityIssue(
            category,
            unexpected_code,
            str(expected),
            str(actual),
            f"{noun} count",
        )
    ]


def _compare_tables(
    expected: tuple[TableRecord, ...], actual: tuple[TableRecord, ...]
) -> list[IntegrityIssue]:
    issues: list[IntegrityIssue] = []
    matcher = SequenceMatcher(a=expected, b=actual, autojunk=False)
    for opcode, expected_start, expected_end, actual_start, actual_end in matcher.get_opcodes():
        if opcode == "equal":
            continue
        expected_slice = expected[expected_start:expected_end]
        actual_slice = actual[actual_start:actual_end]
        paired = min(len(expected_slice), len(actual_slice)) if opcode == "replace" else 0
        for offset in range(paired):
            expected_table = expected_slice[offset]
            actual_table = actual_slice[offset]
            table_number = expected_start + offset + 1
            expected_rows = expected_table.rows
            actual_rows = actual_table.rows
            if tuple(map(len, expected_rows)) != tuple(map(len, actual_rows)):
                issues.append(
                    IntegrityIssue(
                        "table",
                        "changed_table_shape",
                        str(tuple(map(len, expected_rows))),
                        str(tuple(map(len, actual_rows))),
                        f"table {table_number}",
                    )
                )
            max_rows = max(len(expected_rows), len(actual_rows))
            for row_index in range(max_rows):
                expected_row = expected_rows[row_index] if row_index < len(expected_rows) else ()
                actual_row = actual_rows[row_index] if row_index < len(actual_rows) else ()
                max_columns = max(len(expected_row), len(actual_row))
                for column_index in range(max_columns):
                    expected_cell = (
                        expected_row[column_index]
                        if column_index < len(expected_row)
                        else "missing"
                    )
                    actual_cell = (
                        actual_row[column_index]
                        if column_index < len(actual_row)
                        else "missing"
                    )
                    if expected_cell != actual_cell:
                        issues.append(
                            IntegrityIssue(
                                "table",
                                "changed_table_cell",
                                expected_cell,
                                actual_cell,
                                (
                                    f"table {table_number}, row {row_index + 1}, "
                                    f"column {column_index + 1}"
                                ),
                            )
                        )
        for offset, table in enumerate(expected_slice[paired:], start=expected_start + paired):
            issues.append(
                IntegrityIssue(
                    "table",
                    "missing_table",
                    f"table {offset + 1} with {sum(map(len, table.rows))} cells",
                    "missing",
                    f"table {offset + 1}",
                )
            )
        for offset, table in enumerate(actual_slice[paired:], start=actual_start + paired):
            issues.append(
                IntegrityIssue(
                    "table",
                    "unexpected_table",
                    "none",
                    f"table with {sum(map(len, table.rows))} cells",
                    _location(table, f"table {offset + 1}"),
                )
            )
    return issues


def _target_kind(target: str) -> str:
    if target.startswith("#"):
        return "anchor"
    if PureWindowsPath(target).is_absolute():
        return "local"
    scheme = urlsplit(target).scheme.casefold()
    if scheme in EXTERNAL_SCHEMES:
        return "external"
    if scheme and scheme != "file":
        return "unsupported"
    return "local"


def _long_path(path: Path) -> Path:
    if os.name != "nt":
        return path
    value = str(path)
    if not path.is_absolute() or value.startswith("\\\\?\\"):
        return path
    if value.startswith("\\\\"):
        return Path("\\\\?\\UNC\\" + value.lstrip("\\"))
    return Path("\\\\?\\" + value)


def _normal_path(path: Path) -> Path:
    """Remove a Windows extended-length prefix for comparisons and reports."""
    value = str(path)
    if value.startswith("\\\\?\\UNC\\"):
        return Path("\\\\" + value[len("\\\\?\\UNC\\") :])
    if value.startswith("\\\\?\\"):
        return Path(value[len("\\\\?\\") :])
    return path


def _resolve_local_target(
    target: str, *, markdown_path: Path, output_root: Path
) -> tuple[Path | None, str | None]:
    normalized = target.strip().replace("\\", "/")
    if normalized.casefold().startswith("file:"):
        path_text = unquote(urlsplit(normalized).path)
    else:
        split = urlsplit(normalized)
        path_text = unquote(split.path)

    if not path_text or "\x00" in path_text:
        return None, "invalid_local_target"
    if path_text.startswith("/") or PureWindowsPath(path_text).is_absolute():
        return None, "outside_output_root"

    root = _normal_path(_long_path(output_root).resolve())
    candidate = _normal_path(
        _long_path(markdown_path.parent / Path(path_text)).resolve(strict=False)
    )
    try:
        candidate.relative_to(root)
    except ValueError:
        return None, "outside_output_root"
    return candidate, None


def _inspect_local_link(path: Path) -> str | None:
    io_path = _long_path(path)
    try:
        if not io_path.exists():
            return "missing_local_target"
        if not io_path.is_file():
            return "local_target_not_file"
        with io_path.open("rb") as handle:
            handle.read(1)
    except OSError:
        return "unreadable_local_target"
    return None


class _InvalidImageError(Exception):
    pass


def _decode_image(path: Path) -> tuple[str, int, int]:
    from PIL import Image, UnidentifiedImageError

    try:
        with Image.open(_long_path(path)) as image:
            image_format = image.format
            width, height = image.size
            image.verify()
        with Image.open(_long_path(path)) as image:
            image.load()
    except PermissionError:
        raise
    except (UnidentifiedImageError, OSError, SyntaxError, ValueError) as exc:
        raise _InvalidImageError(str(exc)) from exc
    if not image_format or width <= 0 or height <= 0:
        raise _InvalidImageError("image has no format or positive dimensions")
    return image_format, int(width), int(height)


def _issue_for_target(
    code: str, target: str, line: int | None, *, image: bool
) -> IntegrityIssue:
    category: Category = "artifact" if image else "link"
    return IntegrityIssue(
        category,
        code,
        "valid local image" if image else "readable local file",
        target,
        f"Markdown line {line}" if line is not None else target,
    )


def _resolve_artifact_entry(path: Path) -> Path:
    return _normal_path(path.resolve(strict=False))


def _check_local_links(
    links: tuple[LinkRecord, ...], *, markdown_path: Path, output_root: Path
) -> list[IntegrityIssue]:
    issues: list[IntegrityIssue] = []
    for link in links:
        kind = _target_kind(link.target)
        if kind in ("external", "anchor"):
            continue
        if kind == "unsupported":
            issues.append(
                _issue_for_target(
                    "unsupported_link_scheme", link.target, link.line, image=False
                )
            )
            continue
        path, error = _resolve_local_target(
            link.target, markdown_path=markdown_path, output_root=output_root
        )
        if error is not None:
            issues.append(_issue_for_target(error, link.target, link.line, image=False))
            continue
        assert path is not None
        if error := _inspect_local_link(path):
            issues.append(_issue_for_target(error, link.target, link.line, image=False))
    return issues


def _check_images(
    images: tuple[LinkRecord, ...],
    *,
    markdown_path: Path,
    output_root: Path,
    artifacts_dir: Path,
) -> tuple[list[IntegrityIssue], list[ArtifactCheck]]:
    issues: list[IntegrityIssue] = []
    checks: list[ArtifactCheck] = []
    referenced_paths: list[Path] = []

    for image in images:
        kind = _target_kind(image.target)
        if kind == "external":
            issues.append(
                _issue_for_target(
                    "external_image", image.target, image.line, image=True
                )
            )
            checks.append(ArtifactCheck(image.target, "external"))
            continue
        if kind in ("anchor", "unsupported"):
            issues.append(
                _issue_for_target(
                    "invalid_image_target", image.target, image.line, image=True
                )
            )
            checks.append(ArtifactCheck(image.target, "invalid_target"))
            continue

        path, error = _resolve_local_target(
            image.target, markdown_path=markdown_path, output_root=output_root
        )
        if error is not None:
            issues.append(_issue_for_target(error, image.target, image.line, image=True))
            checks.append(ArtifactCheck(image.target, error))
            continue
        assert path is not None
        referenced_paths.append(path)
        io_path = _long_path(path)
        try:
            if not io_path.exists():
                issues.append(
                    _issue_for_target(
                        "missing_image", image.target, image.line, image=True
                    )
                )
                checks.append(ArtifactCheck(image.target, "missing"))
                continue
            if not io_path.is_file():
                issues.append(
                    _issue_for_target(
                        "image_target_not_file",
                        image.target,
                        image.line,
                        image=True,
                    )
                )
                checks.append(ArtifactCheck(image.target, "not_file"))
                continue
            size = io_path.stat().st_size
        except OSError:
            issues.append(
                _issue_for_target(
                    "unreadable_image", image.target, image.line, image=True
                )
            )
            checks.append(ArtifactCheck(image.target, "unreadable"))
            continue
        if size == 0:
            issues.append(_issue_for_target("empty_image", image.target, image.line, image=True))
            checks.append(ArtifactCheck(image.target, "empty", size_bytes=0))
            continue
        try:
            image_format, width, height = _decode_image(path)
        except PermissionError:
            issues.append(
                _issue_for_target(
                    "unreadable_image", image.target, image.line, image=True
                )
            )
            checks.append(ArtifactCheck(image.target, "unreadable", size_bytes=size))
            continue
        except _InvalidImageError:
            issues.append(_issue_for_target("invalid_image", image.target, image.line, image=True))
            checks.append(ArtifactCheck(image.target, "invalid", size_bytes=size))
            continue
        checks.append(
            ArtifactCheck(
                image.target,
                "valid",
                size_bytes=size,
                format=image_format,
                width=width,
                height=height,
            )
        )

    root = _normal_path(_long_path(output_root).resolve())
    occurrences: dict[Path, int] = {}
    for path in referenced_paths:
        occurrences[path] = occurrences.get(path, 0) + 1
    for path, count in occurrences.items():
        if count > 1:
            target = path.relative_to(root).as_posix()
            issues.append(
                IntegrityIssue(
                    "artifact",
                    "ambiguous_duplicate_image",
                    "one image link per generated artifact",
                    f"{count} links to {target}",
                    target,
                )
            )

    artifact_root = _normal_path(_long_path(artifacts_dir).resolve(strict=False))
    try:
        artifact_root.relative_to(root)
    except ValueError:
        issues.append(
            IntegrityIssue(
                "artifact",
                "artifact_directory_outside_root",
                str(root),
                str(artifact_root),
                "artifact directory",
            )
        )
        return issues, checks

    referenced = set(referenced_paths)
    try:
        io_artifacts_dir = _long_path(artifacts_dir)
        artifact_entries: Iterable[Path] = (
            sorted(io_artifacts_dir.rglob("*"), key=lambda path: str(path))
            if io_artifacts_dir.exists()
            else ()
        )
        for io_artifact in artifact_entries:
            artifact = _normal_path(io_artifact)
            target = artifact.relative_to(root).as_posix()
            try:
                resolved = _resolve_artifact_entry(io_artifact)
            except (OSError, RuntimeError) as exc:
                issues.append(
                    IntegrityIssue(
                        "artifact",
                        "artifact_scan_error",
                        "resolvable artifact target",
                        str(exc),
                        target,
                    )
                )
                checks.append(ArtifactCheck(target, "unreadable"))
                continue
            try:
                resolved.relative_to(root)
            except ValueError:
                issues.append(
                    IntegrityIssue(
                        "artifact",
                        "artifact_target_outside_root",
                        str(root),
                        str(resolved),
                        target,
                    )
                )
                checks.append(ArtifactCheck(target, "outside_output_root"))
                continue
            if not io_artifact.is_file():
                continue
            if resolved in referenced:
                continue
            try:
                size = io_artifact.stat().st_size
            except OSError:
                size = None
            issues.append(
                IntegrityIssue(
                    "artifact",
                    "stale_artifact",
                    "artifact referenced by a Markdown image",
                    target,
                    target,
                )
            )
            checks.append(ArtifactCheck(target, "stale", size_bytes=size))
    except OSError as exc:
        issues.append(
            IntegrityIssue(
                "artifact",
                "artifact_scan_error",
                "readable artifact directory",
                str(exc),
                str(artifacts_dir),
            )
        )
    return issues, checks


def evaluate(
    document: Any,
    markdown: str,
    *,
    markdown_path: Path,
    output_root: Path,
    artifacts_dir: Path,
) -> StructuralIntegrityReport:
    """Compare document structure with Markdown and validate referenced files."""
    expected = inspect_document(document)
    actual = parse_markdown(markdown)
    issues: list[IntegrityIssue] = []

    issues.extend(
        _compare_ordered(
            expected.headings,
            actual.headings,
            category="heading",
            changed_code="changed_heading",
            missing_code="missing_heading",
            unexpected_code="unexpected_heading",
            fallback="document headings",
        )
    )
    issues.extend(
        _count_issues(
            category="list",
            expected=expected.list_count,
            actual=actual.list_count,
            missing_code="missing_list",
            unexpected_code="unexpected_list",
            noun="list",
        )
    )
    issues.extend(
        _compare_ordered(
            expected.list_items,
            actual.list_items,
            category="list",
            changed_code="changed_list_item",
            missing_code="missing_list_item",
            unexpected_code="unexpected_list_item",
            fallback="document lists",
        )
    )
    issues.extend(_compare_tables(expected.tables, actual.tables))
    issues.extend(
        _compare_ordered(
            expected.links,
            actual.links,
            category="link",
            changed_code="changed_link",
            missing_code="missing_link",
            unexpected_code="unexpected_link",
            fallback="document links",
        )
    )
    issues.extend(
        _count_issues(
            category="artifact",
            expected=expected.picture_count,
            actual=len(actual.images),
            missing_code="missing_image_link",
            unexpected_code="unexpected_image_link",
            noun="image link",
        )
    )
    issues.extend(
        _check_local_links(
            actual.links,
            markdown_path=markdown_path,
            output_root=output_root,
        )
    )
    artifact_issues, artifacts = _check_images(
        actual.images,
        markdown_path=markdown_path,
        output_root=output_root,
        artifacts_dir=artifacts_dir,
    )
    issues.extend(artifact_issues)

    return StructuralIntegrityReport(
        headings=CountComparison(len(expected.headings), len(actual.headings)),
        lists=CountComparison(expected.list_count, actual.list_count),
        list_items=CountComparison(len(expected.list_items), len(actual.list_items)),
        tables=CountComparison(len(expected.tables), len(actual.tables)),
        table_cells=CountComparison(
            sum(sum(len(row) for row in table.rows) for table in expected.tables),
            sum(sum(len(row) for row in table.rows) for table in actual.tables),
        ),
        links=CountComparison(len(expected.links), len(actual.links)),
        images=CountComparison(expected.picture_count, len(actual.images)),
        issues=tuple(issues),
        artifacts=tuple(artifacts),
    )
