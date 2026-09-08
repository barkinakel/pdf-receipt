"""Fact-based assertions shared by fast and live fixture tests."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

LINK = re.compile(r"(?<!!)\[[^\]]*\]\(([^)]+)\)")
IMAGE_LINK = re.compile(r"!\[[^\]]*\]\(([^)]+)\)")
LIST_ITEM = re.compile(r"^\s*(?:[-+*]|\d+[.)])\s+(.+?)\s*$")


@dataclass(frozen=True)
class FixtureCase:
    name: str
    pdf_path: Path
    facts_path: Path
    features: tuple[str, ...]
    facts: tuple[dict[str, Any], ...]


def load_fixture_cases(root: Path) -> tuple[FixtureCase, ...]:
    cases: list[FixtureCase] = []
    for facts_path in sorted(root.glob("*.facts.json")):
        payload = json.loads(facts_path.read_text(encoding="utf-8"))
        name = payload["name"]
        pdf_path = root / payload["pdf"]
        if not pdf_path.is_file():
            raise AssertionError(f"{name}: fixture PDF is missing: {pdf_path.name}")
        cases.append(
            FixtureCase(
                name=name,
                pdf_path=pdf_path,
                facts_path=facts_path,
                features=tuple(payload["features"]),
                facts=tuple(payload["facts"]),
            )
        )
    if not cases:
        raise AssertionError(f"fixture corpus is empty: {root}")
    return tuple(cases)


def _fail(case: FixtureCase, fact: dict[str, Any], detail: str) -> None:
    fact_id = fact.get("id", "<missing-id>")
    raise AssertionError(f"{case.name}: fact {fact_id!r} failed: {detail}")


def _assert_ordered(case: FixtureCase, fact: dict[str, Any], markdown: str) -> None:
    cursor = 0
    for phrase in fact["phrases"]:
        found = markdown.find(phrase, cursor)
        if found < 0:
            _fail(case, fact, f"ordered phrase {phrase!r} was absent or out of order")
        cursor = found + len(phrase)


def _markdown_rows(markdown: str) -> list[list[str]]:
    rows: list[list[str]] = []
    for line in markdown.splitlines():
        if line.lstrip().startswith("|") and line.rstrip().endswith("|"):
            rows.append([cell.strip() for cell in line.strip().strip("|").split("|")])
    return rows


def _markdown_list_items(markdown: str) -> list[str]:
    return [
        match.group(1)
        for line in markdown.splitlines()
        if (match := LIST_ITEM.match(line)) is not None
    ]


def _assert_image_links(
    case: FixtureCase,
    fact: dict[str, Any],
    markdown: str,
    markdown_path: Path | None,
) -> None:
    targets = IMAGE_LINK.findall(markdown)
    minimum = fact.get("minimum", 1)
    if len(targets) < minimum:
        _fail(
            case,
            fact,
            f"expected at least {minimum} image link(s), found {len(targets)}",
        )
    if markdown_path is None:
        _fail(case, fact, "artifact validation needs the generated Markdown path")
    for target in targets:
        normalized = target.replace("\\", "/")
        artifact = markdown_path.parent / Path(normalized)
        if not artifact.is_file() or artifact.stat().st_size == 0:
            _fail(case, fact, f"image target is missing or empty: {target!r}")
        try:
            from PIL import Image

            with Image.open(artifact) as image:
                width, height = image.size
                image.verify()
            with Image.open(artifact) as image:
                image.load()
        except (OSError, SyntaxError, ValueError) as exc:
            _fail(case, fact, f"image target cannot be decoded: {target!r}: {exc}")
        if width <= 0 or height <= 0:
            _fail(case, fact, f"image target has invalid dimensions: {target!r}")


def _assert_fact(
    case: FixtureCase,
    fact: dict[str, Any],
    markdown: str,
    markdown_path: Path | None = None,
) -> None:
    fact_type = fact["type"]
    if fact_type == "contains":
        if fact["text"] not in markdown:
            _fail(case, fact, f"required text was absent: {fact['text']!r}")
    elif fact_type == "excludes":
        if fact["text"] in markdown:
            _fail(case, fact, f"forbidden text was present: {fact['text']!r}")
    elif fact_type == "one_of":
        if not any(text in markdown for text in fact["texts"]):
            _fail(
                case,
                fact,
                f"none of the allowed texts were present: {fact['texts']!r}",
            )
    elif fact_type == "ordered":
        _assert_ordered(case, fact, markdown)
    elif fact_type == "occurrences":
        actual = markdown.count(fact["text"])
        if actual != fact["count"]:
            _fail(
                case,
                fact,
                f"expected {fact['count']} occurrence(s) of {fact['text']!r}, found {actual}",
            )
    elif fact_type == "heading":
        expected = f"{'#' * fact['level']} {fact['text']}"
        if expected not in markdown.splitlines():
            _fail(case, fact, f"heading was absent: {expected!r}")
    elif fact_type == "list_items":
        actual = _markdown_list_items(markdown)
        cursor = 0
        for expected in fact["items"]:
            try:
                cursor = actual.index(expected, cursor) + 1
            except ValueError:
                _fail(
                    case,
                    fact,
                    f"Markdown list item was absent or out of order: {expected!r}",
                )
    elif fact_type == "table_cells":
        cells = fact["cells"]
        if not any(all(cell in row for cell in cells) for row in _markdown_rows(markdown)):
            _fail(case, fact, f"no table row contained cells {cells!r}")
    elif fact_type == "table_row_occurrences":
        expected_count = fact["count"]
        if not any(
            sum(cell.count(fact["text"]) for cell in row) == expected_count
            for row in _markdown_rows(markdown)
        ):
            _fail(
                case,
                fact,
                f"no table row contained {expected_count} occurrence(s) of {fact['text']!r}",
            )
    elif fact_type == "link_target":
        targets = LINK.findall(markdown)
        if fact["target"] not in targets:
            _fail(case, fact, f"link target was absent: {fact['target']!r}")
    elif fact_type == "no_link_target":
        targets = LINK.findall(markdown)
        if fact["target"] in targets:
            _fail(
                case,
                fact,
                "link target unexpectedly became a Markdown link: "
                f"{fact['target']!r}",
            )
    elif fact_type == "valid_image_links":
        _assert_image_links(case, fact, markdown, markdown_path)
    elif fact_type == "known_limitation":
        failures: list[str] = []
        for outcome in fact["accepted_outcomes"]:
            try:
                for observation in outcome["facts"]:
                    _assert_fact(case, observation, markdown, markdown_path)
                return
            except AssertionError as exc:
                failures.append(f"{outcome['name']}: {exc}")
        _fail(case, fact, "no accepted outcome matched; " + " | ".join(failures))
    else:
        _fail(case, fact, f"unknown fact type: {fact_type!r}")


def assert_markdown_facts(
    case: FixtureCase,
    markdown: str,
    *,
    markdown_path: Path | None = None,
) -> None:
    """Assert every explicit fact and identify both fixture and fact on failure."""
    for fact in case.facts:
        _assert_fact(case, fact, markdown, markdown_path)
