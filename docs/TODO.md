# Development plan

The project is published at `https://github.com/barkinakel/pdf-receipt` under the
MIT license. Development continues in this repository; pushing remains a
user-initiated action. The baseline is commit `569a7a0`; all 59 unit tests
passed at that point.

This plan is ordered. Finish and verify one milestone before starting the next
one. Quality Report v2 is the first product goal because the current
bag-of-words score can overstate coverage: it ignores one- and two-character
tokens, reuses the complete Markdown word counter for every PDF page, and does
not consume page-specific figure/furniture occurrences.

## Progress

Current state after Milestone H.

| Milestone | Sections | State |
|---|---|---|
| A: fixture foundation and tokenization | 1-2 | done |
| B: ordered two-stage alignment | 3 | done |
| B: Quality Report v2 metrics and explanations | 4 | done |
| C: structural integrity and full v2 gate | 5-6 | done |
| D: drop-cap diagnosis | 7 | done |
| E: image scale | 8 | done |
| F: manifest and skip-existing | 9 | done |
| G: live formula test | 10 | done |

Landed for sections 1-7:

- `tests/fixtures/` fact-based PDF corpus plus `tests/fixture_harness.py`, with
  live Docling checks isolated in `tests/integration/` behind
  `PDF_RECEIPT_RUN_DOCLING_FIXTURES=1`.
- Provenance-preserving tokenization in `src/pdf_receipt/quality_report.py`, with the
  `unicode`/`turkic` case profiles and the cautious line-end-hyphen model.
- `src/pdf_receipt/alignment.py`: page-partitioned, bounded-LCS two-stage occurrence
  alignment producing extraction and serialization results.
- `src/pdf_receipt/quality_metrics.py`: `StageMetrics` with enforced source and target
  accounting identities, `None` for zero denominators, separate substitution and
  reading-order-risk categories, and bounded representative issue samples.
- `report_version = 2`, the two-stage console summary and Markdown report,
  `legacy_coverage` with its documented `coverage` alias, and the OCR-only
  unverified-page wording.
- Dependency-free Docling-GFM structure comparison plus safely resolved local
  links, Pillow-decoded image artifacts, dimensions, and stale-file detection in
  `src/pdf_receipt/structural_integrity.py`.
- A concise structural console result and detailed report tables for headings,
  lists/items, tables/cells, links, images, and artifact status.
- The full offline fixture gate and the 95-page NIST v2 diagnostic benchmark.
- A captured two-stage drop-cap diagnosis in `docs/DROP_CAP_DIAGNOSIS.md`:
  PDFium retains the intact word, Docling parsing/layout keeps it as two adjacent
  fragments, final document assembly loses their adjacency, and Markdown
  faithfully serializes the detached order.
- `docs/ALIGNMENT.md` plus README updates in both languages.

Verification at this point: `.venv\Scripts\python.exe -m unittest discover -s tests -t .`
reports 188 tests OK with 2 skips. The separately enabled live Docling
integration suite passes both its pipeline-stage diagnosis and all three
fixtures offline with cached models. The final NIST run passes structure and
artifact integrity; its detailed measurements are recorded in
`docs/ALIGNMENT.md`. `git diff --check` is clean.

## Working contract

- Optimize for local, offline PDF conversion with useful Markdown, Docling JSON,
  referenced image artifacts, and honest quality evidence.
- Treat a PDF text layer as a comparison source, not guaranteed ground truth.
  Scanned pages without independent ground truth must remain `unverified`.
- Separate extraction quality from serialization quality:

  ```text
  PDF text layer -> DoclingDocument -> Markdown and artifacts
   extraction quality                serialization integrity
  ```

- Do not add a runtime dependency for Quality Report v2 unless the standard
  library cannot meet measured correctness or performance requirements.
- Preserve the default conversion behavior unless a milestone explicitly adds
  an opt-in flag.
- Prefer small fact-based regression assertions over exact full-file Markdown
  snapshots.
- A milestone is complete only when its focused tests and the full unit suite
  pass, relevant documentation is updated, and `git diff` contains no unrelated
  changes.
