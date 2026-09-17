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

Current state after the completed supplementary coverage evaluation milestone O.
The integration queue below records potential follow-up work, not an active milestone.

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
| H: independent comparison | 11 | done |
| I: real-document comparison evaluation | 12 | done: selected pilot; gaps documented |
| J: comparison reliability and Markdown support | 13 | done |
| K: readable grouped differences | 14 | done |
| L: structured comparison JSON | 15 | done |
| M: batch comparison | 16 | done |
| N: offline comparison evaluation adapter | 17 | done |
| O: supplementary real-document coverage | 18 | done, with documented gaps |

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
satisfied, and sections 7-10 are also complete.

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

## 12. Real-document comparison evaluation (Milestone I)

Evaluate whether the existing comparison report finds useful differences and
avoids misleading alarms before changing its parser or metrics. The protocol,
source shortlist and case-review template are in `docs/COMPARISON_EVALUATION.md`.
This milestone evaluates the comparator; it does not rank conversion tools.

Scope and acceptance:

- Assemble a small, fixed pilot of existing PDF/Markdown pairs. Include prose,
  multiple columns, repeated headers/footnotes, tables, formulas, local images,
  Turkish text and scans. Features may overlap; missing coverage stays explicit.
- Include independently authored Markdown and, when obtainable with suitable
  terms, pre-existing output from a producer other than Docling. Producer is
  optional research metadata, never a runtime requirement or inferred fact.
- Record dataset revision, source URL, sample ID, file hashes, page mapping,
  text-layer availability, reference provenance and applicable data terms.
  Do not mistake a repository's code license for its document licenses.
- Prefer a small selected subset of public benchmark data; ask before downloads.
  Keep external documents, predictions and private inputs out of Git in the
  ignored `pdfmd_output/comparison_evaluation/` directory. Do not install a
  benchmark runner or another converter in the application environment.
- Review representative findings against PDF appearance and independently
  specified facts. Label true content difference, parser artifact, source-layer
  problem, intentional editorial change, or unresolved. Include known retained
  and deliberately removed/repeated/moved facts to check missed detections too.
- Keep controlled mutations separate from natural conversion failures. An
  upstream reference is evidence for its annotated scope, not guaranteed full
  document truth. Never promote the PDF text layer or another converter to truth.
- Summarize reviewed findings, missed facts, uncovered categories and concrete
  parser/report work items. Do not publish a global accuracy score from a small
  selected pilot or compare our transfer rate with upstream leaderboard metrics.
- Save reproducible commands, settings and sanitized evidence under `docs/`.
  Retain all source files unchanged and confirm hashes after evaluation. Keep
  measurements out of both READMEs. No application behavior changes in I.

Completed (2026-09-16), within the approved selected-pilot scope:

- Acquired and hash-verified 12 PDF/Marker Markdown pairs, corresponding
  references and license metadata from a pinned OpenDataLoader revision. All
  external content stays ignored; inputs remained unchanged after evaluation.
- Produced offline reports and reviewed page images/reference evidence. Found
  a confirmed Markdown masking false loss and misleading order flags caused
  by source text order. Incomplete published image artifacts remain distinct
  from proven conversion failures.
- A controlled paragraph deletion and movement behaved as expected; duplication
  correctly counted added tokens but spuriously flagged unchanged text as moved.
  The failed invariant is retained, not weakened or presented as a passing test.
- Results, reproduction and uncovered categories are in
  `docs/COMPARISON_PILOT_RESULTS.md`. The sample does not validate Turkish,
  natural scans, formulas, full image packages or long documents. No general
  accuracy or upstream leaderboard claim is made.
- Integration candidates and dependency boundaries are documented in
  `docs/COMPARISON_INTEGRATIONS.md`. No product code, installed dependency or
  default behavior changed. Offline probes and diff checks ran; the full test
  suite was not repeated for documentation/evaluation-only work.
- J is ready to be requested; no implementation in J-M started.

## 13. Comparison reliability and broader Markdown support (Milestone J)

Use I's cases to expand the direct comparator's visible-text and image parsing.

Completed (2026-09-16): reproduced and fixed direct-comparison paragraph
duplication and contextual moved-hyphen regressions. Adopted the approved
`markdown-it-py>=4.2,<5` dependency with original character mapping, CommonMark
plus pipe tables, reference images and HTML text/image handling. No package
download was needed. Dialect limits are specified in `docs/COMPARISON.md` and
both READMEs. Original regressions cover entities, nested syntax, literal code,
source positions, image restrictions and malformed inputs. Existing two-stage
conversion behavior remains unchanged. The selected pilot was rechecked offline
with unchanged source hashes; no aggregate accuracy claim is made. Focused
tests: 72 passed; full discovery: 264 OK with seven opt-in skips. K is ready
to be requested; sections 14-16 have not been implemented.

