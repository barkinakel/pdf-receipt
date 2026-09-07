from __future__ import annotations

import unittest
from types import SimpleNamespace

from pdftomd import quality_report as qr


class NormalizationTests(unittest.TestCase):
    def test_default_case_profile_preserves_english_case_insensitivity(self) -> None:
        cases = (("RISK", "risk"), ("TITLE", "title"), ("I", "i"))

        for uppercase, lowercase in cases:
            with self.subTest(uppercase=uppercase):
                self.assertEqual(
                    qr.normalize_token(uppercase),
                    qr.normalize_token(lowercase),
                )

    def test_explicit_turkic_profile_uses_dotted_and_dotless_pairs(self) -> None:
        self.assertEqual(
            qr.normalize_token("İ", case_profile="turkic"),
            qr.normalize_token("i", case_profile="turkic"),
        )
        self.assertEqual(
            qr.normalize_token("I", case_profile="turkic"),
            qr.normalize_token("ı", case_profile="turkic"),
        )
        self.assertNotEqual(
            qr.normalize_token("I", case_profile="turkic"),
            qr.normalize_token("i", case_profile="turkic"),
        )

    def test_default_profile_does_not_guess_turkic_casing(self) -> None:
        self.assertNotEqual(qr.normalize_token("İ"), qr.normalize_token("i"))

    def test_unknown_case_profile_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "Unknown case profile"):
            qr.normalize_token("text", case_profile="unknown")

    def test_compatibility_and_turkic_case_normalization_table(self) -> None:
        cases = (
            ("ﬁ", "fi", "unicode"),
            ("ﬂ", "fl", "unicode"),
            ("ﬀ", "ff", "unicode"),
            ("ＲİＳＫ", "risk", "turkic"),
        )

        for raw, expected, case_profile in cases:
            with self.subTest(raw=raw, case_profile=case_profile):
                self.assertEqual(
                    qr.normalize_token(raw, case_profile=case_profile),
                    expected,
                )

    def test_dotted_and_dotless_i_do_not_acquire_false_matches(self) -> None:
        self.assertNotEqual(
            qr.normalize_token("İ", case_profile="turkic"),
            qr.normalize_token("ı", case_profile="turkic"),
        )
        self.assertNotEqual(
            qr.normalize_token("I", case_profile="turkic"),
            qr.normalize_token("i", case_profile="turkic"),
        )

    def test_unrelated_letters_do_not_match_ligatures(self) -> None:
        self.assertNotEqual(qr.normalize_token("ﬁ"), qr.normalize_token("fl"))
        self.assertNotEqual(qr.normalize_token("ﬀ"), qr.normalize_token("fi"))


