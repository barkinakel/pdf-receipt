# Quality Report v2 alignment and metric contract

The quality-analysis path now builds two separate ordered alignments for every
reported conversion:

```text
PDF text-layer tokens -> DoclingDocument tokens -> visible Markdown tokens
       extraction                 serialization
```

The returned `TwoStageAlignment` keeps those stages separate and is the only
source for Quality Report v2 counts. `report_version` is `2`. The console and
`<name>_report.md` show extraction and serialization independently rather than
collapsing them into an accuracy percentage. `QualityReport.legacy_coverage`
retains the historical v1 bag-of-words value as a diagnostic; `coverage` remains
a compatibility alias for that legacy value and is not used as a v2 headline.

## Evidence and operation semantics

Every operation stores its stage, type, source and target occurrence indexes,
raw and normalized text, source character spans, page, Docling block ID,
token-relevant Docling provenance, the item's complete provenance tuple, an
explicit provenance-mapping status, optional spatial evidence, and bounded
source/target context ranges. Markdown tokens keep offsets into the generated
Markdown, but have unknown page and no provenance unless later work supplies a
real mapping.

Operations have these meanings:

- `match` + `normalized`: the two normalized occurrences are equal. An
  ambiguous source can also record its conservative per-separator `keep`
  choices here.
- `match` + `line_end_hyphen_join`: an ambiguous line-ending separator was
  joined because a neighboring occurrence also aligned. The per-separator
  `keep`/`join` decisions are retained.
- `deletion` + `unexplained`: a source occurrence has no aligned target.
- `deletion` + `figure` or `furniture`: the occurrence is absent from the
  target, but one same-page, spatially overlapping evidence occurrence explains
  it. It remains a deletion and contributes only to accounted-for loss.
- `deletion` + `footnote`: a serialization source occurrence is a Docling item
  explicitly labeled `footnote` and retains both a block ID and provenance.
- `insertion` + `added`: a target occurrence has no aligned source.
- `insertion` + `table_repetition`: a target occurrence consumes one expected
  repetition slot derived from a merged Docling cell and is locally anchored to
  the matched source cell. Each `row_span * col_span - 1` slot is consumable
  once; absent provenance or a missing local anchor leaves the insertion added.
- `substitution` + `different`: one source occurrence and one target
  occurrence occupy the same local position but differ.
- `order_risk` + `reordered`: one source-only and one target-only occurrence
  with the same normalized text were paired as a possible move. For extraction
  this pairing is restricted to the same page. It is a risk because PDF
  content-stream order can be wrong; it is not proof that Docling reordered the
  page incorrectly.

An `AlignmentResult` validates that source indexes and target indexes are each
consumed exactly once across its operations. Explanations consume an evidence
token at most once and require PDF character-box centers to overlap the
page-qualified Docling region. Page-and-text equality by itself is not accepted.
If geometry is missing, more than one evidence token is a spatial candidate, or
the relevant candidate falls beyond the 64-item evidence bound, the deletion
stays `unexplained` rather than receiving a region claim that cannot be proved.

PDFium character boxes are retained only when `get_text_range()` offsets map
one-to-one to `count_chars()`; otherwise that page's boxes are unavailable.
PDFium already uses bottom-left page coordinates. Docling `TOPLEFT` boxes are
converted using the corresponding Docling page height; `BOTTOMLEFT` boxes are
kept in that origin. Invalid boxes and top-left boxes without a usable page
height, or boxes with a missing/unknown origin are omitted conservatively. The
same overlap rule applies to figure and furniture evidence.

For ordinary Docling text items, each token's original item-relative span is
intersected with every valid provenance `charspan`. One-page overlap assigns
that page and retains the overlapping entries; overlap across pages leaves the
page unknown and records `span_ambiguous`. A valid provenance set with no token
overlap records `span_unmapped`. Multiple entries with missing or invalid spans
record `multiple_unmapped` and do not fall back to the first page. The complete
item provenance tuple remains available separately in every case. Table-cell
text has no reliable mapping to table-level charspans, so cells from a
multi-page table deliberately have an unknown page.

## Quality Report v2 metrics

Each stage exposes source and target token counts, normalized matches,
contextual line-end-hyphen matches, explained and unexplained deletions,
explained and unexpected additions, substitutions, and reading-order risks.
Rates are fractions internally and percentages only when rendered:

| Metric | Numerator | Denominator |
|---|---|---|
| Normalized exact-transfer rate | normalized + contextual-hyphen matches | source occurrences |
| Accounted-for loss rate | explained deletions | source occurrences |
| Unexplained-loss rate | unexplained deletions + substitutions | source occurrences |
| Unexpected-addition rate | unexpected insertions + substitutions | target occurrences |

Contextual line-end-hyphen matches are accepted transfers while retaining their
specific reason. A substitution deliberately represents one lost source
occurrence and one unexpected target occurrence. An order risk is separately
accounted on both sides and is neither an exact match nor a loss. Explained
additions do not contribute to unexpected additions. A zero denominator yields
`None` internally and `n/a` in output, never an invented 0% or 100%.

