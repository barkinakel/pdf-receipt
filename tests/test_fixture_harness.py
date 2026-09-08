from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from PIL import Image

from pdftomd import quality_report as qr
from tests.fixture_harness import FixtureCase, assert_markdown_facts, load_fixture_cases

FIXTURES = Path(__file__).resolve().parent / "fixtures"

REQUIRED_FEATURES = {
    "turkish_dotted_dotless_i",
    "unicode_ligatures",
    "line_end_hyphenation",
    "hyphenated_compound",
    "repeated_same_page",
    "repeated_across_pages",
    "short_tokens",
    "numeric_table_cells",
    "headings",
    "lists",
    "links",
    "tables",
    "images",
    "multi_column_order",
    "scanned_page",
    "decorative_drop_cap",
}


class FixtureCorpusTests(unittest.TestCase):
    def test_checked_in_corpus_covers_every_milestone_a_feature(self) -> None:
        cases = load_fixture_cases(FIXTURES)

        covered = {feature for case in cases for feature in case.features}
        self.assertTrue(REQUIRED_FEATURES <= covered, REQUIRED_FEATURES - covered)

    def test_every_fact_has_a_unique_descriptive_id(self) -> None:
        for case in load_fixture_cases(FIXTURES):
            with self.subTest(fixture=case.name):
                ids = [fact.get("id") for fact in case.facts]
                self.assertTrue(all(ids), f"{case.name}: every fact needs an id")
                self.assertEqual(len(ids), len(set(ids)), f"{case.name}: duplicate fact id")

    def test_structure_fixture_uses_structural_or_explicit_limitation_facts(self) -> None:
        case = next(
            case for case in load_fixture_cases(FIXTURES)
            if case.name == "structure-layout"
        )
        facts = {fact["id"]: fact for fact in case.facts}

        self.assertEqual(facts["list-items"]["type"], "list_items")
        self.assertIn(
            facts["source-link"]["type"],
            {"link_target", "known_limitation"},
        )
        self.assertEqual(facts["drop-cap"]["type"], "known_limitation")

        link_outcomes = facts["source-link"]["accepted_outcomes"]
        link_types = {
            observation["type"]
            for outcome in link_outcomes
            for observation in outcome["facts"]
        }
        self.assertIn("link_target", link_types)
        self.assertIn("no_link_target", link_types)
        self.assertIn("table_row_occurrences", link_types)

        drop_cap_outcomes = facts["drop-cap"]["accepted_outcomes"]
        accepted_text = {
            observation.get("text")
            for outcome in drop_cap_outcomes
            for observation in outcome["facts"]
        }
        self.assertIn(
            "This chapter begins with a decorative drop cap",
            accepted_text,
        )
        self.assertIn(
            "his chapter begins with a decorative drop cap",
            accepted_text,
        )

    def test_multicolumn_content_stream_order_is_not_expected_spatial_order(self) -> None:
        content = (FIXTURES / "structure_layout.pdf").read_bytes()

        stream_order = [
            content.index(phrase)
            for phrase in (
                b"Right column third",
                b"Left column first",
                b"Right column fourth",
                b"Left column second",
            )
        ]
        self.assertEqual(stream_order, sorted(stream_order))

    def test_every_pdf_text_token_traces_to_raw_text_and_a_page(self) -> None:
        token_count = 0
        for case in load_fixture_cases(FIXTURES):
            pdf_text = qr.read_pdf_text(case.pdf_path)
            for token in qr.tokenize_pdf_pages(pdf_text):
                with self.subTest(fixture=case.name, raw=token.raw_text):
                    self.assertIsNotNone(token.page_no)
                    raw_page = pdf_text.pages[token.page_no - 1]
                    self.assertEqual(
                        raw_page[token.source_span.start : token.source_span.end],
                        token.raw_text,
                    )
                token_count += 1
        self.assertGreater(token_count, 0)

    def test_failure_names_the_fixture_and_failed_fact(self) -> None:
        case = FixtureCase(
            name="diagnostic-fixture",
            pdf_path=Path("diagnostic.pdf"),
            facts_path=Path("diagnostic.facts.json"),
            features=(),
            facts=(
                {"id": "required-alpha", "type": "contains", "text": "alpha"},
            ),
        )

        with self.assertRaisesRegex(
            AssertionError,
            "diagnostic-fixture: fact 'required-alpha' failed",
        ):
            assert_markdown_facts(case, "beta")

    def test_fact_types_check_content_structure_links_and_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            artifact = root / "sample_artifacts" / "image.png"
            artifact.parent.mkdir()
            Image.new("RGB", (2, 3), "white").save(artifact, format="PNG")
            markdown_path = root / "sample.md"
            markdown = "\n".join(
                (
                    "# Fixture Heading",
                    "alpha first then omega",
                    "- retained list item",
                    "[project](https://example.com/fixture)",
                    "| label | 7 | 42 |",
                    "|---|---:|---:|",
                    "![diagram](sample_artifacts/image.png)",
                )
            )
            case = FixtureCase(
                name="all-facts",
                pdf_path=Path("all-facts.pdf"),
                facts_path=Path("all-facts.facts.json"),
                features=(),
                facts=(
                    {"id": "text", "type": "contains", "text": "alpha"},
                    {"id": "forbidden", "type": "excludes", "text": "beta"},
                    {"id": "alternative", "type": "one_of", "texts": ["alpha", "beta"]},
                    {"id": "order", "type": "ordered", "phrases": ["alpha", "omega"]},
                    {"id": "count", "type": "occurrences", "text": "omega", "count": 1},
                    {
                        "id": "heading",
                        "type": "heading",
                        "level": 1,
                        "text": "Fixture Heading",
                    },
                    {
                        "id": "list",
                        "type": "list_items",
                        "items": ["retained list item"],
                    },
                    {"id": "cells", "type": "table_cells", "cells": ["7", "42"]},
                    {
                        "id": "link",
                        "type": "link_target",
                        "target": "https://example.com/fixture",
                    },
                    {"id": "image", "type": "valid_image_links", "minimum": 1},
                ),
            )

            assert_markdown_facts(case, markdown, markdown_path=markdown_path)

    def test_valid_image_fact_rejects_non_image_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            artifact = root / "sample_artifacts" / "image.png"
            artifact.parent.mkdir()
            artifact.write_bytes(b"not an image")
            markdown_path = root / "sample.md"
            case = FixtureCase(
                name="invalid-image",
                pdf_path=Path("invalid-image.pdf"),
                facts_path=Path("invalid-image.facts.json"),
                features=(),
                facts=(
                    {"id": "image", "type": "valid_image_links", "minimum": 1},
                ),
            )

            with self.assertRaisesRegex(AssertionError, "cannot be decoded"):
                assert_markdown_facts(
                    case,
                    "![Image](sample_artifacts/image.png)",
                    markdown_path=markdown_path,
                )


if __name__ == "__main__":
    unittest.main()