- First reproduce I's paragraph-duplication regression: additions must not
  manufacture order risks in unchanged surrounding text. Fix independently of
  parser adoption, preserving bounded operation and one-to-one identities.
- Reproduce moved line-end-hyphen matching from I; distinguish a real content
  omission from a preserved joined word in a reordered block. Do not relax
  global occurrence accounting to make this case pass.
- Specify the supported dialect before implementation: reference links/images,
  escaped and nested inline syntax, HTML entities, inline/fenced code, and the
  handling of HTML tables/images and math. Explicitly identify unsupported forms.
- Preserve original Markdown offsets and raw evidence through decoding and
  normalization, including entities that change character length.
- Keep actual code content distinct from Markdown syntax inside code; do not
  count hidden destinations, definitions or comments as visible prose.
- Add reference-image resolution and preserve local-root restrictions, offline
  behavior, unreadable-target diagnostics and no implied image-fidelity score.
- Reproduce observed false alarms first; test equivalent rendered content,
  genuine losses, location evidence and malformed inputs. Preserve globally
  one-to-one accounting and existing conversion report behavior.
- Assess existing dependency availability before choosing a parser. Any new
  dependency requires explicit approval; do not grow ad-hoc regexes into an
  undocumented full Markdown implementation.
  Consult `docs/COMPARISON_INTEGRATIONS.md`; `markdown-it-py` and `marko` are
  already present transitively, but direct adoption still needs a version and
  exact source-offset strategy. Integrate at most one unless justified.
- Update the comparison contract and both READMEs; focused/full tests and diff
  review are required. No new aggregate accuracy score or visual verification.

## 14. Readable grouped differences (Milestone K)

Completed (2026-09-16): same-kind adjacent operations now form bounded groups,
ranked by operation count with stable alignment-order ties. Page and endpoint
discontinuities split groups. `--issue-limit` limits groups; each displayed group
retains complete occurrence details, bounded context and explicit omission
counts. Missing text and suspected movement remain distinct. See the grouping
contract in `docs/COMPARISON.md`. No alignment, metrics, dependency or conversion
behavior changed. L is ready to be requested; L/M have not been implemented.
Verification: 47 focused tests passed; full discovery reports 273 tests OK with
seven opt-in skips. All selected pilot counts and input hashes remained unchanged.
Grouped reports were inspected for the source-order/caption case; diff checks passed.

- Group adjacent operations into readable excerpts without changing underlying
  token counts or losing occurrence/page/line/span evidence.
- Show larger affected spans first using a documented deterministic ranking;
  call it size-based priority, not semantic importance or model confidence.
- Keep missing content and suspected movement distinct; do not relabel a moved
  passage as a verified loss. Preserve source order/location within each group.
- Bound group/context display, disclose omitted groups and retain access to
  occurrence details. Define how `--issue-limit` interacts with grouping.
- Verify split-page passages, repeated text, mixed operations and stable tie
  ordering. Revisit I's report-readability findings; update both READMEs and the
  contract, run focused/full tests and inspect the diff.

## 15. Structured comparison JSON (Milestone L)

Completed (2026-09-16): `--json-report PATH` adds schema `1.0` alongside the
default Markdown report. Both serializers share one typed result and one
alignment/image inspection. JSON retains complete token and operation evidence,
nullable rates, coverage, settings, images and group omission metadata. Paths
are preflighted together and created exclusively; independent write failures
return exit 1 while retaining successful outputs and reporting possible partial
files. The schema and recovery contract are in `docs/COMPARISON_JSON.md`.
Review also reproduced and fixed nested inline HTML template leakage, hidden
image inventory and custom-tag prefix handling. No dependency or network access
was added. M is ready to be requested and has not been implemented.
Verification: 57 focused tests passed; full discovery reports 283 tests OK with
seven opt-in skips. Python 3.10 syntax checks passed. The selected pilot's JSON
accounts for every occurrence once; Markdown matches K and input hashes are
unchanged. Final diff checks and the cumulative review are documented in
`docs/COMPARISON_REVIEW.md`.

- Add opt-in machine-readable comparison output with a documented versioned
  schema. Preserve the existing default Markdown report and exit behavior.
- Include settings, coverage/unverified pages, count denominators, nullable
  rates, source/target evidence, image diagnostics and truncation metadata.
- Build Markdown and JSON from the same typed comparison result, avoiding a
  second alignment or scraping the rendered report. State whether occurrence
  details are complete or bounded; never silently omit evidence.
