# Independent PDF-to-Markdown comparison

Development follow-up: [the evaluation protocol](COMPARISON_EVALUATION.md)
defines real-document sampling and review. Batch comparison remains planned in
[TODO section 16](TODO.md). Optional JSON output has a
[versioned contract](COMPARISON_JSON.md).
The [first real-document pilot](COMPARISON_PILOT_RESULTS.md) found parser and
alignment limitations. J's alignment fix now handles pure paragraph duplication
without spurious movement and recovers contextual hyphen joins in moved text.
J also fixes literal angle-bracket masking through source-mapped Markdown parsing.
Read individual evidence rather than interpreting transfer rates as accuracy.

Milestone H adds an offline comparison of an existing PDF and an existing
Markdown file. The Markdown can come from any tool or person. No Docling JSON,
conversion runtime, model setup or network service is used by this command.
The installed Python dependencies are still required.

```powershell
.\pdf-receipt.bat compare source.pdf existing.md
.\pdf-receipt.bat compare source.pdf existing.md --report comparison.md --issue-limit 100
.\pdf-receipt.bat compare source.pdf existing.md --case-profile turkic
.\pdf-receipt.bat compare source.pdf existing.md --json-report comparison.json
```

Inputs are read without modification. Markdown must be UTF-8 (an initial BOM is
accepted), with an `.md` or `.markdown` extension. The default report is
`existing_comparison.md` beside the Markdown. An explicit report's parent must
already exist. Existing targets and input paths are refused; exclusive creation
also protects against a target appearing while the comparison runs. A write
failure can leave a partial report: choose another report path for a retry.
`--json-report PATH` adds complete structured evidence alongside Markdown.
All paths are validated before writing. If either write fails, the other is
still attempted, completed outputs remain, and the command returns exit 1 with
the failed path. See [JSON write semantics](COMPARISON_JSON.md).
Relative paths follow the process working directory; the batch launcher changes
that directory to the repository. Use absolute paths for inputs elsewhere.

Differences and unverified pages return exit 0: the comparison succeeded.
Input, parsing or report-writing failures return exit 1; invalid CLI arguments
return exit 2. Conversion flags such as `--formula`, `--profile`, `--image-scale`
and `--skip-existing` are not accepted. Existing conversion commands and their
two-stage quality reports retain their behavior.

## What the report measures

The PDF text layer is compared directly with tokenized Markdown text. Unicode
normalization, case folding, short tokens and contextual line-end hyphen handling
reuse the existing evidence-preserving tokenizer. `unicode` is the default case
profile; `turkic` uses Turkish casing. Punctuation and formatting are not
scored as textual content.

Direct alignment first checks complete ordered containment in linear time to
identify pure additions/removals, including long repeated paragraphs. Mixed
edits use bounded lookahead of 64 tokens. Every source and target
occurrence is consumed exactly once across the whole document. Repetitions do not
share a match. No figure, furniture, footnote or table-repetition exemption is
inferred. Large rearrangements can appear as missing/added text; this is not an
optimal semantic diff or an explanation of which conversion stage failed.
Moved line-end-hyphen joins require neighboring evidence in the original token
streams and consume a target occurrence only once. Candidate search is bounded;
ambiguous or heavily repeated cases may remain unexplained. Recovered joins in
moved text count as order risks, not accepted in-order transfer.

The report separates accepted matches, missing occurrences, added occurrences
(including surplus repetitions), substitutions and order risks. Substitutions
contribute to both loss and addition numerators. Transfer and loss use source
tokens as denominator; additions use Markdown tokens. Empty denominators are
`n/a`. Both accounting identities and per-page source counts are shown.
Target-only additions have no inferred PDF page.

### Grouped differences

Milestone K groups consecutive operations of the same kind into token excerpts.
An accepted match, a type change, a PDF page boundary or nonconsecutive source
or target occurrence indexes starts a new group. Groups contain at most 40
operations; longer passages continue in separate groups. A passage crossing
pages stays split so that page-local offsets remain unambiguous. Missing text
and suspected movement always remain separate; source reading order may itself
be wrong, so an order risk is not a verified loss.

Groups use size-based priority: descending operation count, then original
alignment position for ties. A substitution counts as one operation for this
ranking even though it has two endpoints. The size is that of each capped group,
not the whole original passage. This is not semantic importance or confidence.
Occurrence order within each group is unchanged.

