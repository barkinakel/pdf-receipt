# Offline fact evaluation adapter

Milestone N is development tooling, not another conversion engine or product
command. It evaluates explicitly authored facts against complete structured
comparison evidence. No downloads, models, additional dependencies or external
services are used. Source data stays local; the adapter never discovers or
downloads a corpus automatically.

## Run the original controls

From the repository root, choose a new report path with an existing parent:

```powershell
.venv\Scripts\python.exe development/evaluate_comparison.py tests/fixtures/comparison_evaluation/manifest.json --report pdfmd_output/original-facts.json
```

The checked-in manifest and Markdown are original MIT-licensed material. They
reuse the original formula PDF and examine only its title and opening sentence.
The rest of the PDF is intentionally not transcribed. These are selected facts,
not whole-document fidelity assertions. Fixtures cover retention, removal,
duplication and movement; unit tests separately exercise deliberately false
expectations and evaluation errors. Fixture Markdown has LF line endings pinned
in `.gitattributes` so Windows checkout preserves its declared SHA-256.

## Manifest schema 1.0

UTF-8 (optional BOM) JSON has exactly `schema_version: "1.0"`, `case_profile`
(`unicode` or `turkic`), and a nonempty `cases` array. Duplicate JSON keys, extra
fields, unknown versions, duplicate case IDs or duplicate fact IDs within a case
are rejected before evaluation. See the checked-in manifest for a full example.

Every case requires:

- Nonempty strings `id`, `dataset`, `revision`, `sample_id`, `terms`, `provenance`.
  Preserve actual upstream fact/sample IDs if importing annotations. When facts
  are local, label them as local; never invent upstream attribution.
- `category`: `natural` or `controlled`. A modified target is controlled.
- `pdf`, `markdown`: objects with `path` and lowercase `sha256` hex digest.
  Relative paths use the manifest directory. Absolute paths and Unicode paths
  are accepted. Ambiguous Windows drive/root-relative paths are rejected.
- Nonempty `facts`: explicit fact objects described below.

The terms/provenance fields record the caller's evidence and review. They do not
automatically verify licenses or turn a reference into ground truth. Additional
reference files are not read or verified by this version. PDF/Markdown bytes are
hashed before comparison and again after facts are evaluated. Missing files,
hash mismatches or comparison errors invalidate all facts for that case; other
cases continue. A case is not accepted against silently changed source material.

### Fact semantics

Every fact requires `id`, `kind`, `basis`, `provenance`, `side`, `page` plus its
kind-specific fields. `basis` is `independent` for independently authored content
expectations or `regression` for expected comparator behavior. Do not generate
passing expectations automatically from the comparator's current output.
`side` is `source` or `target`; source requires an explicit one-based physical PDF
page, target requires `page: null`. Printed page labels are not interpreted.

| Kind | Additional fields | Meaning |
| --- | --- | --- |
| `sequence_count` | `tokens`: nonempty string array; `count`: nonnegative integer | Count exact contiguous sequences of normalized tokens, greedily without overlap. A token cannot satisfy multiple instances. Count zero asserts absence on that side/page. |
| `sequence_order` | `before`, `after`: nonempty string arrays | Each anchor must occur exactly once across all possible starts, including overlapping occurrences, and the entire before sequence must precede the after sequence without overlap. A missing/reversed anchor fails; repeated anchors are ambiguous and produce an error. |
| `operation_span` | `span`: `[start,end]`; `operation`; positive `count` | All occurrences intersecting this raw character interval must have the specified operation, and exactly count occurrences must exist. Boundaries must coincide with the first/last token boundaries. Source spans are page-local; target spans are file-local after optional BOM decoding. |

Sequence arrays contain **explicit normalized token strings**, not prose to be
silently re-tokenized or fuzzy-matched. Unicode/Turkic casing follows the chosen
comparison profile. The adapter does not infer page alignment, remove headers,
compare table trees or judge equation meaning. Source facts on pages without
comparable text are errors/unverified, even an assertion of absence. Target facts
only establish properties of Markdown, not OCR accuracy.

For example, the anchor `echo echo` occurs at two overlapping positions in
`echo echo echo end`, so ordering it before `end` is ambiguous. A sequence-count
fact still counts one disjoint occurrence. Output settings distinguish the
count policy (`sequence_matching`) from ordering-anchor uniqueness
(`order_anchor_matching: exact_all_starts_unique`). Overlapping anchor candidates
are diagnostic evidence, not additional accepted token matches.

Operation names are `match`, `deletion`, `insertion`, `substitution`, `order_risk`.
Expected operation types are regression contracts, not independent accuracy
metrics. Facts are independent assertions and may refer to the same evidence;
they do not allocate matches or change the comparator's one-to-one accounting.

## Output and failures

The single JSON report has `schema_version: "1.0"`,
`report_type: "comparison_evaluation"`, `case_profile`, `settings`, `limits` and
ordered `cases`. Each case contains unchanged metadata, `status`,
`inputs_verified`, `facts` and nullable `error`. Each fact preserves `id`, `basis`,
`provenance`, the complete `expected` fact, `status`, nullable `observed` and `error`.
Observed evidence includes token indexes and raw/normalized text, spans and
page/line evidence; operation facts also include complete relevant operations.

Statuses distinguish `pass`, `fail` (an evaluated expectation disagrees) and
`error` (unverified inputs, unsupported or ambiguous evidence, execution failure).
A case is error if any fact errors, otherwise fail if any fails, otherwise pass.
No aggregate accuracy, leaderboard score or implied full-document verification is
reported. Output creation is exclusive; existing outputs and input collisions
are refused. A failed write may leave a partial file; choose a new report path.
Exit 0 means all facts passed; exit 1 means a fail/error or read/write failure;
invalid CLI syntax returns 2.

Cases run sequentially, retaining report evidence and one document comparison at
a time. Matching is exact and reports are built in memory; large corpora or many
broad facts can consume substantial memory. This is not a streaming evaluator.

## Existing local pilot

The already-acquired OpenDataLoader sample `01030000000180` and its previously
created deletion/duplication/movement controls were evaluated using local facts
from the reviewed pilot. The local manifest `n-facts.json` records the pinned
dataset revision, hashes, original terms and locally assigned fact IDs. No
upstream fact schema or evaluator was imported and no external prose was copied
into Git. The first five opening-paragraph tokens provide a bounded location
check; whole-paragraph reliability remains covered by earlier regressions.

```powershell
.venv\Scripts\python.exe development/evaluate_comparison.py pdfmd_output/comparison_evaluation/opendataloader-7af1d8f4d0c0/n-facts.json --report pdfmd_output/pilot-facts-rerun.json
```

The local pilot manifest is intentionally ignored and requires the previously
authorized acquisition; it is not available in a fresh clone. Use the original
checked-in controls there. [Milestone O](COMPARISON_COVERAGE_RESULTS.md) now adds
reviewed natural multi-page/formula examples and demonstrates the distinction
between exact sequence facts and contextual hyphen alignment. Turkish, natural
scan and complete image-package coverage remain open; upstream evaluators are
still conditional future work.