- Preserve input/output collision checks and exclusive creation; define visible
  partial-success behavior if one of several requested report writes fails.
- Test schema facts, Unicode, empty denominators, consistency with Markdown,
  deterministic ordering and write errors. Update both READMEs and the contract;
  run focused/full tests and inspect the diff.

## 16. Batch comparison (Milestone M)

Completed (2026-09-16): `compare-batch` reads strict versioned explicit pair lists,
resolves paths relative to the list, preflights all planned output collisions,
and isolates missing/invalid inputs and pair execution failures. Sequential
processing reuses single-comparison renderers and exclusive writes. Pair Markdown
and JSON reports plus both batch summaries distinguish execution failure from
differences and unverified pages. No models, network access or dependencies were
added. See `docs/COMPARISON_BATCH.md` for schema and partial-success semantics.
Focused tests: 37 passed; full discovery: 293 tests OK with seven opt-in skips.
The 12 acquired pilot pairs produced JSON identical to saved single-comparison
results, with unchanged input hashes. No integration-queue work was started.

- Follow L with explicit PDF/Markdown pair-list input; define a versioned format
  and relative-path base. Do not guess pairing from ambiguous basenames.
- Detect duplicate pairs, missing inputs and report-name collisions before
  writing. Preserve all inputs and existing output files.
- Isolate pair failures, continue independent pairs and provide an aggregate
  Markdown/JSON summary. Distinguish failed comparisons from successful reports
  containing differences or unverified evidence.
- Reuse single-pair semantics and avoid models, network access or automatic
  conversion. Keep bounded processing and deterministic order; parallelism is
  not required for this milestone.
- Test mixed success/failure, duplicate stems in different folders, Unicode and
  Windows paths. Document commands in both READMEs and the comparison contract;
  run focused/full tests and inspect the diff.

## 17. Offline comparison evaluation adapter (Milestone N)

Implement the requested development-only adapter without extending the product CLI.

Completed (2026-09-16): added `development/evaluate_comparison.py`, strict
manifest/fact semantics, pre/post SHA-256 verification, complete structured
comparison evidence, preserved IDs/provenance, and explicit pass/fail/error
reports with exclusive output creation. Original pinned controls cover retained,
deleted, repeated and moved content. The existing local pilot 0180 and its three
controlled variants passed ten reviewed facts; this is not an accuracy score.
Eleven adapter tests and 29 focused adapter/JSON/batch tests passed; full discovery
reports 304 tests OK with seven opt-in skips. Python 3.10 syntax and diff checks
passed. No network, model or dependency changes occurred. Pending M work was
preserved; wider corpus acquisition and upstream evaluators remain unstarted.

Follow-up review (2026-09-17): fixed overlapping repeated ordering anchors being
mistaken for a unique anchor. Original source/target regression cases failed
before the fix; count facts retain disjoint semantics. Twelve focused adapter
tests and full discovery (305 tests OK, seven opt-in skips) passed. All twenty
O facts retain their original results. See the review section in
[coverage results](COMPARISON_COVERAGE_RESULTS.md).

- Read a versioned local manifest of explicit PDF/Markdown pairs, SHA-256 hashes,
  dataset revision, sample ID, provenance and document terms. Preserve fact IDs
  and reference provenance; do not infer upstream annotation semantics.
- Verify inputs before and after comparison. Hash mismatch or unavailable inputs
  are evaluation errors, not passed/failed content facts. Keep external material
  in ignored storage and introduce no downloads, models or dependencies.
- Reuse the structured comparison result and its complete occurrences. Support
  explicitly specified normalized token-sequence counts, unambiguous sequence
  ordering and expected operation types over exact source/target character spans.
  Keep source page mapping explicit. Unknown or ambiguous facts must fail visibly.
- Report per-fact pass/fail/error with observed evidence, IDs, provenance and
  settings. Separate natural pairs from controlled mutations and regression
  expectations from independent reference facts. No global accuracy score.
- Provide original redistributable fixtures for retained/deleted/repeated/moved
  text and failed expectations. Exercise the already-acquired local pilot with
  reviewed facts; do not copy external prose into Git or bless current output
  automatically as reference truth.
- Preserve existing outputs through exclusive creation; document reproducible
  commands, schema, limitations, focused/full tests and the pilot result.

## 18. Broader real-document coverage (Milestone O)

Completed after explicit bounded network/acquisition approval. See
[supplementary coverage results](COMPARISON_COVERAGE_RESULTS.md) for pinned
sources, hashes, visual review, independently selected facts and reproduction.
Four natural pairs and a separate synthetic OCR control were evaluated. Turkish,
natural-scan and complete image-package coverage remain explicit gaps.