The following identities are validated for every stage:

```text
source = accepted matches + explained deletions + unexplained deletions
       + substitutions + order risks

target = accepted matches + explained additions + unexpected insertions
       + substitutions + order risks
```

Up to eight representative non-match operations are retained in deterministic
alignment order. Samples keep occurrence indexes, stage and reason, raw and
normalized forms, page or `unknown`, block and relevant provenance, and the
bounded source/target contexts already recorded by alignment. Repeated tokens
therefore remain distinct occurrences rather than becoming a frequency map.

## Bounded deterministic strategy

Extraction is partitioned by page. Serialization remains one ordered stream,
but both stages use a deterministic forward scan with a maximum lookahead of
64 tokens in either stream. At each mismatch, a bounded 64-by-64 dynamic-
programming LCS window chooses whether to consume a source deletion or target
insertion while maximizing recoverable occurrences in that window. Equal
scores deterministically consume the source first. The initial pass never emits
a substitution.

A linear occurrence-queue pass next pairs equal deletion/insertion occurrences
as order risks (on the same page for extraction). Only then are remaining
contiguous hard deletion/insertion gaps paired in order as substitutions. Thus
substitution coalescing cannot hide equal occurrences lost by the initial
alignment, and repeated-token outcomes are deterministic.

For `n` source tokens, `m` target tokens, and fixed window `W = 64`, alignment
is bounded by `O((n + m) * W^2)` comparisons and stores
`O(n + m + W^2)` evidence, operations, and window state. Spatial explanation
adds at most `O((n + m) * W)` bounded candidate checks. It does not use
`SequenceMatcher`, so repeated-token behavior is not affected by `autojunk`.
Page partitioning also prevents one known-page Docling occurrence from
satisfying PDF occurrences on different pages.

Moves farther than 64 tokens without useful local anchors can be represented as
substitutions or hard differences. Tokens whose provenance page is unknown are
kept in the unknown-page extraction partition instead of being guessed onto a
page. These are deliberate accuracy/upper-bound tradeoffs; operations retain
the evidence needed for later reporting.

## Normalization, ambiguous hyphens, and Markdown

All three streams must use one explicit document-level case profile. The real
converter uses `unicode`, preserving English `I`/`i`; internal callers can
select `turkic`, preserving the separate `İ`/`i` and `I`/`ı` pairs. Mixed
profiles raise an error. Language is not guessed, and there is no CLI language
or case-profile option yet.

A line-ending hyphen keeps its conservative hyphenated form first. Each raw
separator span and each normalized segment are retained. When the conservative
forms differ, a memoized comparison evaluates `keep` and `join` independently
for every separator without constructing all `2**n` candidate strings. A
joined interpretation is accepted only when the preceding or following token
is an ordinary normalized match. Thus `risk-\nbased` still matches
`risk-based`, while contextual `hyphen-\nation` can match `hyphenation` with a
distinct reason.

The Markdown stream masks common non-visible syntax without changing string
length, preserving useful offsets. It excludes image alt text and artifact
paths, inline-link targets, reference definitions, ordered-list numbers, code
fence markers/info strings, and actual HTML tags. Ordinary link labels, code
body text, and the visible contents of CommonMark URL and email autolinks remain
tokens. Link targets and output structure are evaluated separately from this
token stream by the structural-integrity layer below.

## Structural and artifact integrity

Expected structural facts come directly from the DoclingDocument; actual facts
come from the Markdown file written to disk. The comparison is occurrence-based
and preserves document order:

- titles and section headers retain their expected Markdown levels and text;
- list-group counts and list-item depth, ordered state, and text are compared;
- tables are compared by table, row, and column using `TableData.grid`, so a
  merged cell repeated across Markdown grid slots is expected rather than
  misreported as corruption;
- normal hyperlink targets are consumed one-to-one; and
- the number of Markdown image links is checked against BODY-layer Docling
  picture items included by the default serializer.

The parser deliberately implements the GitHub-Flavoured Markdown subset emitted
by Docling rather than claiming complete CommonMark validation. It ignores
fenced code, handles ATX headings, nested ordered/unordered lists, GFM pipe
tables, escaped cell pipes, multi-line list items, balanced/nested inline link
labels and destinations, percent encoding, Windows separators, and Docling's
literal spaces in referenced-image paths. Paired inline-format markers are
removed from visible text while unmatched or escaped literal Markdown
characters remain part of the compared value. Indented fences used inside list
containers are excluded, and only marker-only lines close a fence.

Local targets are resolved relative to the Markdown file. Existing symlinks are
resolved before the candidate is required to remain under the document output
directory. Missing, directory, unreadable, empty, invalid, outside-root, and
unsupported targets remain distinct issues. HTTP, HTTPS, and mail links are
compared but never fetched; anchors are not treated as files. Pillow is already
a Docling Core dependency and is imported lazily to verify and fully decode each
image, record its byte size, format, width, and height. Unreferenced files in the
dedicated artifact directory and duplicate image targets are reported without
deleting anything.