- If local commits are authorized, create one focused commit per completed
  milestone. Pushing to `origin` stays a user-initiated action.

## 1. Regression contract and fixture foundation

Create the evidence needed before changing the quality algorithm.

- Add a small checked-in fixture corpus covering:
  - Turkish characters, including dotted and dotless I
  - ligatures such as `ﬁ`, `ﬂ`, and `ﬀ`
  - true line-end hyphenation and a real hyphenated compound
  - repeated words on one page and across pages
  - one- and two-character words and numeric table cells
  - headings, lists, links, tables, and images
  - multi-column reading order
  - a scanned page
  - a decorative drop cap
- Store explicit facts next to each fixture, such as required/forbidden text,
  ordered phrases, heading levels, table-cell relationships, and valid image
  links. Do not use an entire generated Markdown file as the only oracle.
- Keep fixture generation reproducible without adding a runtime dependency. If
  a development-only generator is used, retain its source or document exactly
  how each fixture was made.
- Separate fast unit tests from live Docling integration tests. The integration
  corpus must run without downloading models once the documented setup is
  complete.

Acceptance:

- The existing 59 tests still pass.
- The fixture harness reports the fixture name and failed fact clearly.
- At least one regression test demonstrates each known Quality Report v1 bug:
  short tokens omitted, a repeated Markdown occurrence reused across PDF pages,
  and figure/furniture text incorrectly explaining occurrences on another page.

## 2. Provenance-preserving tokenization and normalization

Replace plain `Counter` tokens with a token model that retains enough evidence
to explain every comparison result.

- Each token should retain its raw text, normalized form, page number, source
  span, and Docling block/provenance identity when available.
- Include Unicode letters and numbers of every length. Do not silently discard
  one- and two-character words or numeric cells.
- Apply compatibility normalization suitable for ligatures, then case handling,
  with explicit tests for Turkish `İ`, `I`, `i`, and `ı`.
- Normalize quote/dash variants only if punctuation participates in the chosen
  comparison contract.
- Join line-end hyphenation conservatively. Preserve raw tokens and provenance,
  and do not merge genuine compounds blindly.
- Keep normalization as a pure, deterministic layer with table-driven unit
  tests.

Acceptance:

- All fixture tokens can be traced back to raw source text and a page.
- Ligatures and harmless Unicode presentation differences compare equal.
- True compounds and Turkish casing do not acquire false matches.
- No token is dropped solely because it has fewer than three characters.

## 3. Two-stage ordered alignment

Implement two separate comparisons instead of one direct PDF-to-Markdown score.

### 3a. Extraction comparison

Align the PDF text layer with DoclingDocument content while retaining PDF page
and Docling provenance.

- Count repeated occurrences once; every match or explanation consumes one
  occurrence.
- Report deletions, insertions, substitutions, and reading-order disagreements.
- Attribute figure and furniture text only on the correct page and, when
  coordinates permit, the correct region.
- Treat PDF text-layer order as fallible on multi-column pages. Describe an
  order disagreement as a risk, not automatic proof that Docling is wrong.

### 3b. Serialization comparison

Align DoclingDocument content with the Markdown emitted from the same document.
Use Docling provenance to locate Markdown additions where possible; otherwise
mark their page as unknown rather than guessing.

Implementation constraints:

- A standard-library algorithm such as `difflib.SequenceMatcher` is acceptable,
  but repeated-token behavior must be tested and `autojunk` must not silently
  corrupt long-document results.
- Use page/block alignment or bounded windows when needed. Do not allow an
  unrestricted quadratic comparison to make large documents impractical.

Acceptance:

- Two PDF occurrences cannot both match one Markdown occurrence.
- Deletion, insertion, substitution, and order fixtures produce stable results.
- A 100-page and a 500-page synthetic token stream complete within documented
  time and memory bounds on the development machine.

## 4. Quality Report v2 metrics and explanations

Define every denominator and keep normalized matches separate from explained
loss.

