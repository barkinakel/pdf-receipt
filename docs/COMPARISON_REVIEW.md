# Cumulative review after Milestone L

Reviewed locally on 2026-09-16. Scope: pending formula test changes, independent
comparison, alignment additions, Markdown source mapping, grouped presentation,
JSON export, output protection and their documentation/tests. Earlier committed
conversion functionality was covered by the full regression suite. No network,
model download, commit or publication occurred during this review.

## Findings fixed

- **Nested inline HTML templates leaked hidden text and image references.**
  A single hidden-start flag closed at the first nested end tag. The adapter now
  tracks matching hidden tags and excludes image targets in the hidden ranges.
  The original fixture reproduces both text leakage and spurious image inventory.
- **Custom tags beginning with `br` split words.** Prefix-based line-break
  detection interpreted `<brand>` as `<br>`. Exact tag boundaries now determine
  block separators; a regression preserves the original joined word.

Both defects were reproduced with failing tests before fixing. No additional
release-blocking defect was found in the reviewed scope. This is a bounded code
and regression review, not proof of unrestricted Markdown or PDF accuracy.

## Verification

- Focused comparison/parser/group/JSON modules: 57 tests passed.
- Full discovery: 283 tests OK, including seven deliberately skipped opt-in tests.
  Live model inference and version-specific Hub diagnostics were not rerun.
- Source files parse using Python 3.10 grammar; this does not replace a runtime
  compatibility matrix across Python versions.
- Existing-file/input/output collisions, missing parents, exclusive-creation
  races, either output failing and a partial write all have focused coverage.
- Both serializers share a single typed result; tests assert one alignment and
  one image-check pass when both outputs are requested.
- The 12 already-acquired pilot pairs produced valid JSON in the ignored
  `l-json-recheck/` directory. Every source/target occurrence is referenced once;
  Markdown output is identical to K's saved reports and acquisition hashes match.
- Diff whitespace checks passed; pending earlier milestone files were preserved.

## Remaining limits

The text layer is not ground truth. OCR accuracy, visual images, mathematical
meaning and table structure remain unverified. Complex rearrangements can still
produce fragmented groups, as recorded in the pilot review. The parser adapter
depends on the declared major version's rule interfaces and requires regression
checks before an upgrade. JSON retains all occurrence evidence in memory and can
be large; it is not a streaming export. M was unimplemented at this review;
its subsequent implementation and verification are recorded in `TODO.md`.
