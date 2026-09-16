"""CommonMark evidence for endpoint comparison, with original character spans.

Parser rules decide syntax. This adapter records their consumed source ranges;
it does not render Markdown or infer offsets from rendered HTML. Conversion's
Docling-specific tokenizer is deliberately unchanged.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from html import unescape
from html.parser import HTMLParser
import re
from typing import Any

from . import quality_report as qr


@dataclass(frozen=True)
class ImageReference:
    target: str
    line: int


@dataclass(frozen=True)
class MarkdownEvidence:
    tokens: tuple[qr.Token, ...]
    images: tuple[ImageReference, ...]


def _normalized_source(text: str) -> tuple[str, list[qr.SourceSpan]]:
    chars, spans = [], []
    index = 0
    while index < len(text):
        stop = index + (2 if text[index:index + 2] == "\r\n" else 1)
        chars.append("\n" if text[index] == "\r" else
                     "\ufffd" if text[index] == "\0" else text[index])
        spans.append(qr.SourceSpan(index, stop))
        index = stop
    return "".join(chars), spans


class _HTMLText(HTMLParser):
    """Extract text and img targets; never execute HTML or follow URLs."""
    def __init__(self, text: str) -> None:
        super().__init__(convert_charrefs=False)
        self.text = text
        self.lines = [0] + [m.end() for m in re.finditer("\n", text)]
        self.chars = [""] * len(text)
        self.origins = [qr.SourceSpan(i, i + 1) for i in range(len(text))]
        self.images: list[tuple[str, int]] = []
        self.hidden: list[str] = []

    def source_offset(self) -> int:
        line, column = self.getpos()
        return self.lines[line - 1] + column

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"script", "style", "template", "head"}:
            self.hidden.append(tag)
        if self.hidden:
            return
        if tag == "img":
            self.images.append((dict(attrs).get("src") or "", self.source_offset()))
        if tag in {"br", "p", "div", "tr", "td", "th", "li"}:
            self.chars[self.source_offset()] = "\n"

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.handle_starttag(tag, attrs)
        self.handle_endtag(tag)

    def handle_endtag(self, tag: str) -> None:
        if self.hidden and tag == self.hidden[-1]:
            self.hidden.pop()
        if not self.hidden and tag in {"p", "div", "tr", "td", "th", "li"}:
            self.chars[self.source_offset()] = "\n"

    def handle_data(self, data: str) -> None:
        if not self.hidden:
            start = self.source_offset()
            self.chars[start:start + len(data)] = list(data)

    def entity(self, spelling: str) -> None:
        if not self.hidden:
            start = self.source_offset()
            actual = self.text[start:start + len(spelling)]
            self.chars[start] = unescape(actual)
            self.origins[start] = qr.SourceSpan(start, start + len(actual))

    def handle_entityref(self, name: str) -> None:
        start = self.source_offset() + len(name) + 1
        self.entity("&" + name + (";" if self.text[start:start + 1] == ";" else ""))

    def handle_charref(self, name: str) -> None:
        start = self.source_offset() + len(name) + 2
        self.entity("&#" + name + (";" if self.text[start:start + 1] == ";" else ""))


def _block_maps(parser: Any) -> None:
    """Capture ranges before list/blockquote rules restore their indentation."""
    def wrap(name: str, rule: Any) -> Any:
        def mapped(state: Any, start: int, end: int, silent: bool) -> bool:
            count = len(state.tokens)
            ok = rule(state, start, end, silent)
            if not ok or silent:
                return ok
            cursors: dict[int, int] = {}
            for token in state.tokens[count:]:
                if token.type not in {"inline", "fence", "code_block", "html_block"} or "offsets" in token.meta:
                    continue
                if not token.content:
                    token.meta["offsets"] = []
                    continue
                first, last = token.map
                if token.type == "fence":
                    first += 1
                offsets = []
                line = first
                for piece in token.content.splitlines(keepends=True):
                    body = piece.rstrip("\n")
                    found = False
                    while line < last:
                        shift = 0 if token.type == "html_block" else state.tShift[line]
                        begin = max(state.bMarks[line] + shift, cursors.get(line, 0))
                        # Code indentation may include a partially expanded tab.
                        candidate = state.src[begin:state.eMarks[line]]
                        needle = body
                        leading = len(needle) - len(needle.lstrip(" \t"))
                        if token.type in {"fence", "code_block"}:
                            needle = needle[leading:]
                        candidate_offsets = list(range(begin, state.eMarks[line]))
                        if name == "table":
                            retained = [i for i in range(len(candidate))
                                        if not (candidate[i] == "\\" and candidate[i:i + 2] == "\\|")]
                            candidate = "".join(candidate[i] for i in retained)
                            candidate_offsets = [candidate_offsets[i] for i in retained]
                        pos = candidate.find(needle)
                        if pos >= 0:
                            absolute = candidate_offsets[pos] if pos < len(candidate_offsets) else state.eMarks[line]
                            offsets.extend([absolute] * leading if token.type in {"fence", "code_block"} else [])
                            offsets.extend(candidate_offsets[pos:pos + len(needle)])
                            cursors[line] = candidate_offsets[pos + len(needle) - 1] + 1 if needle else absolute
                            if piece.endswith("\n"):
                                offsets.append(state.eMarks[line])
                            found = True
                            break
                        line += 1
                    if not found:
                        raise ValueError("Cannot preserve Markdown source positions for this block")
                    if piece.endswith("\n"):
                        line += 1
                if len(offsets) != len(token.content):
                    raise ValueError("Markdown source mapping length mismatch")
                token.meta["offsets"] = offsets
            return ok
        return mapped
    names = parser.block.ruler.get_active_rules()
    rules = parser.block.ruler.getRules("")
    # Ruler.at replaces options too: retain the preset's interruption chains.
    chains = {name: parser.block.ruler.getRules(name)
              for name in ("paragraph", "reference", "blockquote", "list")}
    for name, rule in zip(names, rules):
        parser.block.ruler.at(name, wrap(name, rule),
                              {"alt": [key for key, members in chains.items() if rule in members]})


def _inline_text(parser: Any, content: str, env: dict[str, Any]) -> tuple[list[str], list[qr.SourceSpan], list[tuple[str, int]]]:
    chars = list(content)
    origins = [qr.SourceSpan(i, i + 1) for i in range(len(content))]
    images: list[tuple[str, int]] = []
    delimiters: list[tuple[int, Any]] = []
    hidden_start: int | None = None
    hidden_tags: list[str] = []
    hidden_ranges: list[tuple[int, int]] = []

    def clear(start: int, end: int) -> None:
        chars[start:end] = [""] * (end - start)

    def wrap(name: str, rule: Any) -> Any:
        def record(state: Any, silent: bool) -> bool:
            nonlocal hidden_start
            start, count = state.pos, len(state.tokens)
            label_end = -1
            active = not silent and state.src is content
            if active and name == "link" and content[start:start + 1] == "[":
                label_end = parser.helpers.parseLinkLabel(state, start, True)
            ok = rule(state, silent)
            if not ok or not active:
                return ok
            stop = state.pos
            added = state.tokens[count:]
            if name == "image":
                image = next((t for t in reversed(added) if t.type == "image"), None)
                if image is not None:
                    clear(start, stop)
                    images.append((image.attrGet("src") or "", start))
            elif name == "link" and label_end >= 0:
                clear(start, start + 1)
                clear(label_end, stop)
            elif name == "html_inline":
                clear(start, stop)
                html = _HTMLText(content[start:stop])
                html.feed(content[start:stop])
                html.close()
                if re.match(r"</?(br|p|div|tr|td|th|li)(?:\s|/?>)", content[start:stop].lower()):
                    chars[start] = "\n"
                images.extend((target, start + offset) for target, offset in html.images)
                spelling = content[start:stop].lower()
                opening = re.match(r"<(script|style|template|head)(?:\s|/?>)", spelling)
                closing = re.match(r"</(script|style|template|head)\s*>", spelling)
                if opening and not spelling.endswith("/>"):
                    if hidden_start is None:
                        hidden_start = start
                    hidden_tags.append(opening.group(1))
                elif closing and hidden_tags and closing.group(1) == hidden_tags[-1]:
                    hidden_tags.pop()
                    if not hidden_tags:
                        clear(hidden_start, stop)
                        hidden_ranges.append((hidden_start, stop))
                        hidden_start = None
            elif name == "autolink":
                clear(start, start + 1)
                clear(stop - 1, stop)
            elif name in {"entity", "escape"}:
                token = next((t for t in reversed(added) if t.type in {"text_special", "hardbreak"}), None)
                if token is not None:
                    clear(start, stop)
                    chars[start] = token.content if token.type != "hardbreak" else "\n"
                    origins[start] = qr.SourceSpan(start, stop)
            elif name == "backticks":
                token = next((t for t in reversed(added) if t.type == "code_inline"), None)
                if token is not None:
                    size = len(token.markup)
                    clear(start, start + size)
                    clear(stop - size, stop)
                    for i in range(start + size, stop - size):
                        if chars[i] == "\n":
                            chars[i] = " "
            elif name == "emphasis":
                markers = added[-(stop - start):]
                delimiters.extend((start + i, token) for i, token in enumerate(markers))
            return ok
        return record

    names = parser.inline.ruler.get_active_rules()
    originals = parser.inline.ruler.getRules("")
    try:
        for name, rule in zip(names, originals):
            parser.inline.ruler.at(name, wrap(name, rule))
        parser.inline.parse(content, parser, env, [])
        for offset, token in delimiters:
            if token.type in {"em_open", "em_close"}:
                clear(offset, offset + 1)
            elif token.type == "strong_open":
                clear(offset - 1, offset + 1)
            elif token.type == "strong_close":
                clear(offset, offset + 2)
        if hidden_start is not None:
            clear(hidden_start, len(content))
            hidden_ranges.append((hidden_start, len(content)))
    finally:
        for name, rule in zip(names, originals):
            parser.inline.ruler.at(name, rule)
    images = [(target, offset) for target, offset in images
              if not any(start <= offset < end for start, end in hidden_ranges)]
    return chars, origins, images


def parse_markdown(text: str, *, case_profile: qr.CaseProfile = "unicode") -> MarkdownEvidence:
    from markdown_it import MarkdownIt

    normalized, raw_spans = _normalized_source(text)
    # Indented code can gain a trailing newline at EOF. It has no raw bytes.
    raw_spans.append(qr.SourceSpan(len(text), len(text)))
    parser = MarkdownIt("commonmark").enable("table")
    # Targets are data, never rendered or fetched. Preserve unsafe/unsupported
    # schemes so the artifact checker can explicitly report them as unchecked.
    parser.validateLink = lambda target: True
    _block_maps(parser)
    parser.core.ruler.disable(["inline", "text_join"])
    env: dict[str, Any] = {}
    blocks = parser.parse(normalized, env)
    tokens: list[qr.Token] = []
    images: list[ImageReference] = []
    for block in blocks:
        if block.type not in {"inline", "fence", "code_block", "html_block"}:
            continue
        content = block.content
        offsets = block.meta["offsets"]
        if not content:
            continue
        if block.type == "inline":
            chars, origins, references = _inline_text(parser, content, env)
        elif block.type == "html_block":
            html = _HTMLText(content)
            html.feed(content)
            html.close()
            chars, origins, references = html.chars, html.origins, html.images
        else:
            chars = list(content)
            origins = [qr.SourceSpan(i, i + 1) for i in range(len(content))]
            references = []
        visible = "".join(chars)
        mapped: list[qr.SourceSpan] = []
        for value, span in zip(chars, origins):
            if value:
                raw = qr.SourceSpan(raw_spans[offsets[span.start]].start,
                                    raw_spans[offsets[span.end - 1]].end)
                mapped.extend([raw] * len(value))
        for token in qr.tokenize(visible, page_no=None, block_id="markdown", case_profile=case_profile):
            def raw_span(span: qr.SourceSpan) -> qr.SourceSpan:
                return qr.SourceSpan(mapped[span.start].start, mapped[span.end - 1].end)
            span = raw_span(token.source_span)
            tokens.append(replace(token, raw_text=text[span.start:span.end], source_span=span,
                                  line_end_hyphen_spans=tuple(raw_span(s) for s in token.line_end_hyphen_spans)))
        for target, offset in references:
            raw_offset = raw_spans[offsets[offset]].start
            line = len(re.findall(r"\r\n|\r|\n", text[:raw_offset])) + 1
            images.append(ImageReference(target, line))
    return MarkdownEvidence(tuple(tokens), tuple(images))
