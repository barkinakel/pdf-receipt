# Quality Report v2 research

Research date: 2026-09-04

## Conclusion

There is no mature, lightweight tool that can take an arbitrary PDF and its
generated Markdown and independently prove that the conversion is correct. The
available projects fall into two groups:

1. benchmark runners that compare predictions with manually annotated ground
   truth; and
2. per-document integrity or fact checks that test selected properties without
   claiming complete accuracy.

Quality Report v2 should therefore have two layers. The converter should keep a
fast runtime report for every user document, while a separate development
benchmark guards against regressions on an annotated corpus.

## Relevant projects

### Docling-eval and docling-metrics

- <https://github.com/docling-project/docling-eval>
- <https://github.com/docling-project/docling-metrics>

These are the closest upstream projects because this converter already uses
Docling. `docling-eval` evaluates text, layout, reading order, and table
structure against DP-Bench, OmniDocBench, DocLayNet, FinTabNet, PubTabNet, and
other ground-truth datasets. `docling-metrics` separates reusable text metrics
(edit distance, BLEU, METEOR, precision, recall, and F1), table metrics (TEDS),
and layout metrics.

`docling-eval` is a benchmark suite rather than a runtime validator. It also has
a large dependency set, including datasets, matplotlib, NLTK, APTED, COCO tools,
pandas, PyArrow, and several edit-distance packages. It should run in a separate
development environment rather than become a dependency of this local tool.
The smaller `docling-metrics` packages may be worth reassessing later, but they
are not installed by the current Docling requirement.

### OmniDocBench

- <https://github.com/opendatalab/OmniDocBench>

OmniDocBench supplies manually checked page-level ground truth for diverse
documents and evaluation code for text, formulas, tables, layout, and reading
order. Its metrics include normalized edit distance, BLEU, METEOR, formula CDM,
and table TEDS. It can compare page Markdown directly with ground-truth Markdown,
although its richer JSON-based end-to-end evaluation is recommended upstream.

Useful ideas for this project are per-element metrics and keeping text, tables,
formulas, and reading order separate. The dataset is suitable for regression
testing Docling settings, not for scoring a user's arbitrary PDF at runtime.

### olmOCR-Bench

- <https://github.com/allenai/olmocr/blob/main/olmocr/bench/README.md>

olmOCR-Bench deliberately uses small, machine-checkable facts instead of only a
soft edit-distance score. Its checks cover text presence and absence, natural
reading order, table-cell relationships, formulas, headers and footers,
multi-column pages, and scans. Any converter that emits Markdown or plain text
can be adapted to it.

This fact-based approach is valuable for a small local regression corpus: each
fixture can assert a few critical facts instead of requiring a perfect reference
Markdown file. The complete upstream benchmark is too heavy for normal use and
its math checks require a headless Chromium installation. Its fuzzy matching
must also be treated carefully; an upstream issue has documented false matches
for nearly empty output.

### opendataloader-bench and DP-Bench

- <https://github.com/opendataloader-project/opendataloader-bench>

This public harness evaluates a 200-document ground-truth corpus using reading
order similarity (NID), table structure and content (TEDS/TEDS-S), and heading
hierarchy (MHS/MHS-S). These metrics map directly to gaps in the current report.
Its documented environment requires Python 3.13 or newer, so it should remain a
separate benchmark from this Python 3.12 application.

### PDF Text Extraction Benchmark

- <https://github.com/ckorzen/pdf-text-extraction-benchmark>

This older project builds ground truth from TeX and evaluates words, reading
order, paragraph boundaries, and semantic roles across 12,099 scientific
articles. It is useful evidence for sequence and paragraph metrics but is biased
toward born-digital academic PDFs and does not cover today's Markdown table and
image expectations well.

### docmetry

- <https://github.com/gaureshpai/docmetry>

docmetry is a new contract-first extraction harness with artifact integrity,
provenance, offline deterministic stages, and optional PDF-grounded question
tests. Its manifest and artifact checks are relevant design ideas. It is a very
young project with little adoption, so it should not become a dependency; any
useful checks should be implemented locally and tested directly.

## Recommended approach

1. Implement the dependency-free runtime improvements already listed in
   `docs/TODO.md`: normalization, ordered alignment, additions and deletions,
   explained coverage, context, and artifact integrity.
2. Add a small curated local fixture set inspired by olmOCR-Bench. Each PDF gets
   explicit pass/fail facts for text presence, unwanted header absence, reading
   order, table neighbors, and image links.
3. Run Docling against DP-Bench or OmniDocBench separately during development to
   measure text, reading order, table, and heading regressions. Do not install
   those benchmark dependencies for end users.
4. Consider a small `docling-metrics` component only after the local metrics are
   stable and its installation cost and Python 3.12 compatibility are verified.
5. Keep scanned pages explicitly "unverified" without ground truth. OCR
   confidence, a second OCR engine, or an LLM judge may identify risk, but none
   should be presented as guaranteed accuracy.

