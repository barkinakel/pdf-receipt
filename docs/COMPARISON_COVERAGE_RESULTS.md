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

## Continued source research after the commit checkpoint

The user requested continued work on the remaining categories. Research remains
within the original acquisition ceiling; no additional endpoint pair has yet
been accepted. The existing five pairs, including the synthetic control, still
define evaluated coverage. The cumulative download ledger now contains 32 files
and 18,105,889 bytes, including the new inventories and source metadata.

- [OCRTurk](https://github.com/metunlp/ocrturk/tree/4402e3b057cf7f2d07b441b34d6f088dd03d23e8)
  is a more directly relevant Turkish candidate. The pinned tree contains
  per-sample PDF, Markdown, figures and source metadata. Its root README and
  inspected tree provide no license notice. `data/sources.json` identifies
  original sources, including central-bank reports and journal articles.
  Document-specific source review has begun; neither reference correctness nor
  permission for the supplied annotations is established by the directory names.
  No PDF, Markdown endpoint or figure from this repository was downloaded.
- [PDF-to-Markdown benchmark](https://github.com/pdfmarkdownapp/pdf-to-markdown-benchmark/tree/d1a9d07bd64b18429887770a5d04bfe920b1efb3)
  publishes outputs and image assets. Its source-document manifest identifies
  a historical water-department booklet, using the cover and inside cover.
  The repository explicitly excludes third-party PDFs from its MIT license.
  Original-source metadata from Internet Archive could not be retrieved:
  Python's HTTPS request failed certificate verification, and the web reader
  also failed. Certificate validation was not disabled. Exact source bytes,
  page correspondence and source terms therefore remain unverified; no scan
  endpoint or image package was acquired.

Decision: retain these as candidates, not new test coverage or integrations.
Next acquisition must establish sample-level terms and endpoint correspondence,
then review source pages and author expectations before comparison. Existing
download permission remains usable within the unchanged ceiling. No additional
package, model, converter, upstream scoring script or external judge is needed.

## Turkish endpoint and complete image references: follow-up

The continued evaluation accepted OCRTurk `data_14` at revision
`4402e3b057cf7f2d07b441b34d6f088dd03d23e8` for local inspection. Its
`source.json` identifies [the original article](https://doi.org/10.2339/politeknik.1456567).
The [journal's notice](https://dergipark.org.tr/en/pub/politeknik) states
CC BY-SA 4.0 and also contains noncommercial-use wording. That inconsistency is
recorded, not resolved into a blanket license claim. OCRTurk provides no separate
repository license; this evaluation does not redistribute its annotations,
figures or PDF, or represent them as MIT-licensed material.

The existing upstream Markdown is a reference endpoint, not an identified
converter prediction or independent proof of correctness. One physical PDF page
corresponds to the article's page 823 according to its text layer. Visual review
matched the figure 8 panels, figures 9-11, prose and equation labels against the
Markdown and all four supplied PNG files. No converter was run.

Inputs under the pinned repository's `data/data_14/`:

- `data_14.pdf`: SHA-256
  `31277e2ddc97886d2cca1c50cd858957dfc44c18059e9767c2d57e4af18ca241`.
- `data_14.md`: SHA-256
  `57ad401f45025eb0d0b3d20d13606e7c9f90c4b9e79cd1a0eae439060ddfab0e`.
- `figures/figure_1.png` through `figure_4.png`: all four referenced images
  were acquired, decoded and visually inspected. Individual hashes and exact
  raw URLs remain in the ignored cumulative download ledger, along with
  upstream source metadata and equation reference files.

Before comparison, `turkish-facts.json` specified three selected sequence
expectations on both endpoints: an opening prose phrase once, a repeated
hypothesis heading twice and the final caption's distinctive name once.
All six assertions passed with the explicit `turkic` case profile. Endpoint
hashes were verified before and after evaluation. The adapter did not judge
equation semantics or the images.

The comparator reports 195 source tokens, 198 target tokens, 164 matches,
17 deletions, 20 additions, 14 substitutions and no suspected movements.
The 17 deletions are the article header and page information exposed by PDFium
but absent from the rendered sample page. They are not established visible
content loss. Formula glyphs and LaTeX command text have different textual
representations; their operation counts do not measure mathematical correctness.
All four image references resolve to decodable images. Manual inspection found
corresponding diagrams, but neither the link check nor this limited review
establishes pixel identity or complete image-text accuracy.

Reproduce using new output paths beneath the ignored coverage directory:

```powershell
.venv\Scripts\python.exe development/evaluate_comparison.py pdfmd_output/comparison_evaluation/coverage_o/turkish-facts.json --report pdfmd_output/comparison_evaluation/coverage_o/turkish-evaluation-rerun.json
.\pdf-receipt.bat compare pdfmd_output/comparison_evaluation/coverage_o/upstream/ocrturk/data/data_14/data_14.pdf pdfmd_output/comparison_evaluation/coverage_o/upstream/ocrturk/data/data_14/data_14.md --case-profile turkic --report pdfmd_output/comparison_evaluation/coverage_o/turkish-report-rerun.md --json-report pdfmd_output/comparison_evaluation/coverage_o/turkish-report-rerun.json
```

Both original commands exited successfully. All 45 downloaded files still match
their ledger hashes; cumulative acquisition is 21,676,165 bytes and six endpoint
pairs, including the earlier synthetic control. The original O results remain
unchanged. No product code changed, so the unit suite was not repeated; the last
full result remains 305 tests OK with seven skips. Documentation diff checks pass.

This adds one natural Turkish endpoint and one complete referenced-image package,
not broad Turkish coverage. Natural scan coverage is still open. Windows HTTPS
successfully retrieved the historical booklet's archive metadata without
disabling certificate verification, resolving the earlier transport problem.
That metadata identifies a paper scan but supplies no explicit rights statement;
the PDF and its derived pair were not acquired. Its exact byte/page correspondence
therefore remains unverified. Further acquisition is conditional on resolving
those source questions, not on installing another evaluation tool.

## Natural scan: existing archival OCR, not independent truth

The requested natural-scan follow-up used the 1878 booklet **Gettysburg**,
Internet Archive identifier `gettysburg00linc`, contributed by the Library of
Congress. The [Commons file description](https://commons.wikimedia.org/wiki/File:Gettysburg_.._(IA_gettysburg00linc).pdf)
identifies this edition as public domain. The [archive metadata](https://archive.org/metadata/gettysburg00linc)
records its publication date, contributor and file checksums. The historical
water-department candidate was not acquired; this is a different source.

Exact inputs acquired on 2026-09-17:

| Artifact | URL / derivation | SHA-256 |
| --- | --- | --- |
| Full scanned PDF | `https://archive.org/download/gettysburg00linc/gettysburg00linc.pdf` | `0c9395f40ad6cce9269ad05bd3fc7f99528d4ddb1f046be39ffdd0ec412dbc13` |
| Existing OCR text | `https://archive.org/download/gettysburg00linc/gettysburg00linc_djvu.txt` | `5071a257a93f9269bc4310307de934b8d9d6a6c33d144fa443e79818caca3854` |
| Markdown endpoint | Byte-identical local copy of the OCR text, named `gettysburg00linc.md` | Same hash as OCR text |

No OCR engine or PDF-to-Markdown converter was run. This is unedited archival
plain text interpreted as Markdown, **not** a formatted Markdown prediction.
The original TXT remains alongside the copy. Its same-item DjVu XML and metadata
were acquired as provenance evidence. PDF, TXT and XML match the archive's SHA-1
checksums as well as locally recorded SHA-256. Archive files do not have Git
revisions; the dated metadata and hashes pin this acquisition instead.

Both PDF and XML contain 36 physical pages. Source pages 9, 13, 25 and 28 were
rendered and visually reviewed, with XML page anchors checked for correspondence.
The targets cover the full item, including blank pages, endpapers and OCR noise;
no text was silently cleaned or cropped. Page 28 visibly identifies the 1878
edition. The scan has an existing searchable OCR layer, so a nonempty source
denominator is available on many pages. That layer is not independent truth.

Before comparison, four locally transcribed expectations were recorded in
`scan-facts.json`, each tested on the specified source page and full target:

| Fact prefix | Physical page | Independently reviewed expectation | Source / target |
| --- | --- | --- | --- |
| `battle-opening` | 13 | Opening sequence of the battle account occurs once | pass / pass |
| `speech-opening` | 25 | Opening sequence of the address occurs once | pass / pass |
| `poet-name` | 9 | The visible poet name occurs once | fail / fail |
| `refused-request` | 13 | The visible phrase about a refused request occurs once | fail / fail |

The eight assertions produced four passes and four failures. The failures are
two distinct OCR mistakes appearing in **both** endpoints, not four independent
conversion defects. For example, the printed poet surname is Montgomery, while
both OCR endpoints have `Moittgonwry`; alignment marks that incorrect spelling
as a match. The reviewed phrase on page 13 is also corrupted in both endpoints.
These selected independent visual checks reveal errors that endpoint agreement
alone cannot detect. They do not establish whole-book OCR accuracy.

The comparator reports 3,130 source tokens, 3,156 target tokens, 3,105 matches,
no deletions, 26 additions and 25 substitutions. These counts measure endpoint
agreement. They must not be used as OCR accuracy. Twelve physical pages have no
comparable source text and remain explicitly unverified: 4, 5, 7, 8, 10, 27,
29, 30, 31, 32, 33 and 36. This does not imply that every such page contains
unrecognized prose; some are blank. Visual fidelity and image retention remain
unverified, and the plain-text target has no image references.

Reproduce with new report names under the existing ignored directory:

```powershell
.venv\Scripts\python.exe development/evaluate_comparison.py pdfmd_output/comparison_evaluation/coverage_o/scan-facts.json --report pdfmd_output/comparison_evaluation/coverage_o/scan-evaluation-rerun.json
.\pdf-receipt.bat compare pdfmd_output/comparison_evaluation/coverage_o/upstream/archive/gettysburg00linc.pdf pdfmd_output/comparison_evaluation/coverage_o/upstream/archive/gettysburg00linc.md --report pdfmd_output/comparison_evaluation/coverage_o/scan-report-rerun.md --json-report pdfmd_output/comparison_evaluation/coverage_o/scan-report-rerun.json
```

Settings are `unicode`, default 50 displayed groups and complete JSON evidence.
The fact evaluator reports failed expectations; the comparison command succeeds
in generating its reports. Source hashes were checked before and after fact
evaluation. `scan-verification.json` records seven cumulative endpoint pairs,
55 ledger files totaling 23,264,462 bytes and unchanged hashes for all 40 files
in the original pilot. The ledger covers saved acquisitions; exploratory web and
metadata requests are not a byte-accurate network traffic meter. No corpus,
preview, OCR prose or generated report was added to Git.

This follow-up changes only evaluation documentation and ignored artifacts.
The complete documentation diff was reviewed and `git diff --check` passed.
The unit suite was not repeated; the last full run remains 305 tests OK with
seven opt-in skips. Existing Turkish evaluation and earlier pilot outputs were
preserved, and no new commit was created during this follow-up.

Review decision: the natural-scan gap now has a concrete case with a correlated
OCR layer and independently reviewed failures. It does not cover natural scans
without any text layer, broad scan diversity, or independent full transcriptions.
No new comparator regression is established: matching identical incorrect text
is consistent with its documented endpoint-evidence contract. Keep the warnings
and selected visual checks; do not introduce an OCR-accuracy score or install a
second converter. One pair slot remains within the original ceiling. Further
acquisition should answer a new coverage question, not merely increase the count.
