# Formula conversion and download recovery

## Scope

Milestone G checks the existing opt-in `--formula` setting with an original PDF
containing raised exponents, a drawn fraction bar, and surrounding prose. The
fixture and its standard-library generator are under `tests/fixtures/formulas/`.
This is a regression check, not evidence of accuracy on arbitrary mathematics,
handwriting, complex notation, or scanned research papers.

## Model and environment

- Windows, Python 3.12, pinned Docling 2.124.0.
- Docling Core 2.93.0, Transformers 5.16.1, Torch 2.14.0 (CPU).
- Hugging Face Hub client 1.29.0; HTTP downloads with `HF_HUB_DISABLE_XET=1`,
  matching the application's default transport setting.
- Model: `docling-project/CodeFormulaV2`.
- Snapshot: `ecedbe111d15c2dc60bfd4a823cbe80127b58af4`.
- Expected model SHA-256 from the cached Hub tree:
  `4b04e77af34c4e682a7ab1617628340d658f3c3dcd12456dd2a7fff805cf79d2`.

## Interrupted-download recovery

The installed Hub client creates a unique `.incomplete` filename for each
download. It does not reopen a previous process's partial file. On a handled
exception it removes its own temporary file; a forcibly terminated process can
leave that file behind. Completed cached files remain reusable.

Evidence gathered during this milestone:

- A real snapshot download found an older partial model file, created a new
  temporary file, and called HTTP download with `resume_size=0`.
- That transfer stalled initially and was interrupted. A subsequent range GET
  to the same model returned HTTP 206 with the requested content range.
- The installed client's actual temporary-file routine was tested with a
  simulated interrupted HTTP writer. No final model appeared after interruption;
  retry began at offset zero and produced the complete expected file. This test
  does not claim to simulate a power failure or an actual network interruption.

Recovery for users: rerun the original `--formula` command with network access.
Expect the incomplete file to restart rather than resume its old bytes. Do not
rename a partial file to `model.safetensors` or assume its size proves validity.
If the process was forcibly killed, also follow the output-lock recovery steps
in the README after confirming no conversion is active.

For this development run only, the stalled transfer was replaced with bounded
HTTP range requests into an isolated task copy, preserving the original partial
files. Every response range and byte count is checked, and the full SHA-256 must
match before installation into the existing snapshot. This diagnostic procedure
is not a new application downloader or a promise of automatic resume support.
The completed model matched the expected SHA-256 and was installed into the
existing cached snapshot. Original partial files were preserved. No downloaded
model weights or third-party model files are included in this repository.

## Offline checks

Both fast and quality conversion produced the following raw formula text from
the fixture, with the same expressions serialized into Markdown display blocks:

```latex
a ^ { 2 } \, + \, b ^ { 2 } \, = \, c ^ { 2 }
x \, = \, \frac { a + b } { c + d }
```

The test ignores whitespace, thin-space commands, and optional braces around
single-digit exponents. It still rejects changed signs, exponents, variables,
and swapped numerator/denominator. All four surrounding sentences must survive
exactly once, with each equation between its associated preceding/following
sentences. JSON and Markdown must agree, and report/manifest generation must
succeed.

Transformers emitted upstream warnings about an out-of-vocabulary
`pad_token_id` and differing checkpoint weights despite a tied-weights config.
No model configuration was patched locally. The observed equations were correct,
but this narrow check does not dismiss those warnings for other inputs.

See `tests/fixtures/formulas/README.md` for the opt-in command. Both
`HF_HUB_OFFLINE=1` and `TRANSFORMERS_OFFLINE=1` are required; missing models fail
visibly instead of triggering downloads.

The unavailable-model test makes formula-engine creation fail deliberately.
Ordinary conversion still works in both profiles without requesting that engine.
An explicit formula request fails and leaves its completion manifest incomplete.
This isolates optional-model availability without deleting or moving cached
models. Without enrichment, detected equations may be emitted as
`<!-- formula-not-decoded -->`; surrounding prose remains available.

## Verification result

On 2026-09-15, all three opt-in offline formula tests passed, including both
conversion profiles. The two focused fixture tests passed, and full discovery
reported 224 tests OK with seven opt-in live tests skipped. The fixture generator
reproduces the checked-in PDF byte for byte. No application code, dependencies,
or default conversion settings were changed for this milestone.

Review follow-up (2026-09-16): the live formula test now pins the recorded model
snapshot in a private copy of the test pipeline options, including all engine
revision overrides. It cannot silently select a newer cached `main` snapshot.
The application retains its existing defaults.

The Hub recovery diagnostic is now in `tests/integration/test_hub_recovery.py`,
enabled only by `PDF_RECEIPT_RUN_HUB_DIAGNOSTICS=1`. It explicitly covers Hub
1.29.0 and skips other versions before accessing private implementation helpers.
The two conversion tests remain under `PDF_RECEIPT_RUN_FORMULA_TESTS=1`.
Four focused tests and the separate recovery diagnostic passed. Both runtime
configurations and local availability of the exact snapshot were verified
offline without rerunning model inference. Full discovery reports 226 tests OK
with seven opt-in skips.