Structural findings are serialization-integrity evidence, not proof of correct
PDF extraction. Ordinary findings keep the conversion successful and appear in
the console summary and detailed report. An unexpected report-generation
exception continues through the existing visible, non-fatal warning path.

## Synthetic development measurements

Measured on 2026-09-07 with Python 3.12.0 on Windows
(`Intel64 Family 6 Model 198`) using identical six-token pages containing
repeated `echo` occurrences. Token construction was outside the timed region;
each alignment was measured five times with `tracemalloc` enabled:

| Pages | Tokens per stream | Median | Observed range | Maximum peak memory |
|---:|---:|---:|---:|---:|
| 100 | 600 | 0.013728 s | 0.013496–0.015558 s | 0.792 MiB |
| 500 | 3,000 | 0.089558 s | 0.080512–0.096238 s | 4.055 MiB |

The near-worst-case 400-versus-400 repeated mismatch was measured three times
with `tracemalloc`: median 5.384644 seconds, observed range
4.220809–7.290506 seconds, and maximum peak memory 0.615 MiB. It produces 400
substitutions after the bounded LCS and occurrence-recovery passes.

The identical-page cases are intentionally close to best case. A separate
near-worst-case guard aligns 400 repeated `alpha` source tokens against 400
repeated `echo` target tokens, forcing a fresh full lookahead window at most
mismatches. Its limit is 15 seconds and 128 MiB; the identical-page limits stay
at 10 seconds and 128 MiB. These thresholds are deliberately generous and
detect loss of the documented bound without making normal machine-speed
variance brittle.

## Full NIST v2 measurement

Measured on 2026-09-08 with Python 3.12.0 on Windows (`Intel64 Family 6 Model
198`), cached models, forced Hugging Face and Transformers offline modes, the
default `quality` profile, and formula enrichment off. Repeated runs, including
the post-review verification, produced identical Quality Report v2 counts.

The verification command was run in a separate process with a task-specific
temporary output directory:

```powershell
$env:PYTHONPATH = Join-Path (Get-Location) "src"
$env:HF_HUB_OFFLINE = "1"
$env:TRANSFORMERS_OFFLINE = "1"
.venv\Scripts\python.exe -m pdf_receipt "NIST SP 800-30.pdf" --quality --no-open -o <temporary-output>
```

Generated benchmark outputs are intentionally not checked in.

| Measure | Extraction | Serialization |
|---|---:|---:|
| Source tokens | 42,724 | 41,355 |
| Target tokens | 41,355 | 41,245 |
| Accepted transfer | 39,921 (93.44%) | 40,680 (98.37%) |
| Accounted loss | 1,167 (2.73%) | 192 (0.46%) |
| Unexplained loss, including substitutions | 272 (0.64%) | 47 (0.11%) |
| Unexpected additions, including substitutions | 70 (0.17%) | 94 (0.23%) |
| Reading-order risks | 1,364 | 436 |

Structural integrity passes: 152/152 headings, 40/40 lists with 183/183 items,
55/55 tables with 1,274/1,274 grid cells, and 7/7 decoded PNG artifacts. The
artifacts total 178,143 bytes; none is missing, invalid, duplicated, or stale.
The document contains no DoclingDocument hyperlinks, so link integrity is 0/0;
this does not claim that PDF annotations were extracted.

The latest warm-cache verification took 283.355 seconds end to end; the CLI's
per-document conversion timer reported 276 seconds. The highest real Docling
Python process `PeakWorkingSet64` from valid process samples in the first two
offline measurement runs was 3,587,977,216 bytes (3,421.762 MiB, 3.342 GiB).
The post-review run reconfirmed output metrics but its process-memory query was
not available in the restricted shell. The old v1 bag-of-words value was
99.62%, but its short-token omissions and non-occurrence-based accounting make
it neither ground truth nor directly comparable to the v2 transfer rates.

## Deferred limitations

- Structural parsing covers Docling's emitted Markdown dialect, not arbitrary
  hand-written CommonMark extensions or HTML structure.
- PDFium text/character offset disagreement disables spatial attribution on
  that page; no heuristic offset repair is attempted.
- Table cells spanning several table-level provenance entries remain page
  unknown because Docling does not provide a reliable cell-to-page charspan in
  this path.
- Footnote explanations cover only serialization deletions whose Docling role,
  block, and provenance are explicit. They do not guess about glued PDF-layer
  numbers or infer missing footnotes from spelling alone.
- Merged-cell additions are explained only within the finite span-derived slot
  count and near a matching source cell; other repeated text remains unexpected.
- The Markdown masker is deliberately small and deterministic, not a complete
  CommonMark parser. Unusual nested constructs, formulas, and custom extensions
  may still yield imperfect text operations.
- The fixture's lost PDF link annotation/repeated URL row remains recorded as a
  limitation. A link annotation absent from the DoclingDocument cannot be
  verified as Markdown serialization. The decorative drop cap is diagnosed in
  `docs/DROP_CAP_DIAGNOSIS.md`: its character survives, but Docling document
  parsing/layout does not reconstruct the word relationship and final document
  assembly then loses the fragments' reading-order adjacency.