- Add `report_version = 2`.
- Report at least:
  - normalized exact-transfer rate: matched source tokens / source tokens
  - accounted-for loss rate: explained deletions / source tokens
  - unexplained-loss rate: unexplained deletions / source tokens
  - unexpected-addition rate: unexpected additions / Markdown tokens
  - substitution count, with an explicit rule for whether it also contributes
    to deletion/addition totals
- Show raw text, normalized text when different, page/provenance, and surrounding
  context for representative problems.
- Make explanation counters occurrence-based and page/region-aware for figures,
  furniture, footnote numbers, and any table serialization repetition.
- Preserve the report path and a concise console summary. Do not preserve flawed
  internal field semantics merely to keep old unit tests unchanged. If the old
  score is temporarily useful, expose it explicitly as `legacy_coverage`.
- Relabel or replace the historical NIST `99.6%` README claim after v2 is
  measured; do not present the v1 number as verified conversion accuracy.
- Continue to state that OCR-only pages cannot receive a verified accuracy
  percentage without independent ground truth.

Acceptance:

- Metric identities and denominators are unit-tested, including empty sources.
- Explained loss never improves the raw transfer rate silently.
- Console and Markdown reports distinguish extraction issues, serialization
  issues, structural issues, and unverified pages.

## 5. Structural and artifact integrity

Compare DoclingDocument structure with the serialized Markdown and files.

- Check heading counts and levels, list counts/items, table counts, and table-cell
  text.
- Check normal link targets and image link targets.
- Resolve local artifact links safely within the output directory; flag missing,
  empty, outside-root, or unreadable targets.
- Decode images and record their dimensions. A filename with image extension is
  not sufficient evidence that the artifact is valid.
- Check expected artifact counts and detect stale extra artifacts when they can
  make output ambiguous.
- Keep these checks under serialization/integrity; they do not prove that
  Docling extracted the source PDF correctly.

Acceptance:

- Tests cover a missing image, empty image, invalid image bytes, broken relative
  link, outside-root link, lost heading, changed list, and changed table cell.
- Report generation remains non-fatal to an otherwise successful conversion,
  but every report failure remains visible as a warning.

## 6. Full regression and benchmark gate

Run the completed v2 pipeline against the curated fixtures and the NIST
document.

- Use the fact-based fixture expectations as the correctness gate.
- Compare v1 and v2 NIST output only as diagnostic history; v1 is not ground
  truth.
- Record extraction, serialization, structure, duration, and peak-memory results
  separately.
- Keep external suites such as DP-Bench or OmniDocBench in a separate development
  environment.
- Optionally run MarkItDown against the same fixtures as a development baseline.
  Do not add it as an end-user dependency without evidence that it improves a
  defined profile.

Completed gate (2026-09-08, Python 3.12.0, Windows, cached models, offline,
default `quality` profile):

- All fixture facts pass, including decoded referenced images; the live suite
  completes as one integration test with three fixture subtests.
- NIST extraction transfer is 93.44% (39,921/42,724), with 2.73% accounted loss,
  0.64% unexplained loss, and 1,364 reading-order risks.
- NIST serialization transfer is 98.37% (40,680/41,355), with 0.11% unexplained
  loss, 0.23% unexpected additions, and 436 reading-order risks.
- NIST structural integrity passes for 152 headings, 40 lists/183 items, 55
  tables/1,274 cells, and 7/7 decoded PNG artifacts with no stale files.
- The post-review warm-cache run takes 283.355 seconds end to end (276 seconds
  inside the document conversion timer). The maximum valid real-process
  `PeakWorkingSet64` observation from the first two offline measurement runs is
  3,587,977,216 bytes (3.342 GiB).
- The v1 `99.62%` value remains diagnostic history, not ground truth and not a
  directly comparable v2 transfer score.

Quality Report v2 is complete when milestones 1-6 pass, the report documents its
limits honestly, and the README examples match the new output. This condition is
satisfied, and sections 7-9 are also complete. Milestone G is complete.

## 7. Lost decorative drop caps

Investigate the known `This chapter` -> `his chapter` loss using the drop-cap
fixture.

