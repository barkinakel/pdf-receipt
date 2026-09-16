# Comparison JSON contract

Schema version: `1.0`. This is independent endpoint evidence, not Docling JSON
or the conversion manifest. Enable it with an explicit new path:

```powershell
.\pdf-receipt.bat compare source.pdf existing.md --report comparison.md --json-report comparison.json
```

Markdown is still written, using its normal default path when `--report` is
absent. Both serializers use one immutable comparison result: alignment, metrics,
image checks and grouping are computed once. Neither output is parsed to create
the other. No models, network calls or new dependencies are required.

## Writes and failures

All requested paths are checked before comparison or writing. Inputs, existing
files (including symlinks), duplicate output paths and missing parent directories
are rejected with exit 1. Relative paths follow the same rules as `--report`.
Both strings are prepared before writing. Exclusive creation writes Markdown
first and JSON second; a file appearing after preflight is not replaced.

If either write fails, the other is still attempted. Successful paths are printed
and retained; failed paths and errors appear on stderr, and exit status is 1.
A failure during writing can leave a partial file. No output is deleted or rolled
back automatically. Retry with new paths. Differences and unverified pages alone
remain successful comparisons (exit 0); invalid arguments return exit 2.

## Schema

JSON is UTF-8 without a BOM. Unicode is retained; numbers are finite. There are
no timestamps or random IDs: the same result serializes deterministically.
The fields below are always present. Consumers should check `schema_version`
and tolerate additional fields in compatible minor versions. Incompatible
meaning/type changes require a new major version.

| Field | Type and meaning |
| --- | --- |
| `schema_version` | String, currently `1.0`. |
| `inputs` | `pdf_name`, `markdown_name`: display names, not absolute paths or hashes. |
| `settings` | `case_profile`, `lookahead_tokens`, `markdown_dialect`, `issue_limit`, `group_operation_limit`, `excerpt_character_limit`, `group_ranking`. Dialect: `commonmark+pipe_tables`; ranking: `operation_count_descending_then_alignment_order`. |
| `evidence_limits` | `source` explanation and false booleans `ocr_performed`, `visual_fidelity_verified`, `table_structure_verified`, `equation_meaning_verified`, `image_fidelity_verified`. |
| `coverage` | `page_count`, one-based `unverified_pages`, and ordered `pages`. Each page has `page`, `source_tokens`, and `counts` containing `match`, `deletion`, `substitution`, `order_risk`. No comparable tokens means unverified, not necessarily scanned. |
| `counts` | Nonnegative integers: `source_tokens`, `target_tokens`, `matches`, `normalized_matches`, `contextual_hyphen_matches`, `missing`, `added`, `substitutions`, `order_risks`. |
| `rates` | `accepted_transfer`, `loss`, `addition`: each has integer `numerator`, integer `denominator`, and numeric or null `value`. |
| `source_tokens`, `target_tokens` | Complete ordered occurrence arrays; see below. |
| `operations` | Complete alignment in original order, including matches; see below. |
| `displayed_groups` | Same selected, size-ranked groups as Markdown. Each has an operation `type` and ordered `operation_indexes` into the complete operations array. |
| `images` | All inventoried references in source order: one-based `line`, `target`, human-readable diagnostic `status`. Status may include system errors and is not a stable enum. No image bytes are embedded or remote targets fetched. |
| `truncation` | Completeness and display omissions; see below. |

Accounting identities:

```text
source_tokens = matches + missing + substitutions + order_risks
target_tokens = matches + added + substitutions + order_risks
matches = normalized_matches + contextual_hyphen_matches
```

Accepted transfer is matches/source. Loss is (missing + substitutions)/source.
Addition is (added + substitutions)/target. Zero denominators give `null`, never
NaN. These describe available text-layer evidence, not document accuracy.

### Occurrences and operations

Each token contains:

- `index`: zero-based position in its own token array, identifying one occurrence.
- `raw_text`, `normalized_text`: original spelling and comparison spelling.
- `span`: `{start, end}`, zero-based half-open character positions, page-local
  for source and file-local for target after optional BOM decoding.
- `page`: one-based PDF page for source; null for target.
- `line`: one-based original Markdown line for target; null for source.
- `joined_normalized_text`: optional contextual hyphen-join spelling or null.
- `line_end_hyphen_spans`: original character spans; `line_end_parts`: strings
  preserving the tokenizer's hyphenation evidence.

Each operation has zero-based `index`, `type` (`match`, `deletion`, `insertion`,
`substitution`, `order_risk`), `match_kind` (`normalized`, `line_end_hyphen_join`,
`unexplained`, `added`, `different`, `reordered`), and nullable
`source_index`/`target_index` references. Each occurrence is consumed once.
`source_context`/`target_context` are `{start, end}` half-open token-array ranges,
including alignment-gap context where an endpoint is absent. `hyphen_decisions`
contains `keep`/`join` decisions when applicable. Target-only additions have no
inferred PDF page.

### Completeness and size

`occurrence_details_complete` is true, `operations_omitted` is zero, and
`json_text_truncated` is false. All tokens and operations survive `--issue-limit`.
Group metadata includes `groups_total`, `groups_shown`, `groups_omitted`,
`markdown_difference_operations_shown` and `markdown_difference_operations_omitted`.
The latter concern non-match operations only. Excerpts are not exported; their
Markdown character cap does not truncate JSON raw evidence.

Complete evidence can make JSON substantially larger than the Markdown summary.
The serializer builds it in memory. This version does not stream, batch, embed
complete source files or verify visual accuracy. See [the comparison guide](COMPARISON.md)
for dialect and grouping limitations.
