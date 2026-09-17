# Independent comparison: first real-document pilot

Date: 2026-09-16. Milestone I evaluation is complete for the selected pilot;
this is not a complete benchmark or a claim of general accuracy. No comparator
behavior was changed. Known defects below remain open for the next work item.

J follow-up: the original results below are retained as historical evidence.
The direct alignment fixes now pass the duplication control (all original
occurrences matched, only surplus additions), preserve the removal/movement
controls and recover the eight moved hyphen joins in case 0008. Parser issues
remain pending. Recheck evidence is stored locally in `j-alignment-check.json`.

## Acquisition and reproducibility

The user authorized up to 12 PDF/Markdown pairs. Acquired exactly 12 PDF files,
their 12 existing Marker Markdown predictions, 12 reference Markdown files and
four source/license metadata files from
[OpenDataLoader benchmark revision 7af1d8f4d0c09f51ea1a5c6ba5f66e993286d109](https://github.com/opendataloader-project/opendataloader-bench/tree/7af1d8f4d0c09f51ea1a5c6ba5f66e993286d109).

Selection was fixed before reading scores: sorted PDF indices
`0,4,7,19,39,59,79,99,119,139,159,179`. This is a spread across filenames, not
random or statistically representative sampling. Exact case IDs are below.
The prediction directory establishes the producer name; the exact historical
Marker model/version/settings are not established by these downloaded files.
No converter, model or upstream evaluation package was installed or executed.

The pinned repository's `LICENSE` is Apache-2.0; its `THIRD_PARTY_NOTICES.md`
lists DP-Bench under MIT. The [Upstage dataset card](https://huggingface.co/datasets/upstage/dp-bench)
also declares MIT. These records are retained separately; they are not a claim
that all embedded source-document rights are the same as the code license.
All acquired content and page previews stay in ignored local storage.

Local root:
`pdfmd_output/comparison_evaluation/opendataloader-7af1d8f4d0c0/`.

- `source-tree.json`, `selection.json`, `acquisition.json`: fixed file inventory,
  source URLs, byte lengths, Git blob hashes and SHA-256 hashes. Every downloaded
  file matched both the listed Git blob hash and byte length.
- `upstream/`: original directory layout, including prediction and reference
  Markdown. References assist review; the comparator reads only PDF/prediction.
- `reports/`, `observations.json`: actual direct reports, settings, per-case
  counts, unverified pages, image diagnostics, report hashes and code fingerprint.
- `previews/`: locally rendered PDF pages and a contact sheet. These were used
  for visual review, not sent to an external document-processing service.
- `controls/`: separate retained/deleted/duplicated/moved Markdown copies and
  their reports. `observations.json` records the failed expected invariant.
- `acquire.py`, `evaluate.py`, `controls.py`: development notebook scripts,
  outside the product and ordinary test suite. They preserve existing files;
  evaluation reruns need fresh output paths. The duplication assertion in
  `controls.py` intentionally remains failing against the current comparator.

Offline invocation for any acquired case, with a fresh report path:

```powershell
.\pdf-receipt.bat compare pdfmd_output\comparison_evaluation\opendataloader-7af1d8f4d0c0\upstream\pdfs\01030000000001.pdf pdfmd_output\comparison_evaluation\opendataloader-7af1d8f4d0c0\upstream\prediction\marker\markdown\01030000000001.md --report pdfmd_output\comparison_evaluation\opendataloader-7af1d8f4d0c0\review-rerun.md
```

Settings: Unicode case profile and 50 representative issues. The source-code
fingerprint is recorded in `observations.json`; it hashes sorted
`src/pdf_receipt/*.py` using filename UTF-8, NUL, file bytes, NUL for each file.
The working tree included pending G/H implementation. All acquired input hashes
were checked again after reports, preview generation and controlled edits;
the originals are unchanged. Full upstream leaderboard scores were not computed.

## Reviewed cases

All cases are single-page PDF slices with an available text layer. Page numbers
below mean physical PDF page 1, not the printed page label. All page previews
were inspected as a contact sheet; cases 01, 08, 80, 120 and 140 also received
larger page review. This is representative issue review, not verification of
every token or every table cell. Case IDs share prefix `0103000000`.

| ID suffix | Visible content | Reviewed finding and interpretation |
| --- | --- | --- |
| 0001 | Prose, heading, footnote | The footnote includes literal angle-bracket text present in the prediction but masked as HTML by our tokenizer: confirmed parser false loss. An extra text-layer `UN` token is not visible in the reviewed page: suspect source-layer content, not an established Markdown loss. |
| 0005 | Photos and captions | Caption text matches; two image targets are absent from the upstream prediction package. Artifact diagnostics are valid for the supplied files, but do not prove the original converter failed to export images. |
| 0008 | Two columns, figure and footnotes | Footnotes follow body text in Markdown but interrupt it in the PDF text stream. Reported order risks need source-order context. Some moved, line-end-hyphenated words appear as loss/addition even though their joined forms are retained: unresolved contextual matching defect. |
| 0020 | Prose with running header | Reported missing words belong to the running header and printed page label. This is a real endpoint omission, potentially intentional editorial removal; intent is not verified. |
| 0040 | Two-column report and chart | Report catches absent footer and chart labels. Chart image is referenced but unavailable, so image-based preservation cannot explain the losses. |
| 0060 | Charts and prose | Printed page label is absent. One referenced chart image is unavailable. Retained body text is not proof of chart-value fidelity. |
| 0080 | Decorative initial and large side heading | PDF shows the full initial word while Markdown starts without its decorative initial. Another word is visibly mistyped. The report flags discrepancies, but pairs one substitution with a page-number token; its individual correspondence should not be treated as a causal explanation. Heading order also differs from text-stream order. |
| 0100 | Chart and caption/prose | Missing occurrences are the footer label and page number. The chart image is unavailable. Chart values have no verified independent comparison. |
| 0120 | Biology worksheet and table | Retained table text matches; header and page number are omitted. The visible table contains images absent from the Markdown, which has no image references. Our image-link check cannot discover this kind of missing image. |
| 0140 | Prose around pie charts | PDF text extraction puts captions before prose; Markdown places them near the related paragraphs, consistent with the page layout. Order flags do not establish an incorrect conversion. Chart text visible in the page/reference is not fully represented in the extracted PDF text, so an endpoint text report cannot detect all omissions. |
| 0160 | Boxed instructional list | Reviewed missing occurrences are the footer/page label. Useful retained-list control for later parser changes. |
| 0180 | Revision history and table | All text tokens match in the unmodified pair. Used as the retained and controlled-mutation baseline; table structure is still not independently scored. |

Across the acquired cases, the eight referenced image files are not present in
the pinned Marker prediction tree. No unavailable assets were silently replaced
or fetched from inferred URLs. The full tree inventory distinguishes incomplete
published artifacts from a broken local download.

## Controlled findings and missed expectations

On case 0180, the original prediction has 174 source and target tokens, all
accepted. Its first prose paragraph has 63 tokens. Separate copies produced:

| Edit | Expected | Observed |
| --- | --- | --- |
| Remove that paragraph | Its occurrences become missing | 63 missing, no additions or order risks: passed |
| Duplicate that paragraph in place | 63 additions; original text remains matched in order | 63 additions, but only 123 accepted matches and 51 spurious order risks: **failed** |
| Move that paragraph to the end | Same token totals; movement flagged | 63 order risks and no losses/additions: passed for this control |

The duplication failure preserves the global count identities but changes the
interpretation of unchanged text. This is an alignment defect to reproduce in
the unit suite before fixing; replacing the Markdown parser alone cannot solve
it. Do not weaken the expected unchanged-order condition to make the probe pass.

For the angle-bracket failure, an original, redistributable minimal example is
`<TaskName 125-386>`. The current tokenizer drops both visible tokens. The
already-installed `markdown-it-py` CommonMark renderer treats it as literal text,
which agrees with the reviewed source/prediction footnote. This does not require
embedding copyrighted benchmark text in a regression fixture.

Additional original diagnostic probes found existing documented parser gaps:

- `A &amp; B` introduces a spurious `amp` token.
- Inline code containing `[alpha](beta)` loses `beta`, despite code content
  being part of the comparator's visible-text contract.
- A reference-style image contributes its alt/label words and is not inventoried
  as an image target. These probes are controls, not observations of their
  frequency in the selected real documents.

No fix was applied during I. The full product suite was not rerun because no
product code or tests changed. Offline comparisons, input hash verification and
the controlled probes were run; the failing duplication probe is an evaluation
result, not a passing test. Diff whitespace checks passed.

## Coverage and next work

The sample covers prose, multi-column layouts, captions, footnotes, running
headers, charts, a decorative initial and tables. It does not establish behavior
on natural Turkish documents, image-only scans, equations, complete image
packages or long/multi-page documents. Existing original fixtures cover some
of these as controls; they do not fill the real-document coverage gaps. The
already-local NIST PDF still has no paired Markdown in this workspace.

There is no aggregate accuracy claim. Cases 0160/0180 remain unmodified regression
controls, but have already been inspected and are not a blind held-out set.
Additional independent samples are needed before generalization claims.

Priorities for J: reproduce the paragraph-duplication error, then evaluate a
proper Markdown parser while preserving source offsets. Track moved-hyphen
behavior explicitly. K should group contextual evidence and distinguish
source-order uncertainty from established content omissions. No automatic
header-removal exemptions or visual-image accuracy claims should be added.

See [integration assessment](COMPARISON_INTEGRATIONS.md) for concrete reuse
options and the boundary between development benchmarks and runtime behavior.

## J regression recheck

The earlier observations above describe I's original implementation. J's final
source-mapped parser was rechecked offline against all 12 acquired predictions
and their references; acquisition hashes remained unchanged. Separate reports
and counts are retained in the ignored pilot directory's `j-parser-recheck/`.
Case 0001 now retains all 441 Markdown occurrences, with only the source's
separate `UN` occurrence missing. The literal angle-bracket false loss is gone.
Case 0008 retains the contextual moved joins as order risks; case 0180 still
matches all 174 occurrences. Original regression tests also cover controlled
duplication/removal, entities, code, reference images and precise raw positions.
These checks do not close the pilot's visual or dataset coverage gaps.

## K report review

All 12 selected pairs were rendered again offline into the ignored
`k-group-recheck/` directory. Operation counts exactly match J's saved results;
the grouping retains every non-match operation once and input hashes are intact.
Case 0140 now presents its 56 operations in seven groups, including caption
excerpts explicitly labeled suspected movement rather than verified loss.
The group and occurrence locations were inspected against the prior findings.
Case 0008 still has fragmented endpoint correspondence: its 206 operations form
85 groups, of which the default report shows 50 and discloses the remainder.
This is a known readability limit of faithful adjacency grouping; no rematching
or unsupported paragraph-level claim was added to make the report look simpler.
For this local case, rerun `compare` with `--issue-limit 85 --report new-report.md`
to retain all group details. Ordinary output-file protection still applies.

## N fact adapter check

The already-local 0180 natural prediction and three controlled variants were
evaluated with explicit opening-sequence counts, ordering and source-span
operation expectations. Ten facts passed across four cases; both endpoint
hashes were verified before and after each comparison. Input terms and the
pinned acquisition revision remain recorded in the ignored `n-facts.json`.
The final report is `n-evaluation-final.json` beside that manifest.

These facts are locally authored from the reviewed pilot controls, not imported
upstream annotations. IDs use a `local:` prefix to preserve that distinction.
No source prose was copied into Git, new corpus downloaded, or aggregate accuracy
claim made. The original checked-in adapter controls can run on a fresh clone;
the external pilot still requires the previously acquired local files. See
[the adapter contract](COMPARISON_ADAPTER.md) for reproduction and limitations.