- Determine whether the letter exists in the PDF text layer.
- Inspect whether Docling sees it as text, a separate block, or a picture.
- Locate the first stage where it disappears: extraction, document assembly, or
  Markdown serialization.
- Do not add a guessed leading letter. Implement a correction only when evidence
  makes false insertions unlikely; otherwise document the upstream limitation
  and consider an upstream Docling report.

Acceptance:

- The diagnosis identifies the failing stage with captured evidence.
- Any correction has positive and negative regression cases.

Completed diagnosis (2026-09-08, Docling 2.124.0):

- PDFium returns the intact `This chapter...` text and adjacent character boxes.
- Docling parsed text lines and layout clusters already represent `T` and
  `his chapter...` as separate but adjacent blocks. Page and conversion assembly
  preserve that adjacency.
- The final DoclingDocument/JSON retain both as BODY text items but place a
  picture and right-column blocks between them.
- Markdown serialization faithfully preserves that already detached order, so
  word fragmentation begins in Docling parsing/layout and reading-order
  adjacency is lost during final document assembly. Markdown serialization is
  not an additional failing stage.
- No local correction is applied. There is no semantic drop-cap marker, and one
  synthetic positive case cannot rule out false joins of initials, labels,
  charts, columns, or intentionally separate one-letter paragraphs. The fixture
  continues to accept both the current upstream behavior and a future corrected
  outcome. Evidence and upstream-report notes are in
  `docs/DROP_CAP_DIAGNOSIS.md`.

## 8. Configurable image resolution

Add an opt-in `--image-scale` setting.

- Keep `1.0` as the default so current output remains unchanged.
- Accept documented safe values such as `1`, `2`, and `3`, and reject invalid or
  unreasonable input clearly.
- Thread the value into Docling's pipeline options.
- Report conversion duration and total artifact bytes in the batch/result
  summary when useful.
- Verify that higher scales increase dimensions as expected and do not break
  Markdown image links.

Completed (2026-09-15, pinned Docling 2.124.0, cached models, offline):

- `--image-scale` accepts finite floats in the inclusive range `1.0` to `3.0`,
  including fractional values such as `1.5`. This follows Docling's float field
  while bounding resource use; the default remains `1.0` in both profiles.
- The value reaches `PdfPipelineOptions.images_scale`; CLI and direct runtime
  calls reject unsupported values before importing Docling or loading models.
- Per-document completion and batch entries report conversion/export/report
  duration (excluding runtime object creation but including lazy pipeline/model
  initialization during conversion) and bytes of all existing artifact-folder
  files, including stale files. Measurement failures warn without failing an
  otherwise successful conversion. No manifest or cleanup behavior was added.
  Directory scanning propagates access errors instead of silently reporting
  partial or zero artifact bytes.
- The offline live test decodes every referenced image at all four documented
  example scales in both profiles, verifies proportional dimensions within
  pixel rounding, and checks working forward-slash Markdown links.
- Focused converter/CLI tests pass; full discovery reports 195 tests OK with
  3 skips (the opt-in live tests). The separate image-scale live test passes
  all eight profile/scale combinations. Both READMEs document the option and
  measurement scope without adding benchmark figures.

## 9. Output manifest, atomic completion, and `--skip-existing`

Do not implement freshness using modification times alone.

- Write a per-document manifest containing:
  - source identity (size, modification time, and SHA-256)
  - application and Docling versions
  - profile, formula setting, image scale, and report setting
  - expected Markdown, JSON, report, and artifact paths
  - artifact sizes and a final completion marker
- Write the completion manifest last. Prefer a staging directory or another
  safe atomic-completion strategy so an interrupted run cannot look complete.
- `--skip-existing` may skip only when the manifest matches the source and all
  requested settings, every required output passes integrity checks, and the
  completion marker is present.
- A missing, old, corrupt, or incompatible manifest causes reconversion.
- Show converted, skipped, and failed counts separately in batch summaries.
- Never delete unrelated user files while cleaning stale converter artifacts.

Completed (2026-09-15):