- Target a small supplementary selection of at most eight real PDF/Markdown
  pairs, with at most 100 MiB total downloaded material including references and
  assets. Prefer Turkish text, natural scans, formulas, multiple pages and
  complete local image packages; record unavailable categories honestly.
- Review candidate source terms and exact endpoint/page correspondence before
  acquisition. Record URLs, pinned revisions, sample IDs, hashes, provenance and
  terms. Prefer existing predictions; do not install or run another converter.
- Keep all acquired material ignored. Do not upload repository or user document
  contents. No models, packages or upstream evaluation runner are required.
- Specify a few independently reviewed facts before interpreting comparator
  output. Use N's adapter where its semantics apply; leave visual/table/math
  semantics unresolved rather than translating them into misleading text facts.
- Visually review selected source pages, separate source-layer problems from
  conversion differences, and include retained as well as missing facts.
  Source facts on textless pages must remain unverified; target-only facts are
  not OCR accuracy evidence.
- Preserve hashes and previous pilot inputs. Document commands, selected facts,
  observed errors, unresolved findings and coverage gaps. No aggregate accuracy
  claim and no benchmark numbers in either README.
- Convert any confirmed product regression into a small original reproduction
  before proposing a separately scoped implementation change. This milestone
  evaluates coverage; it does not implicitly add metrics or dependencies.

Local inventory: the existing pilot contains twelve single-page pairs; original
fixtures cover controlled Turkish/scanned/formula cases, not natural coverage.
The local NIST source has no corresponding Markdown in this workspace. Temporary
commit-validation fixture copies are not additional independent samples.

Outcome: selected missing diagram/formula text was confirmed; a failed exact
sequence fact was traced to source line-end hyphenation, while alignment joined
the occurrence correctly. Textless source evidence remained unverified. No new
product regression or dependency was justified. The bounded evaluation is done;
additional coverage or implementation needs a separately requested scope.

The user subsequently requested continued research on the missing categories.
The research first pinned OCRTurk and a historical scanned-booklet benchmark;
the acquisition ceiling stayed unchanged. The resulting evaluations are below.

Follow-up result: OCRTurk `data_14` now adds one reviewed natural Turkish pair
with all four referenced images. Six selected text facts passed under `turkic`;
image files decode, while visual/math correctness remains outside the metric.
This brought the selection to six pairs including the synthetic OCR control.
The water-department scan candidate was not acquired because its source terms
and exact page correspondence remained unresolved. No product code or new
dependency was needed. See the Turkish follow-up section in the coverage report.

Natural-scan follow-up: evaluated the 1878 Gettysburg booklet with its existing
archival OCR text copied byte-for-byte to a Markdown extension. Four of eight
independently selected source/target facts failed because both endpoints share
two OCR errors; endpoint agreement is not OCR accuracy. Seven cumulative pairs
remain below the approved ceiling. The source has an OCR layer, so natural scans
without text and broader scan diversity remain gaps. No product change was
justified; see the natural-scan section of the coverage report.

## Integration queue after the current comparison milestones

This queue records justified candidates; it does not start another milestone
or authorize package/corpus downloads. See `docs/COMPARISON_INTEGRATIONS.md`.

1. **Completed within J:** adopted one source-mapped Markdown parser after
   direct-dependency approval and the source-offset regression gate.
2. **Completed in N:** a development-only adapter for already acquired,
   hash-verified endpoint pairs and explicit reference facts. It reuses structured
   results and preserves supplied IDs and terms. Additional datasets and new
   upstream fact semantics need separate scope and acquisition approval.
3. **Conditional research:** isolate `docling-eval` or selected `docling-metrics`
   components only when an independent table/text reference and a need for
   upstream-comparable scores exist. Prove Windows/offline installation first.
   Do not add a second converter, remote judge or default benchmark downloads.

Milestones K-O are complete. Remaining candidates require a separately requested
implementation scope; they do not start automatically.

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
8. Milestone H: independent PDF-to-Markdown comparison (section 11)
9. Milestone I: real-document comparison evaluation (section 12)
10. Milestone J: comparison reliability and Markdown support (section 13)
11. Milestone K: readable grouped differences (section 14)
12. Milestone L: structured comparison JSON (section 15)
13. Milestone M: batch comparison (section 16)
14. Milestone N: offline fact evaluation adapter (section 17)
15. Milestone O: broader real-document coverage (section 18)

Within each run, the agent should inspect the relevant code first, add failing
tests for the contract, implement the smallest cohesive change, run focused and
full tests, inspect the final diff, update documentation, and stop only at the
milestone's verifiable acceptance condition. It should ask for user input only
when work requires network/model downloads, destructive replacement, a new
runtime dependency, or a product decision not settled by this plan.
