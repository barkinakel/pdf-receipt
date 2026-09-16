"""Original source-location and visible-text regression cases for comparison."""
import unittest
from pathlib import Path

from pdf_receipt import comparison as cp, quality_report as qr
from pdf_receipt.markdown_evidence import parse_markdown


class MarkdownEvidenceTests(unittest.TestCase):
    def target(self, text):
        return cp.compare_text(qr.PdfText("empty.pdf", ("",)), text).target_tokens

    def test_literal_angle_brackets_are_not_html(self):
        self.assertEqual([t.normalized_text for t in self.target("<TaskName 125-386>")],
                         ["taskname", "125-386"])

    def test_entities_preserve_raw_spans_and_unicode(self):
        text = "# caf&eacute; &#304; A &amp; B"
        tokens = self.target(text)
        self.assertEqual([t.normalized_text for t in tokens], ["café", "i\u0307", "a", "b"])
        self.assertEqual(tokens[0].raw_text, "caf&eacute;")
        for token in tokens:
            self.assertEqual(text[token.source_span.start:token.source_span.end], token.raw_text)

    def test_inline_and_fenced_code_are_literal(self):
        text = "`[alpha](beta)`\n\n```md\n![photo](image.png) &amp;\n```"
        self.assertEqual([t.normalized_text for t in self.target(text)],
                         ["alpha", "beta", "photo", "image", "png", "amp"])

    def test_reference_images_and_definitions_are_not_text(self):
        text = "before ![hidden][pic] after\n\n[pic]: assets/image.png \"title\""
        self.assertEqual([t.normalized_text for t in self.target(text)], ["before", "after"])

    def test_nested_labels_repeated_words_and_crlf_offsets(self):
        text = "> 1. [**word**](word) word\r\n>    caf&eacute;\r\n"
        tokens = self.target(text)
        self.assertEqual([t.normalized_text for t in tokens], ["word", "word", "café"])
        self.assertEqual([t.source_span.start for t in tokens],
                         [text.index("word"), text.index("word\r"), text.index("caf")])

    def test_html_table_entities_comments_and_script(self):
        text = '<table><tr><td>A</td><td>caf&eacute;</td></tr></table>\n<!-- hidden -->\n<script>secret</script>'
        self.assertEqual([t.normalized_text for t in self.target(text)], ["a", "café"])

    def test_link_labels_and_code_do_not_consume_destinations(self):
        text = "[alpha](alpha) `alpha` [alpha][ref]\n\n[ref]: alpha"
        tokens = self.target(text)
        self.assertEqual(len(tokens), 3)
        self.assertEqual([t.source_span.start for t in tokens], [1, 16, 24])

    def test_table_repeated_cells_keep_distinct_spans(self):
        text = "| word | word |\n|---|---|\n| word | word |"
        tokens = self.target(text)
        self.assertEqual(len(tokens), 4)
        self.assertEqual(len({t.source_span.start for t in tokens}), 4)

    def test_formatting_inside_word_preserves_visible_word_and_raw_span(self):
        text = "pre**fix**suffix"
        tokens = self.target(text)
        self.assertEqual([t.normalized_text for t in tokens], ["prefixsuffix"])
        self.assertEqual(tokens[0].raw_text, text)

    def test_list_marker_is_not_used_as_content_location(self):
        text = "1. 1\n   - 1\n\n> 1. 1"
        tokens = self.target(text)
        self.assertEqual([t.source_span.start for t in tokens], [3, 10, 18])

    def test_escaped_table_pipe_and_html_cell_boundaries(self):
        text = "| a\\|b | c |\n|---|---|\n| d | e |"
        self.assertEqual([t.normalized_text for t in self.target(text)], ["a", "b", "c", "d", "e"])
        self.assertEqual([t.normalized_text for t in self.target('<table><tr><td>one</td><td>two</td></tr></table>')], ["one", "two"])

    def test_unclosed_fence_keeps_content_without_language(self):
        self.assertEqual([t.normalized_text for t in self.target('```python\nvalue')], ["value"])

    def test_images_reference_html_and_code_locations(self):
        text = '![alt][PIC]\r\n\r\n[PIC]: <assets/a%20b.png> "Title"\r\n\r\n<img src="local.png" alt="hidden">\r\n\r\n`![example](ignored.png)`'
        result = parse_markdown(text)
        self.assertEqual([(i.target, i.line) for i in result.images], [("assets/a%20b.png", 1), ("local.png", 5)])
        self.assertEqual([t.normalized_text for t in result.tokens], ["example", "ignored", "png"])

    def test_inline_script_text_and_comments_do_not_become_prose(self):
        self.assertEqual([t.normalized_text for t in self.target('before <script>secret</script> after <!-- hidden -->')], ["before", "after"])

    def test_undefined_reference_and_malformed_link_remain_literal(self):
        self.assertEqual([t.normalized_text for t in self.target('[label][unknown] [other](broken')], ["label", "unknown", "other", "broken"])

    def test_indented_code_without_final_newline_keeps_exact_span(self):
        token, = self.target('    value')
        self.assertEqual(token.raw_text, 'value')
        self.assertEqual((token.source_span.start, token.source_span.end), (4, 9))

    def test_fence_interrupts_paragraph_without_blank_line(self):
        self.assertEqual([t.normalized_text for t in self.target('before\n```python\nvalue\n```')],
                         ['before', 'value'])

    def test_cr_only_report_line_numbers(self):
        report = cp.render_report(qr.PdfText('empty.pdf', ('',)), 'first\rsecond', Path('sample.md'))
        self.assertIn('Markdown line 2, raw span [6, 12)', report)

    def test_inline_hidden_images_and_nested_template_are_excluded(self):
        text = 'before <template><template>secret</template> hidden <img src="missing.png"></template> after'
        parsed = parse_markdown(text)
        self.assertEqual([t.normalized_text for t in parsed.tokens], ['before', 'after'])
        self.assertEqual(parsed.images, ())

    def test_custom_tag_prefix_is_not_a_line_break(self):
        self.assertEqual([t.normalized_text for t in self.target('pre<brand>fix</brand>')], ['prefix'])

    def test_math_remains_literal_not_semantically_scored(self):
        self.assertEqual([t.normalized_text for t in self.target('$x^2$ and $$y=3$$')], ["x", "2", "and", "y", "3"])


if __name__ == "__main__":
    unittest.main()
