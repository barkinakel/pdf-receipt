# Supplementary comparison coverage (Milestone O)

Reviewed on 2026-09-16/17. This is a bounded endpoint evaluation, not a
converter ranking or a whole-document accuracy measurement. No conversion,
model download, dependency installation or document upload was performed.
Product behavior is unchanged.

## Acquisition and provenance

The user authorized source research and at most eight supplementary pairs with
at most 100 MiB of downloaded material, including metadata and assets. The run
acquired four natural document pairs and one additional **synthetic OCR control**.
The control is not natural scanned-document coverage. Total acquisition was
17,669,153 bytes across 23 files, including repository inventories, notices and
test-source metadata. Existing pilot files are separate and were not downloaded
again. All acquired material remains ignored beneath
`pdfmd_output/comparison_evaluation/coverage_o/`.

Endpoints come from [Docling at the pinned revision](https://github.com/docling-project/docling/tree/e8c6092fe6ee995ce0719a71352b9f1fad5350cf/tests/data).
The exact revision is `e8c6092fe6ee995ce0719a71352b9f1fad5350cf`.
Its [MIT notice](https://github.com/docling-project/docling/blob/e8c6092fe6ee995ce0719a71352b9f1fad5350cf/LICENSE)
was inspected before acquiring the endpoints. Embedded publications retain
their own rights; repository licensing is not a blanket license for their
contents. For example, the DocLayNet paper has a publication notice on its first
page. This run uses local copies for inspection and does not redistribute them.

The upstream `groundtruth` directory contains conversion snapshots. Its name
does **not** make those snapshots independent truth. The run uses existing PDF
conversion outputs, including the explicitly named EasyOCR full-page snapshot;
it neither attributes them to this project's pinned Docling version nor claims
to reproduce their generation settings. Source names, full endpoint contents,
first/last-page evidence and upstream OCR test paths establish correspondence.
No Markdown file was shortened to match selected pages.

| Sample ID | PDF / Markdown paths relative to upstream `tests/data/` | Physical pages | Visual pages reviewed |
| --- | --- | --- | --- |
| `2206.01062` | `pdf/sources/2206.01062.pdf` / `pdf/groundtruth/2206.01062.md` | 9 | 1, 9 |
| `2305.03393v1` | `pdf/sources/2305.03393v1.pdf` / `pdf/groundtruth/2305.03393v1.md` | 14 | 1, 5, 14 |
| `amt_handbook_sample` | `pdf/sources/amt_handbook_sample.pdf` / `pdf/groundtruth/amt_handbook_sample.md` | 1 | 1 (printed 7-45) |
| `2203.01017v2` | `pdf/sources/2203.01017v2.pdf` / `pdf/groundtruth/2203.01017v2.md` | 16 | 1, 4, 6, 16 |
| `ocr_test` (synthetic) | `ocr/sources/ocr_test.pdf` / `ocr/groundtruth/easyocr/full_page/ocr_test.easyocr.full_page.md` | 1 | 1 |

Each raw URL is
`https://raw.githubusercontent.com/docling-project/docling/` + revision +
`/tests/data/` + the path above. `downloads.json` records exact URLs, bytes,
SHA-256 and Git blob hashes; acquired endpoint blobs matched the pinned tree.
`selection.json` records terms and provenance. `facts.json` separately pins
every evaluated endpoint:

| Sample | PDF SHA-256 | Markdown SHA-256 |
| --- | --- | --- |
| `2206.01062` | `5dfbd8c115a15fd3396b68409124cfee29fc8efac7b5c846634ff924e635e0dc` | `0e445098b9ba80a7837c8090c28ece0e988915bb1154bacea43e43a1754374b8` |
| `2305.03393v1` | `62f2a2163d768d5b125a207967797aefa6c9cc113de8bb5c725c582595dd0c1d` | `ac9d70c3e2966a5e6ec0d7659229ce2fd810d597ff22462786138334f86a28f1` |
| `amt_handbook_sample` | `7099fe05ade36067cf66e72b23277972a1a2b7d2da1cb82c8d690efd70143fe0` | `1f4f85e987b43b6243e66de39262d91bbd97c99f5f4a405246c23cad002d4465` |
| `2203.01017v2` | `4fa8dff93d74a84069210c84a38d14d62a39ec8f4e4c90bf955fdebdebcf6636` | `bfa417c369046ebf5f2a025af4a4f156d80f73edf8331b6036cf71f5aa7dde5a` |
| `ocr_test` | `73f23122e9edbdb0a115b448e03c8064a0ea8bdc21d02917ce220cf032454f31` | `28fed8792d9241376340d087cabe6ad203a646bd257cef279ab3a3a734ce1933` |

## Independently selected facts

The source pages above were rendered locally with PDFium and inspected beside
the existing Markdown **before** interpreting comparator output. The local
`prepare_facts.py` notebook records manually specified retention expectations;
it does not derive expected counts from comparison results. `facts.json` was
created before `evaluation.json` and remains unchanged after the run. All facts
are locally authored, not upstream annotations.

Each row below specifies a sequence expected once on the stated physical source
page and once in the target. The exact normalized token arrays and evidence are
in the ignored manifest/report. All source expectations have explicit pages;
target checks apply to the full Markdown, not an inferred page mapping.

| Sample / fact prefix | Source page | Source result | Target result |
| --- | --- | --- | --- |
| `2206.01062` / `abstract-opening` | 1 | pass | pass |
| `2206.01062` / `last-page-caption` | 9 | pass | pass |
| `2305.03393v1` / `title` | 1 | pass | pass |
| `2305.03393v1` / `escaped-html` | 5 | pass | pass |
| `amt_handbook_sample` / `opening` | 1 | pass | pass |
| `amt_handbook_sample` / `figure-label` | 1 | pass | fail: absent |
| `2203.01017v2` / `abstract-opening` | 1 | fail: exact sequence differs | pass |
| `2203.01017v2` / `missing-formula-label` | 6 | pass | fail: absent |
| `2203.01017v2` / `last-page-caption` | 16 | pass | pass |
| `ocr_test` / `visible-opening` | 1 | error: unverified | pass |

The 20 fact assertions produced 16 passes, three failures and one unverified
error. These are selected evidence checks, **not an accuracy percentage**.
The adapter correctly returned exit 1 because some expectations failed or could
not be verified. All five endpoint hashes were verified before and after their
evaluations. The batch separately completed all five report pairs with exit 0:
successful report generation does not mean the content has no differences.

## Findings and interpretation

### Missing content that the endpoints support

- The handbook's diagram label checked by `figure-label` is visible in the PDF
  and its text layer, but absent from the Markdown. Both source tokens are
  classified as deletions. The opening prose is retained. This is a bounded
  confirmed omission, not a claim about every diagram label.
- TableFormer's page 6 has displayed loss equations and input constraints.
  The Markdown substitutes `formula-not-decoded` comments. The independently
  selected constraint label is absent: three of its source tokens are deletions
  and its common conjunction is classified as suspected movement. The latter
  illustrates occurrence ambiguity; the absent phrase remains the stronger
  content evidence. Equation equivalence is not evaluated.
- The OTSL article preserves the reviewed sequence of literal HTML tag names
  using escaped entities. Both source and target facts pass, exercising entity
  handling on a natural publication without treating the prose as actual HTML.

### Source evidence and exact-fact limitations

- TableFormer's opening paragraph is visually retained. PDFium exposes the
  line-broken word as `com\ufffepact`; the conservative source token is `com-pact`.
  The independent fact expected `compact`, so the adapter's **exact normalized
  sequence** check fails. The main alignment correctly matches that occurrence
  through `line_end_hyphen_join`. The original expectation was retained rather
  than rewritten to manufacture a pass. This is a fact-representation limit,
  not missing content or a new alignment regression.
- DocLayNet reports many suspected movements. Its PDF text stream includes
  embedded figure text, while the Markdown places first-page right-column
  material before the abstract. Visual review confirms that source stream order
  and intended reading order cannot be equated. The reviewed opening and final
  caption survive; the rest of the movement count is **not adjudicated**.
- The synthetic OCR PDF has no comparable text layer. Its readable target
  sentence passes a target-only fact, while the source fact remains unverified.
  This neither measures OCR accuracy nor adds natural scan coverage.
- All five Markdown files have zero actual image references. The natural
  snapshots use image placeholders rather than complete local image packages.
  Zero broken references therefore does not establish image preservation.
  Visual figures, table topology and mathematical meaning remain unresolved.

The initial O evaluation confirmed no new product regression requiring a fix.
The subsequent adapter review below found a separate ordering-fact defect.
Do not turn
the snapshot omissions, exact-fact limitation or unresolved movement evidence
into an implementation change without a separately scoped reproduction and
acceptance criteria.

## Reproduction and verification

For this already-acquired local run, use new output names:

```powershell
New-Item -ItemType Directory pdfmd_output/comparison_evaluation/coverage_o/rerun
.\pdf-receipt.bat compare-batch pdfmd_output/comparison_evaluation/coverage_o/pairs.json --output-dir pdfmd_output/comparison_evaluation/coverage_o/rerun
.venv\Scripts\python.exe development/evaluate_comparison.py pdfmd_output/comparison_evaluation/coverage_o/facts.json --report pdfmd_output/comparison_evaluation/coverage_o/rerun/evaluation.json
```

Settings: `unicode` case profile, default 50 displayed difference groups,
complete JSON occurrences, exact nonoverlapping sequence facts. Batch IDs replace
periods in upstream IDs with hyphens to satisfy the documented batch ID syntax;
the fact manifest preserves upstream sample IDs separately.

The original run is in `reports/` and `evaluation.json`; page images and raw
PDFium text are in `previews/`. `verification.json` records that all 23 new
downloads and all 40 previously acquired pilot files still match their stored
SHA-256 values. No source PDF was edited. No third-party document, source prose,
preview or generated comparison output was added to Git.

Verification: `python -m unittest tests.test_comparison_evaluation` passed all
11 focused tests. O changes documentation and ignored evaluation artifacts only;
the full suite was not repeated. The preceding N verification remains 304 tests
OK with seven opt-in skips. `git diff --check` passed, and the complete tracked
diff was inspected with the pre-existing M/N work preserved.

A fresh clone does not contain these ignored manifests/endpoints. Use the
checked-in original controls in [the adapter guide](COMPARISON_ADAPTER.md) for
an offline smoke check. Reacquisition requires permission and the pinned paths
and hashes above; the application does not download them automatically.

## Coverage gaps and next decision

This completes the bounded O evaluation with explicit gaps, not comprehensive
coverage. It adds natural multi-page, two-column, formula and diagram examples
to the earlier single-page pilot. It does not add:

- Turkish natural-document evidence. The candidate
  [Turkish RAG repository](https://github.com/Turkish-RAG-Benchmark/turkish-rag-benchmark/tree/f4e0f6f1856eb94897125fb7a94a4d95791ce7c1)
  has paired source/output paths, but the inspected tree has no repository
  license and document-specific terms were not established. Only its inventory,
  README and metadata were acquired; none of its PDF/Markdown pairs were used.
- Natural scans, complete referenced-image packages, very long documents or
  independently annotated table/equation semantics. The synthetic OCR control
  cannot close those gaps.
- A new comparison engine or metric integration. Existing batch, JSON and fact
  tools were sufficient for the reviewed questions. Upstream metric reuse stays
  conditional on independent references and a separately justified scope.

The most useful next evaluation input is a rights-cleared Turkish pair, a natural
scan with an independent transcription, or a complete Markdown/image package.
Do not start a new implementation milestone implicitly to fill these gaps.

## Follow-up review (2026-09-17)

The requested review examined the batch/fact implementation and O's saved
evidence. It found an adapter correctness issue: ordering reused the greedy
disjoint occurrence counter, which could hide overlapping repeated anchors.
The original text `echo echo echo end` has two possible starts for `echo echo`,
but an ordering fact previously accepted it as a unique anchor before `end`.
Both source and target checks were affected; reversing the anchors incorrectly
returned a content failure instead of an ambiguity error.

A small original regression test reproduced all four cases before the fix.
Ordering now inspects every anchor start and returns error for ambiguity, while
count facts retain their documented disjoint occurrence policy. This fixes the
existing N contract; it adds no new metric, dependency or implementation milestone.
The output records the ordering policy separately from count matching.

Verification: 12 focused adapter tests passed; full discovery passed 305 tests
with seven opt-in skips. All 20 original O facts were reevaluated from saved
complete JSON evidence and produced identical fact results. Endpoint hashes were
verified again. The ignored `review_recheck.json` pins the reviewed source files,
evidence and current package versions; it is a review-time record, not a claimed
fingerprint of the original acquisition environment. No PDF extraction or corpus
download was repeated for this check.

Review decision: keep the fix and the existing evaluation limits. No further
blocking defect was confirmed in the reviewed scope; this is not an exhaustive
correctness proof. The natural examples are still mostly related English
technical publications, and the image/scanned/Turkish gaps remain substantial.
Prioritize independently reviewable missing categories before adding metrics or
another converter. The previous bounded source-research approval does not imply
approval to install tools or expand the corpus limit.