class TokenizationTests(unittest.TestCase):
    def test_letters_and_numbers_of_every_length_are_tokens(self) -> None:
        tokens = qr.tokenize("A ve 7 42 123", page_no=4)

        self.assertEqual(
            [token.normalized_text for token in tokens],
            ["a", "ve", "7", "42", "123"],
        )
        self.assertTrue(all(token.page_no == 4 for token in tokens))

    def test_raw_text_normalized_text_span_page_and_provenance_are_retained(self) -> None:
        provenance = object()
        text = "prefix ﬁnal suffix"

        token = qr.tokenize(
            text,
            page_no=3,
            block_id="#/texts/7",
            provenance=provenance,
        )[1]

        self.assertEqual(token.raw_text, "ﬁnal")
        self.assertEqual(token.normalized_text, "final")
        self.assertEqual(text[token.source_span.start : token.source_span.end], "ﬁnal")
        self.assertEqual(token.page_no, 3)
        self.assertEqual(token.block_id, "#/texts/7")
        self.assertEqual(token.provenance, (provenance,))

    def test_line_end_hyphenation_retains_both_forms_and_raw_span(self) -> None:
        text = "hyphen-\r\nation continues"

        tokens = qr.tokenize(text, page_no=2)

        self.assertEqual(tokens[0].raw_text, "hyphen-\r\nation")
        self.assertEqual(tokens[0].normalized_text, "hyphen-ation")
        self.assertEqual(tokens[0].joined_normalized_text, "hyphenation")
        self.assertEqual(tokens[0].comparison_forms, ("hyphen-ation", "hyphenation"))
        self.assertEqual(len(tokens[0].line_end_hyphen_spans), 1)
        self.assertEqual(
            text[tokens[0].source_span.start : tokens[0].source_span.end],
            tokens[0].raw_text,
        )

    def test_pdfium_hyphenation_marker_is_joined_and_preserved(self) -> None:
        text = "hyphen\ufffeation"

        token = qr.tokenize(text, page_no=2)[0]

        self.assertEqual(token.raw_text, text)
        self.assertEqual(token.normalized_text, "hyphen-ation")
        self.assertEqual(token.joined_normalized_text, "hyphenation")

    def test_wrapped_real_compound_keeps_both_interpretations(self) -> None:
        text = "risk-\nbased"

        token = qr.tokenize(text, page_no=9)[0]

        self.assertEqual(token.raw_text, text)
        self.assertEqual(token.normalized_text, "risk-based")
        self.assertEqual(token.joined_normalized_text, "riskbased")
        hyphen_span = token.line_end_hyphen_spans[0]
        self.assertEqual(
            text[hyphen_span.start : hyphen_span.end],
            "-\n",
        )

    def test_multiple_line_end_hyphens_retain_parts_and_every_raw_span(self) -> None:
        text = "alpha-\nbeta-\ngamma"

        token = qr.tokenize(text, page_no=9)[0]

        self.assertEqual(token.line_end_parts, ("alpha", "beta", "gamma"))
        self.assertEqual(len(token.line_end_hyphen_spans), 2)
        self.assertEqual(
            [text[span.start : span.end] for span in token.line_end_hyphen_spans],
            ["-\n", "-\n"],
        )
        self.assertEqual(
            token.hyphen_decisions_for("alphabeta-gamma"),
            ("join", "keep"),
        )

    def test_hyphen_without_a_line_break_is_a_real_compound(self) -> None:
        compound = qr.tokenize("risk-based", page_no=1)
        separate = qr.tokenize("risk based", page_no=1)

        self.assertEqual(len(compound), 1)
        self.assertEqual(compound[0].normalized_text, "risk-based")
        self.assertNotEqual(
            [token.normalized_text for token in compound],
            [token.normalized_text for token in separate],
        )

    def test_dash_variants_inside_compounds_compare_equal(self) -> None:
        variants = ("risk-based", "risk‐based", "risk‑based", "risk–based")

        normalized = {
            qr.tokenize(value, page_no=1)[0].normalized_text for value in variants
        }

        self.assertEqual(normalized, {"risk-based"})

    def test_a_trailing_hyphen_is_not_joined_without_a_line_break(self) -> None:
        tokens = qr.tokenize("risk- based", page_no=1)

        self.assertEqual(
            [token.normalized_text for token in tokens],
            ["risk", "based"],
        )

    def test_repeated_words_retain_distinct_spans_on_one_page(self) -> None:
        tokens = qr.tokenize("echo echo", page_no=6)

        self.assertEqual([token.normalized_text for token in tokens], ["echo", "echo"])
        self.assertNotEqual(tokens[0].source_span, tokens[1].source_span)

    def test_repeated_words_retain_their_own_pages_across_pages(self) -> None:
        tokens = qr.tokenize_sources(
            (
                qr.TextSource("echo", page_no=1, block_id="page-1"),
                qr.TextSource("echo", page_no=2, block_id="page-2"),
            )
        )

        self.assertEqual([token.page_no for token in tokens], [1, 2])
        self.assertEqual([token.block_id for token in tokens], ["page-1", "page-2"])

    def test_pdf_page_tokens_trace_to_raw_page_text(self) -> None:
        pdf_text = qr.PdfText("sample.pdf", ("alpha ﬁ", "I 42"))

        tokens = qr.tokenize_pdf_pages(pdf_text)

        self.assertEqual([token.page_no for token in tokens], [1, 1, 2, 2])
        for token in tokens:
            page = pdf_text.pages[token.page_no - 1]
            self.assertEqual(
                page[token.source_span.start : token.source_span.end],
                token.raw_text,
            )

    def test_tokenization_is_pure_and_deterministic(self) -> None:
        first = qr.tokenize("ﬁ risk-based 42", page_no=5, block_id="block")
        second = qr.tokenize("ﬁ risk-based 42", page_no=5, block_id="block")

        self.assertEqual(first, second)

    def test_figure_and_furniture_sources_keep_page_specific_attribution(self) -> None:
        figure_prov = object()
        furniture_prov = object()
        figure = qr.TextSource(
            "shared",
            page_no=1,
            block_id="figure-1",
            provenance=figure_prov,
        )
        furniture = qr.TextSource(
            "shared",
            page_no=2,
            block_id="furniture-2",
            provenance=furniture_prov,
        )

        figure_token = qr.tokenize_sources((figure,))[0]
        furniture_token = qr.tokenize_sources((furniture,))[0]

        self.assertEqual(figure_token.page_no, 1)
        self.assertEqual(furniture_token.page_no, 2)
        self.assertNotEqual(figure_token.block_id, furniture_token.block_id)
        self.assertEqual(figure_token.provenance, (figure_prov,))
        self.assertEqual(furniture_token.provenance, (furniture_prov,))

    def test_docling_items_supply_block_and_primary_provenance(self) -> None:
        provenance = SimpleNamespace(page_no=8)
        item = SimpleNamespace(
            text="A 42",
            self_ref="#/texts/12",
            prov=(provenance,),
        )

        tokens = qr.tokenize_docling_items((item,))

        self.assertEqual([token.raw_text for token in tokens], ["A", "42"])
        self.assertTrue(all(token.page_no == 8 for token in tokens))
        self.assertTrue(all(token.block_id == "#/texts/12" for token in tokens))
        self.assertTrue(all(token.provenance == (provenance,) for token in tokens))

    def test_docling_items_map_tokens_to_relevant_provenance_entries(self) -> None:
        first = SimpleNamespace(page_no=8, charspan=(0, 6))
        second = SimpleNamespace(page_no=9, charspan=(7, 11))
        item = SimpleNamespace(
            text="shared text",
            self_ref="#/texts/13",
            prov=(first, second),
        )

        tokens = qr.tokenize_docling_items((item,))

        self.assertEqual([token.page_no for token in tokens], [8, 9])
        self.assertEqual([token.provenance for token in tokens], [(first,), (second,)])
        self.assertTrue(all(token.all_provenance == (first, second) for token in tokens))
        self.assertTrue(all(token.provenance_status == "span_mapped" for token in tokens))

    def test_overlapping_provenance_on_different_pages_is_ambiguous(self) -> None:
        first = SimpleNamespace(page_no=1, charspan=(0, 7))
        second = SimpleNamespace(page_no=2, charspan=(0, 7))
        token = qr.tokenize_docling_items(
            (SimpleNamespace(text="overlap", self_ref="#/texts/14", prov=(first, second)),)
        )[0]

        self.assertIsNone(token.page_no)
        self.assertEqual(token.provenance, (first, second))
        self.assertEqual(token.all_provenance, (first, second))
        self.assertEqual(token.provenance_status, "span_ambiguous")

    def test_invalid_multi_provenance_does_not_fall_back_to_first_page(self) -> None:
        first = SimpleNamespace(page_no=1, charspan=(20, 30))
        second = SimpleNamespace(page_no=2, charspan=None)
        token = qr.tokenize_docling_items(
            (SimpleNamespace(text="word", self_ref="#/texts/15", prov=(first, second)),)
        )[0]

        self.assertIsNone(token.page_no)
        self.assertEqual(token.provenance, (first, second))
        self.assertEqual(token.all_provenance, (first, second))
        self.assertEqual(token.provenance_status, "multiple_unmapped")


if __name__ == "__main__":
    unittest.main()
