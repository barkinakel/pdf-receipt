# Integration assessment

Milestone I identified a source-mapped Markdown parser as the first candidate for J.
Both markdown-it-py and marko are already installed transitively. Direct dependency
adoption requires explicit approval and original character-offset regression tests.
No package was installed or imported during this evaluation.

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
