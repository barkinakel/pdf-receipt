# Comparison evaluation protocol

Milestone I; source review date: 2026-09-16. This is a development evaluation,
not an additional application command. Its historical plan is in sections 12-16
of [the ordered plan](TODO.md). Those changes are complete; the development-only
[fact adapter](COMPARISON_ADAPTER.md) implements the follow-up in section 17.
The bounded section 18 evaluation is also complete; see
[supplementary coverage results](COMPARISON_COVERAGE_RESULTS.md) for sources,
reviewed facts, preserved input hashes and remaining coverage gaps.

## Which benchmark fits?

There is no single interchangeable score in the sources below. They assess
different properties against different annotations. Our direct comparison uses
the source PDF text layer; an upstream benchmark typically uses annotated facts
or reference content. Our transfer rate is not an upstream benchmark score.

| Source | Evidence supplied and intended use | Acquisition considerations |
| --- | --- | --- |
| [OmniDocBench](https://github.com/opendatalab/OmniDocBench) / [dataset](https://huggingface.co/datasets/opendatalab/OmniDocBench) | Document pages with element text, formulas, tables and reading-order annotations; useful for diverse difficult layouts. | The dataset card restricts use to noncommercial research. It distinguishes original PDF slices from image-derived PDFs; inspect text layers before choosing samples. Pin both data and evaluator revisions. |
| [olmOCR-Bench](https://github.com/allenai/olmocr/blob/main/olmocr/bench/README.md) / [dataset](https://huggingface.co/datasets/allenai/olmOCR-bench) | PDF samples and pass/fail facts for text presence/absence, order, tables and math. Useful inspiration for explicit, reviewable checks. | The dataset card declares ODC-BY; inspect source-document terms separately. Facts are not a complete reference Markdown transcription. Its header-removal expectations are not automatically our comparator's policy. |
| [OpenDataLoader benchmark](https://github.com/opendataloader-project/opendataloader-bench) | Repository exposes PDFs, ground truth and predictions for several engines. Promising first source of existing endpoint pairs without installing those engines. | Confirm that selected predictions are actual Markdown and correspond to the exact PDF/page range; an evaluation JSON alone is insufficient. Check [third-party notices](https://github.com/opendataloader-project/opendataloader-bench/blob/main/THIRD_PARTY_NOTICES.md) and per-source terms. |
| [Upstage DP-Bench](https://huggingface.co/datasets/upstage/dp-bench) / [Docling-eval](https://github.com/docling-project/docling-eval) | Docling-eval supports DP-Bench and OmniDocBench alongside layout/table datasets. This is evidence of upstream evaluation practice, not a required dependency. | Use the document-parsing dataset under `upstage`, not unrelated similarly named DP-Bench projects. Keep any upstream runner in a separate, explicitly approved environment. |

The practical first choice is a small selection of existing pairs from
OpenDataLoader's repository, if file formats and terms check out. Use
OmniDocBench annotations for harder cases later, and olmOCR-style facts to make
each review concrete. Do not download entire corpora or install several engines
just to exercise a producer-independent comparison command.

The initial research inspected public documentation only. After explicit user
approval, the selected OpenDataLoader pilot was acquired and evaluated locally;
see [results and coverage gaps](COMPARISON_PILOT_RESULTS.md). No upstream runner
was executed and no leaderboard scores were reproduced. Integration options
are assessed in [Comparison integrations](COMPARISON_INTEGRATIONS.md).

## Pilot selection

Start with about a dozen pairs, small enough to inspect individually. This is
a target sample size, not a statistical adequacy claim. Include these features:

- Ordinary prose and headings, with a known retained and missing passage.
- Multi-column reading order and passages moved a long distance.
- Repeated headers/footers, footnotes and repeated body text across pages.
- Tables, equations and local images; record unsupported visual checks.
- Turkish casing/diacritics and at least one existing non-Docling Markdown.
- Image-only scans, mixed text/image pages and unreliable text-layer order.
- Long documents, including the already-local NIST PDF if a corresponding
  Markdown becomes available. Do not modify or regenerate the NIST source.

One document may cover multiple categories. Mark missing categories explicitly.
Original project fixtures are useful controls but do not replace real documents.
User-owned documents can fill coverage gaps locally; never commit their content
or identifying metadata. Public availability alone does not grant redistribution.

Prefer source PDFs that retain their original text layer for direct text checks.
An image wrapped in a PDF remains useful for testing the honest "unverified"
result, but cannot establish OCR accuracy with this command. Do not silently add
OCR text to make a benchmark input appear comparable.

## Case record template

Keep full records and files under ignored
`pdfmd_output/comparison_evaluation/<run-id>/`. Publish only sanitized findings
and redistributable original fixtures. A record should contain:

```text
Case ID:
Source URL / dataset ID / pinned revision / sample ID:
Data terms and attribution source:
PDF relative path / SHA-256 / page range:
Markdown relative path / SHA-256 / encoding:
Image asset paths / hashes, where relevant:
Markdown origin: unknown | independently authored | existing tool output
Producer/version/settings, if actually known (optional):
Reference facts and how independently established:
Text-layer state: present | mixed | absent | suspect
Features covered:
Comparison command / code revision and dirty-state fingerprint:
Report path / hash:
Reviewed PDF page and Markdown line/span:
Finding classification and supporting evidence:
Known facts missed by the report:
Unreviewed / unresolved findings:
Input hashes after the run:
Follow-up issue and reproduction:
```

Review findings as **true content difference**, **parser artifact**,
**source-layer problem**, **intentional editorial change**, or **unresolved**.
Keep upstream fact IDs and page mappings when available. Do not decide that
the comparator is right merely because it agrees with its own PDF extractor.
Visual inspection and independently specified facts establish the reviewed scope.

Alongside natural outputs, create separate controlled copies with a known
deletion, duplication and movement. Preserve originals and record each edit.
Such controls measure detection of those edits; they do not measure how often
real converters make them. Include known retained facts to detect false alarms.

## Running the existing command

For each acquired pair, use explicit paths and a new report name:

```powershell
.\pdf-receipt.bat compare "path\source.pdf" "path\prediction.md" --report "pdfmd_output\comparison_evaluation\run-id\case-report.md"
```

Create the run folder first. Use the existing `--case-profile` and `--issue-limit`
options as needed and record their values. Inspect images relative to the
original Markdown directory; moving only the Markdown can manufacture broken
links. Differences return success, so an exit code alone is not a quality check.
Do not run a conversion when an existing prediction is available.

Report reviewed findings, missed known facts and unresolved coverage separately.
Do not tune parser behavior on every sample: reserve some unmodified pairs to
recheck later changes. Record timings and sizes in evaluation notes or handoffs,
never either README. Completion requires real-document review and actionable
findings; a runnable protocol alone does not complete Milestone I.

## Initial offline pilot (2026-09-16)

Status: control exercise completed; real-document sample not yet acquired.
The only pre-existing converted Markdown located in the workspace was the
Milestone G formula baseline. The local NIST PDF was present without a matching
Markdown. No conversion or external acquisition was performed.

Used the original project formula fixture and the existing baseline output;
this is synthetic source material, not evidence of real-world accuracy. The
baseline manifest records fast profile, formula disabled, Docling 2.124.0.
Comparison itself used only the PDF and Markdown. The baseline omits equation
content; inspecting its missing-token contexts points to those equation spans.
This validates missing textual occurrences, not equation semantics.

- Existing output retained all prose tokens in this control.
- Removing the first prose sentence in a separate copy increased missing
  occurrences by exactly the number of tokens in that sentence.
- Duplicating that sentence in another copy produced the corresponding surplus
  additions without increasing accepted source matches.
- The original scanned-page fixture remained explicitly unverified with an
  empty source denominator.
- Original PDF and Markdown hashes were unchanged after the exercise.

Reports and development-only observations are in ignored
`pdfmd_output/comparison_evaluation/local-pilot-2rr1txc0/`. Its observations JSON
is a pilot notebook artifact, not the planned public JSON report feature.
It records settings, input/report hashes and the fingerprint of the working
application source. No pilot artifact or third-party document is added to Git.

Reproduce the baseline using a new report target:

```powershell
.\pdf-receipt.bat compare tests\fixtures\formulas\formula_equations.pdf pdfmd_output\milestone_g_baseline\formula_equations.md --report pdfmd_output\comparison_evaluation\new-run\baseline-report.md
```

Create `new-run` first. For the two controlled copies, remove or duplicate only
the first prose sentence in that existing Markdown, leaving the original alone,
then compare each copy with the same PDF. An equivalent independently authored
prose Markdown can be used if the ignored baseline is unavailable, but must be
recorded as a different case.

Follow-up evidence: the equation omission appears as several individual token
entries. Grouped excerpts in K should make such findings easier to inspect
without pretending to recognize the equation. The pilot does not exercise J's
reference-image/entity cases, natural reading-order failures or non-Docling
outputs. Those gaps and real-document visual review remain open.