- `src/pdf_receipt/manifest.py` records source path/size/mtime/SHA-256,
  application and Docling/core versions, application source digest, all four
  conversion settings, expected relative export/artifact paths, file sizes and
  hashes, schema version, and the final completion marker.
- Completion is atomically invalidated before exports and atomically published
  last after validation. The same per-document exclusive lock protects writers
  and reuse checks. Failed invalidation stops before changing outputs; failed
  report or completion recording warns and leaves the run ineligible for reuse.
- `--skip-existing` verifies required hashes, Docling JSON schema, decoded
  Markdown/JSON image targets (including Windows JSON separators), and local
  Markdown links. All-skipped commands avoid creating the Docling runtime.
  Batch summaries separate converted, skipped, and failed documents.
- Required outputs are tracked from exports and their image references.
  Unrelated files, old reports when disabled, and unreferenced stale artifacts
  are preserved. No cleanup or output rollback is attempted. A force-killed
  process can leave an incomplete record, partial exports, a temporary file,
  and a lock; both READMEs explain manual lock recovery after checking that no
  conversion is running.
- Focused manifest/converter/CLI tests: 72 passed. Full discovery: 219 tests OK,
  4 opt-in live-test skips. The separate cached-model offline Docling manifest
  check passed on the structure fixture and rejected a corrupted image.
- Both READMEs and fixture instructions are updated without new benchmark
  figures. Section 10 remains unstarted.

## 10. Live formula conversion

When network/model availability permits, finish the CodeFormulaV2 download and
test `--formula` with a real PDF.

- Verify LaTeX output and surrounding prose.
- Test both fast and quality profiles.
- Verify and document interrupted-download recovery instead of assuming it.
- Keep ordinary conversion usable when the optional model is unavailable.

Completed (2026-09-15, Docling 2.124.0):

- Completed the authorized CodeFormulaV2 download at snapshot
  `ecedbe111d15c2dc60bfd4a823cbe80127b58af4` and verified the full model SHA-256.
  A stalled standard download required a development-only bounded range transfer;
  existing partial files were preserved. No model files were added to Git.
- Added an original, reproducible PDF with raised exponents, a drawn fraction,
  and surrounding prose. Both fast and quality profiles produce correct LaTeX
  in JSON and Markdown, preserve prose and equation order, and complete reports
  and manifests offline.
- Verified the installed Hub 1.29.0 client starts a new partial file at offset
  zero. Its actual temporary-file lifecycle also passes a simulated interrupted
  transfer/retry check. Both READMEs now document restart rather than promising
  byte resume; the development range-transfer recovery is distinguished from
  normal application behavior in `docs/FORMULA_VERIFICATION.md`.
- With optional formula-engine creation made unavailable, ordinary conversion
  passes in both profiles; explicit formula conversion fails visibly and leaves
  its manifest incomplete. No runtime behavior or dependency was changed.
- Verification: 2 focused fixture tests passed; 3 opt-in offline formula tests
  passed; full discovery reports 224 tests OK with 7 live-test skips.
- Known limits: two simple equations are a regression gate, not general formula
  accuracy evidence. Upstream Transformers configuration warnings remain
  documented. Milestones A-G are complete; deferred work remains deferred.
- Review follow-up (2026-09-16): pin the recorded snapshot in test-only formula
  options; separate the Hub 1.29.0 diagnostic behind its own opt-in flag and skip
  other Hub versions explicitly. Four focused tests and the diagnostic pass;
  full discovery reports 226 tests OK with seven opt-in skips. The pinned runtime
  options and snapshot availability were checked offline; model inference was
  not repeated for this test-configuration change.

## 11. Independent PDF-to-Markdown comparison (Milestone H)

Compare an existing source PDF with an existing Markdown file, regardless of
which tool or person produced the Markdown. Do not require Docling JSON, rerun
conversion, load models, infer a conversion tool, or attribute differences to
intermediate processing stages.

CLI contract:

```powershell
.\pdf-receipt.bat compare source.pdf existing.md --report comparison.md
```

- Read both inputs without modifying them. Write a separate Markdown report;
  default to `<markdown-stem>_comparison.md` beside the Markdown. Refuse an
  existing report target instead of overwriting user files.
