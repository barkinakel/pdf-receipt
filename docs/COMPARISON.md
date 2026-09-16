# Independent PDF-to-Markdown comparison

Milestone H adds an offline comparison of an existing PDF and an existing
Markdown file. The Markdown can come from any tool or person. No Docling JSON,
conversion runtime, model setup or network service is used by this command.
The installed Python dependencies are still required.

```powershell
.\pdf-receipt.bat compare source.pdf existing.md
.\pdf-receipt.bat compare source.pdf existing.md --report comparison.md --issue-limit 100
.\pdf-receipt.bat compare source.pdf existing.md --case-profile turkic
```

Inputs are read without modification. Markdown must be UTF-8 (an initial BOM is
accepted), with an `.md` or `.markdown` extension. The default report is
`existing_comparison.md` beside the Markdown. An explicit report's parent must
already exist. Existing targets and input paths are refused; exclusive creation
also protects against a target appearing while the comparison runs. A write
failure can leave a partial report: choose another report path for a retry.
Relative paths follow the process working directory; the batch launcher changes
that directory to the repository. Use absolute paths for inputs elsewhere.

Differences and unverified pages return exit 0: the comparison succeeded.
Input, parsing or report-writing failures return exit 1; invalid CLI arguments
return exit 2. Conversion flags such as `--formula`, `--profile`, `--image-scale`
and `--skip-existing` are not accepted. Existing conversion commands and their
two-stage quality reports retain their behavior.

## What the report measures

The PDF text layer is compared directly with tokenized Markdown text. Unicode
normalization, case folding, short tokens and contextual line-end hyphen handling
reuse the existing evidence-preserving tokenizer. `unicode` is the default case
profile; `turkic` uses Turkish casing. Punctuation and formatting are not
scored as textual content.

Direct alignment uses bounded ordered matching and globally one-to-one occurrences.
The PDF text layer is evidence, not guaranteed ground truth.

The report separates accepted matches, missing occurrences, added occurrences
(including surplus repetitions), substitutions and order risks. Substitutions
contribute to both loss and addition numerators. Transfer and loss use source
tokens as denominator; additions use Markdown tokens. Empty denominators are
`n/a`. Both accounting identities and per-page source counts are shown.
Target-only additions have no inferred PDF page.

Representative differences retain raw/normalized evidence, page, line and character spans.
`--issue-limit` limits individual differences (default 50); complete counts and omitted examples are disclosed.

## Evidence limits

The PDF text layer is evidence, not ground truth. It can contain omissions,
incorrect text or an incorrect reading order. Pages without comparable tokens
are explicitly unverified, whether scanned, blank or otherwise inaccessible.
No OCR is run. Text-bearing pages can still contain unverified scanned regions.
Reported rates describe the available text layer, never whole-document accuracy.

The lightweight parser supports common headings, lists, pipe tables and inline links/images.
Reference syntax, HTML, entities and nested formatting may affect counts. Inline local image
references are resolved relative to the Markdown directory.
Local files are checked for existence, readability, nonempty content and actual
image decoding. Paths outside that folder, including resolved symlink escapes,
are refused. Remote and unsupported targets are reported as unchecked and never
fetched. A decodable image proves neither correspondence with a PDF image nor
that all PDF images survived. Image diagnostics do not change comparison exit
status and are separate from text counts.

## Verification

`tests/test_comparison.py` covers occurrence accounting across pages, repetitions,
loss/addition, substitutions, ordering, Unicode, empty evidence, Markdown syntax,
location evidence, report truncation, image diagnostics and CLI file protection.
It also compares the checked-in original formula PDF with independently authored
Markdown without creating a Docling runtime. These are deterministic offline
regression checks, not a general accuracy benchmark.

```powershell
.venv\Scripts\python.exe -m unittest tests.test_comparison
.venv\Scripts\python.exe -m unittest discover -s tests -t .
```
