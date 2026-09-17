# Batch comparison

Milestone M processes an explicit list of existing PDF/Markdown pairs without
conversion, models or network access. It never guesses pairs from filenames.

Create `pairs.json` (UTF-8, optional BOM):

```json
{
  "schema_version": "1.0",
  "pairs": [
    {"id": "invoice-a", "pdf": "originals/a.pdf", "markdown": "converted/a.md"},
    {"id": "invoice-b", "pdf": "other/a.pdf", "markdown": "other/a.md"}
  ]
}
```

Then select an existing output directory:

```powershell
New-Item -ItemType Directory comparison-results
.\pdf-receipt.bat compare-batch pairs.json --output-dir comparison-results
```

## Input contract

The top-level object requires exactly `schema_version` (`"1.0"`) and `pairs`
(a nonempty array). Each entry requires exactly `id`, `pdf`, `markdown`.
Unknown fields, duplicate JSON keys and unsupported versions are errors.
IDs contain 1-64 ASCII letters, digits, underscores or hyphens, starting with
a letter or digit, and must be unique ignoring case. Paths may contain Unicode.
IDs identify pairs and report names; they do not infer conversion provenance.

Relative pair paths are resolved against the pair-list directory, not the shell
directory. Absolute paths are accepted. Windows JSON paths can use forward
slashes or escaped backslashes. Drive-relative/root-relative Windows paths are
rejected as ambiguous. Tilde expansion is supported. Duplicate resolved endpoint
pairs are rejected even with different IDs. A PDF can be compared to different
Markdown files as separate explicit pairs.

CLI list/output paths follow the process working directory; the batch launcher
changes that directory to the repository. Use absolute paths when needed.
`--case-profile unicode|turkic` and positive `--issue-limit` (default 50) apply
to every pair, with the same meaning as single comparison.

## Preflight and isolation

The whole list is parsed and input existence/extensions checked before any
report is written. A missing or invalid input is recorded as a failed pair;
independent pairs continue. Invalid list structure, duplicate IDs/pairs, missing
output directory or any input/output/existing-file collision rejects the whole
batch before writes. Planned outputs are reserved even for invalid pairs.
All input paths and the pair-list path are protected against output collisions.

Processing is sequential in list order, with one comparison result in memory
at a time plus a compact per-pair summary. A read, parse, comparison or write
failure does not stop later pairs. Every file uses exclusive creation. A file
appearing after preflight is never overwritten. Successful outputs are retained;
a failed write may leave a partial file. Retry into a fresh output directory.

## Outputs and status

Every valid pair attempts `pair-<id>.md` and `pair-<id>.json`, using the same
single-comparison renderers and [JSON schema](COMPARISON_JSON.md). Local image
checks remain relative to the original Markdown directory. These reports have
complete counts and occurrence evidence under the single-pair limitations.

`batch_summary.md` links to successfully written reports and shows status,
differences, unverified pages and errors. `batch_summary.json` contains:

- `schema_version`: `"1.0"`; `report_type`: `"comparison_batch"`.
- `settings`: `case_profile`, `issue_limit`.
- `totals`: integer `pairs`, `succeeded`, `failed`; pairs = succeeded + failed.
- `evidence_limits`: an explanation, not an aggregate accuracy score.
- `pairs`: entries in input order. Each contains `id`, resolved `pdf`/`markdown`
  paths, `status` (`success` or `failed`), nullable `error`, nullable boolean
  `has_differences`, nullable `unverified_pages`, nullable `counts`, and `reports`.
  Counts include source/target tokens, missing, added, substitutions and order
  risks. Reports contain `kind`, relative `path`, `status` (`written` or `failed`)
  and nullable `error`. A failed write may still have comparison counts; a
  comparison that never completed has unknown/null evidence and no reports.

An otherwise successful pair containing differences, unverified pages or image
diagnostics stays `success`. Both reports must be written for pair success.
Batch exit is 0 only when all pairs and both summaries succeed; otherwise 1.
Invalid CLI arguments return 2. Summary writes are independently attempted;
failure is reported on stderr and by exit status, retaining the other summary.
Summary pair totals describe pair results, not whether both summaries were saved.

No automatic pairing, recursive discovery, parallelism, resume or merged
document accuracy score is provided. Summary paths can reveal local filenames;
review before sharing. The ordinary conversion and single-comparison defaults
remain unchanged.