- Compare PDF text-layer tokens directly with visible Markdown text using
  bounded ordered alignment and globally one-to-one occurrence accounting.
- Preserve PDF page/raw-span evidence and Markdown line/raw-span evidence.
  Report accepted transfer, missing and added occurrences, substitutions and
  reading-order risks separately, with explicit denominators and empty cases.
- Do not guess page numbers for target-only additions. Do not explain losses
  away as figures, furniture, or footnotes without independent evidence.
- Show per-page source accounting and bounded representative differences with
  both contexts; disclose when additional differences are omitted.
- Mark pages without comparable text as unverified. Rates concern only the
  available text layer, never full-document accuracy; source reading order may
  itself be wrong. No OCR or network access is introduced.
- Check supported local Markdown image references relative to the Markdown
  directory, decode them and report missing/empty/invalid/outside-root targets.
  Never fetch remote images. Document Markdown dialect and visual-fidelity
  limits; link validity is not proof of PDF image preservation.
- Keep existing conversion CLI behavior and two-stage reports unchanged.

Acceptance:

- Tests cover matching inputs, missing/added/repeated tokens across pages,
  substitutions, order risks, Unicode/short tokens, empty and scanned sources,
  Markdown syntax, line/page evidence, and invalid image targets.
- A real checked-in PDF and independently authored Markdown can be compared
  offline without creating a Docling runtime or requiring a JSON document.
- CLI validates inputs, rejects conversion-only flags, preserves both inputs
  and existing output files, and reports errors clearly. Differences are a
  successful comparison (exit 0); input/write failures return nonzero.
- Update both READMEs and a dedicated comparison contract document. Run focused
  tests, the full unit suite, and inspect the final diff. Preserve pending
  Milestone G changes and do not commit without explicit authorization.

Completed (2026-09-16):

- Added `compare` with independent UTF-8 Markdown input, exclusive report
  creation, explicit case profile and a configurable representative-issue limit.
- Added direct global occurrence alignment without intermediate-document
  explanations, per-page accounting, raw/normalized location evidence and
  explicit unverified text-layer coverage.
- Added supported inline image diagnostics without remote fetching. The report
  and `docs/COMPARISON.md` document the lightweight Markdown dialect and the
  lack of visual/structural fidelity verification; both READMEs describe usage.
- Verification: 13 focused tests passed; full discovery reports 239 tests OK
  with seven opt-in skips. Real source and scanned PDFs are exercised offline.
  Final diff checks passed. Pending Milestone G work was preserved.
- No dependency, download, conversion-default change or commit was introduced.
  Follow-up work is now ordered in sections 12-16; deferred table work remains deferred.

## Deferred: merged-cell HTML tables

Markdown pipe tables cannot represent `colspan` or `rowspan`; the real structure
already remains in Docling JSON. The NIST document contains merged cells in 27
of 55 tables, so a mixed HTML serializer would turn roughly half its tables into
HTML while not recovering lists that were already flattened during extraction.

Do not implement this now. Reconsider an opt-in mixed serializer only if visual
document fidelity becomes more important than readable Markdown source and LLM
or search consumption.

## Suggested agent checkpoints

Use these as separate implementation runs rather than asking one agent to finish
the entire open-ended backlog:

1. Milestone A: fixture foundation and tokenization (sections 1-2)
2. Milestone B: ordered alignment and metrics (sections 3-4)
3. Milestone C: structural integrity and full v2 gate (sections 5-6)
4. Milestone D: drop-cap diagnosis (section 7)
5. Milestone E: image scale (section 8)
6. Milestone F: manifest and skip-existing (section 9)
7. Milestone G: live formula test when network is available (section 10)

Within each run, the agent should inspect the relevant code first, add failing
tests for the contract, implement the smallest cohesive change, run focused and
full tests, inspect the final diff, update documentation, and stop only at the
milestone's verifiable acceptance condition. It should ask for user input only
when work requires network/model downloads, destructive replacement, a new
runtime dependency, or a product decision not settled by this plan.