`--issue-limit` now limits **groups**, rather than individual differences; its
default remains 50 and any positive integer is accepted. Counts and rates always
cover the full alignment. The report discloses both omitted groups and omitted
operations. Increase the limit and choose a new report path to see more groups.

Each group includes excerpts and up to three neighboring tokens on each side;
PDF context stays on the affected page. A side with no corresponding occurrence
shows the existing alignment-gap context without assigning that occurrence a
PDF page. Each excerpt is capped at 800 characters with a truncation label.
Excerpts join raw token spellings with spaces; they are reading aids, not exact
source substrings or rendered Markdown.

Expandable **Occurrence details** retain every operation in each displayed
group, including zero-based occurrence indexes, type, raw and normalized text,
PDF page, Markdown line and half-open character spans. These details are not
character-truncated. View the report source if a Markdown viewer does not
support HTML details. PDF offsets are page-local; Markdown offsets are file-local
after decoding the optional BOM. Grouping neither reruns alignment nor changes
the conversion command's two-stage report.

## Evidence limits

The PDF text layer is evidence, not ground truth. It can contain omissions,
incorrect text or an incorrect reading order. Pages without comparable tokens
are explicitly unverified, whether scanned, blank or otherwise inaccessible.
No OCR is run. Text-bearing pages can still contain unverified scanned regions.
Reported rates describe the available text layer, never whole-document accuracy.

### Supported Markdown dialect

Independent comparison uses `markdown-it-py>=4.2,<5`: CommonMark with pipe tables.
Headings, lists, blockquotes, nested emphasis, escapes, inline links and full,
collapsed or shortcut reference links/images are parsed as syntax. Link labels
participate; image alt text, destinations, titles and reference definitions do
not. Undefined references remain literal text. HTML entities are decoded in
prose, while inline, fenced and indented code stays literal, including Markdown
examples within code. Fence language labels are excluded.

HTML tables contribute cell text in source order, separated at cell boundaries;
HTML `img src` joins the image inventory. Tags, attributes, comments and
script/style/template/head content do not contribute prose. HTML is parsed
without execution or rendering. CSS visibility, JavaScript, `srcset`, SVG image
references and browser error recovery are unsupported. This is text evidence,
not a browser-equivalence guarantee.

Math has no extension or semantic evaluator: its literal textual tokens
participate under the same punctuation rules as other prose. Footnotes,
front matter, task lists and other Markdown extensions have no special handling;
their syntax may contribute tokens. Tables, formulas, visual layout and image
content are not compared structurally or visually.

The adapter records original character positions during block and inline
parsing. Decoded entities and formatted words retain their original raw spelling
and half-open span, including intervening syntax. CRLF/CR normalization preserves
file offsets and line evidence. A block whose positions cannot be preserved
causes an explicit comparison failure instead of fabricated locations. The
conversion command retains its existing Docling-specific tokenizer.

Supported inline/reference/HTML image targets are resolved relative to the Markdown folder.
Local files are checked for existence, readability, nonempty content and actual
image decoding. Paths outside that folder, including resolved symlink escapes,
are refused. Remote and unsupported targets are reported as unchecked and never
fetched. A decodable image proves neither correspondence with a PDF image nor
that all PDF images survived. Image diagnostics do not change comparison exit
status and are separate from text counts.

## Verification

`tests/test_markdown_evidence.py` covers the dialect and original source spans.
`tests/test_comparison_json.py` covers the JSON contract, shared computation,
exclusive writes, path collisions and partial-success diagnostics.
`tests/test_comparison_groups.py` covers size ranking, ties, page boundaries,
movement, repetitions, mixed edits, display bounds and retained evidence.
`tests/test_comparison.py` covers occurrence accounting across pages, repetitions,
loss/addition, substitutions, ordering, Unicode, empty evidence, Markdown syntax,
location evidence, report truncation, image diagnostics and CLI file protection.
It also compares the checked-in original formula PDF with independently authored
Markdown without creating a Docling runtime. These are deterministic offline
regression checks, not a general accuracy benchmark.

```powershell
.venv\Scripts\python.exe -m unittest tests.test_comparison_json tests.test_comparison_groups tests.test_markdown_evidence tests.test_comparison
.venv\Scripts\python.exe -m unittest discover -s tests -t .
```
