# Integration assessment

Reviewed 2026-09-16 during Milestone I; parser adoption completed during J after
explicit direct-dependency approval. Other entries remain recommendations. The approved
benchmark download did not authorize package/model installation or a new
conversion engine. See [pilot evidence](COMPARISON_PILOT_RESULTS.md).

Milestone O's [supplementary evaluation](COMPARISON_COVERAGE_RESULTS.md) used the
existing batch and fact adapter successfully. Its unresolved visual/table/math
questions do not have independent references yet, so they do not justify adding
an upstream metric package. Integration remains conditional on that evidence.

## Adopted in J: a source-mapped Markdown parser

The local environment already contains `markdown-it-py 4.2.0` (required by Rich)
and `marko 2.2.4` (required by the installed Docling standard dependencies).
J declares `markdown-it-py>=4.2,<5` directly with user approval. No installation
or download was necessary. `marko` is not imported by the comparator.

[`markdown-it-py`](https://markdown-it-py.readthedocs.io/en/latest/using.html)
exposes parsed Markdown tokens and configurable rules. It is the first candidate
to prototype because the locally installed parser correctly distinguishes the
literal angle-bracket example from HTML, decodes entities and keeps inline code
separate. Compare `marko` before deciding; do not integrate both without a need.

This is not a drop-in replacement for our evidence tokenizer:

- Parser syntax tokens are not our one-to-one word occurrences.
- Its documented [source map](https://markdown-it-py.readthedocs.io/en/latest/api/markdown_it.token.html)
  uses line boundaries; exact raw inline character spans still need a verified
  mapping strategy, especially after entities, escapes and Unicode normalization.
- Define handling of HTML tables/images, math and reference targets explicitly.
  Do not render or execute untrusted HTML to extract comparison text.
- Preserve bounded alignment, immutable raw evidence, offline image checks and
  existing conversion behavior. Parser adoption must not silently redefine
  report metrics or explain missing tokens away.

Adoption gate: reproduce I's parser failures with original fixtures, prove
visible-text correctness and exact raw offsets, run the comparison and existing
conversion regressions, then declare one dependency if approved. The separate
paragraph-duplication alignment failure must be fixed independently.

## Recommended now: corpus and fact reuse in development

OpenDataLoader's existing PDF/prediction/reference files already served as local
evaluation inputs without importing its runner. Continue this form of reuse:
retain pinned revisions and hashes locally, turn confirmed defects into small
original fixtures, and keep annotated facts independent of the comparator.

The [olmOCR-Bench fact approach](https://github.com/allenai/olmocr/blob/main/olmocr/bench/README.md)
is useful for presence, absence and ordering controls. Any future adapter must
respect individual fact semantics and page mapping. Do not silently adopt its
header-removal expectations or treat a few passed facts as full accuracy.
Downloading this additional corpus would require separate authorization.

## Conditional: upstream evaluators in a development environment

[`docling-eval`](https://github.com/docling-project/docling-eval) and
[OmniDocBench](https://github.com/opendatalab/OmniDocBench) are candidates for
separate, opt-in annotated evaluation if we need upstream-comparable scores.
They belong in an isolated development environment with pinned evaluator/data
revisions, explicit downloads and recorded settings. Do not make ordinary
conversion or direct comparison depend on a benchmark environment.

The [`docling-metrics` monorepo](https://github.com/docling-project/docling-metrics)
offers separate text, table and layout packages. These may avoid implementing
established metrics ourselves when suitable ground truth exists. The reviewed
[text package](https://github.com/docling-project/docling-metrics/blob/main/packages/docling-metrics-text/pyproject.toml)
declares `evaluate` and NLTK; the
[table package](https://github.com/docling-project/docling-metrics/blob/main/packages/docling-metrics-table/pyproject.toml)
declares tree-edit and XML dependencies plus native build tooling. They are not
installed here. Check Windows wheels, Python support and offline resource needs
against an exact release before proposing installation.

TEDS compares table trees; it needs an independently established source table
structure. It cannot infer the correct table from an arbitrary PDF merely
because both files were supplied. Similarly, BLEU/edit-distance scores do not
replace our occurrence accounting, evidence locations or unverified-page policy.

## Not currently justified

- Embedding Marker/MinerU or another converter just to read their Markdown.
  The existing `compare` command already accepts their files.
- A remote OCR or LLM judge in the default path. This would change the local
  product contract and still would not create independent ground truth.
- A universal quality score assembled from unrelated benchmark metrics.
- Automatic benchmark downloads, model setup or dependency installation when
  running the CLI or ordinary tests.

The completed parser gate is described below. Milestones K-M are complete;
larger evaluators remain conditional research. The approved local fact adapter
is documented in [Milestone N](COMPARISON_ADAPTER.md).

## Queue decision during J

The user requested justified integrations be queued. Parser adoption is the
first candidate within J; an offline adapter for already acquired pairs/facts
follows structured output and batch milestones L/M. Larger upstream evaluators
remain conditional on suitable reference data and a concrete metric need.
See the integration queue in `docs/TODO.md`; no unrelated engine is scheduled.

Both locally installed parsers passed original probes for literal angle-bracket
text, entities, inline code, nested link labels, reference images and HTML
tables. `markdown-it-py` is preferred for its explicit rule interfaces and line
maps. The probe
record is in ignored `pdfmd_output/comparison_evaluation/j-parser-assessment.json`.
The approved adapter now captures block content while indentation state is
active, then records inline rule ranges before decoding/formatting. It preserves
the parser's interruption chains and maps CRLF/CR and entities back to original
characters. Source mapping errors are visible failures. Original fixtures cover
raw spans, repeated cells/labels, nested syntax, code and image references;
existing conversion tests retain their tokenizer. The adapter is tied to the
declared major version and must be regression-tested before upgrading it.
