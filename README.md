# pdf-receipt

Local, offline PDF to Markdown conversion that reports **exactly what it lost**,
page by page, with evidence.

A personal tool that converts PDF files to Markdown locally. It runs on Docling,
so page layout, tables and scanned text are handled by machine learning models.
Nothing is uploaded anywhere; everything happens on this computer.

A Turkish version of this document is available in [README_tr.md](README_tr.md).

## Installation

You need Python 3.10+ on Windows (tick "Add python.exe to PATH" when installing
it from python.org). Then run `install.bat` once: it creates the virtual
environment, downloads Docling, and adds `pdf-receipt` to the Windows "Send to"
menu. This can take a few minutes the first time. Docling also downloads its own
models during the first conversion, so setup and the first run need an internet
connection; everything after that is offline. Running `install.bat` again keeps
the existing environment and packages; it does not reinstall them from scratch.

## Usage

**Drag and drop:** drop one or more PDFs onto `pdf-receipt.bat`. A console window
opens, prints its progress, and opens the output folder in Explorer when it is
done. If something fails the window stays open so you can read the message.

**Selected files anywhere:** `install.bat` adds a `pdf-receipt` shortcut to the
Windows "Send to" menu. Select any number of PDFs in Explorer, right-click, then
choose Send to → pdf-receipt. On Windows 11, "Send to" may be under "Show more
options". Only the selected files are converted, so if a folder contains four
PDFs you can select two and process just those two. If you installed the tool
before this shortcut was added, run `install.bat` again; installed dependencies
are reused.

**Command line:**

```powershell
.\pdf-receipt.bat                                             # every PDF in this folder
.\pdf-receipt.bat --yes                                       # same, without confirmation
.\pdf-receipt.bat "C:\Docs\sample.pdf"                     # a single file
.\pdf-receipt.bat --fast "C:\Docs\sample.pdf"              # fast profile
.\pdf-receipt.bat "C:\Docs\a.pdf" "C:\Docs\b.pdf"          # several files
.\pdf-receipt.bat "C:\Docs\sample.pdf" -o "C:\out"         # output folder
.\pdf-receipt.bat --no-open "C:\Docs\sample.pdf"           # no Explorer window
.\pdf-receipt.bat --no-report "C:\Docs\sample.pdf"         # no quality report
.\pdf-receipt.bat --help                                   # all options
```

**Current folder:** when no PDF path is supplied, the tool finds every `.pdf`
file directly in the folder it was launched from. Matching is case-insensitive,
and subfolders are not searched. For example, to convert the PDFs in `C:\Docs`
from anywhere the batch file is installed:

```powershell
cd "C:\Docs"
C:\path\to\pdf-receipt.bat
```

The folder and file names are printed first. If more than one PDF is found in an
interactive console, type `yes` to start or anything else to cancel. Use
`--yes` to skip that question. Scripts and other noninteractive runs proceed
without asking.

## Output

For a single PDF the output is created next to the source file:

```text
sample_markdown/
├── sample.md          the file you read
├── sample.json        Docling's structural record
├── sample_report.md   what the conversion lost
└── sample_artifacts/  images extracted from the document (PNG)
```

Images are **not embedded** in the Markdown; they are separate files the `.md`
links to. If you move the Markdown file somewhere else, take the `_artifacts`
folder with it or the images will break.

The `.json` file holds what Markdown cannot: which page each block came from and
where it sits on that page, the cell-by-cell structure of tables (merged cells
included), and block types. Useful for feeding a search/RAG system or answering
"which page is this sentence on". If you only want to read the document you can
delete it; the Markdown works without it.

When several PDFs are given and `-o` is not, a shared folder is created next to
the first PDF, and files with the same name are separated by `_2`, `_3`:

```text
pdfmd_output/
├── one_markdown/
└── two_markdown/
```

With `-o`, a single PDF writes straight into that folder, while several PDFs get
their document folders created inside it. If one file fails the rest keep going
and a summary is printed at the end.

## Quality report

After every conversion the tool prints a concise Quality Report v2 summary. The
numbers below are illustrative, not a reproduced document measurement:

```text
Quality Report v2 | Extraction: transfer 98.0% (980/1000); unexplained 10; order risks 2 | Serialization: transfer 99.0% (990/1000); unexpected 5; order risks 1
Structure: PASS | headings 12/12; lists 3/3 (items 18/18); tables 4/4 (cells 86/86); links 2/2; images 5/5; stale 0
```

The details go into `<name>_report.md`. Extraction (PDF text layer to
DoclingDocument) and serialization (DoclingDocument to visible Markdown) have
separate token counts, rates, accounting identities, and occurrence-level issue
samples. This is text-layer agreement evidence, not verified document accuracy.
The structural section also compares heading, list, table-cell, and link
occurrences between the DoclingDocument and Markdown. It keeps local targets
inside the output directory, decodes images to record their format and
dimensions, and reports missing, empty, invalid, or stale artifacts. It never
opens external links over the network. These are serialization-integrity
checks; they do not by themselves prove that Docling extracted the PDF correctly.

It earns its keep on scanned documents. Converting a PDF without a text layer
using `--fast` silently produces an empty file, and the report says so:

```text
Quality Report v2 | Extraction: transfer n/a (no source tokens); unexplained 0; order risks 0 | Serialization: transfer n/a (no source tokens); unexpected 0; order risks 0
Structure: PASS | headings 0/0; lists 0/0 (items 0/0); tables 0/0 (cells 0/0); links 0/0; images 0/0; stale 0
WARNING: 2 pages without a text layer are unverified; --fast turned OCR off, so they may have come out empty. Coverage cannot be measured. Try again with --quality.
```

Pass `--no-report` if you do not want it.

The counter now includes Unicode letters and numbers of every length, so short
words and table values such as `A`, `ve`, `7`, and `42` are not silently
dropped. Unicode compatibility normalization makes ligatures such as `ﬁ`
compare equal to their ordinary letters.

Case handling has an explicit document-level policy. The default `unicode`
profile uses locale-free Unicode case folding, so English `RISK`/`risk`,
`TITLE`/`title`, and `I`/`i` match. The token model also supports an explicitly
selected `turkic` profile, where `İ`/`i` and `I`/`ı` are separate pairs. The
converter does not guess a document's language: no single locale-free string
can satisfy both interpretations of `I` safely.

A same-line compound such as `risk-based` keeps its hyphen. A hyphen at a line
ending is ambiguous because it can also be a wrapped compound. Tokens retain
every raw separator span, a conservative hyphen-preserving form, and independent
keep/join choices. Ordered alignment only joins a candidate when neighboring
tokens support it and records that decision separately from an ordinary match.

The analysis path now builds two occurrence-based results: PDF text layer to
DoclingDocument (extraction), then DoclingDocument to visible Markdown
(serialization). Alignment is page-partitioned and uses a bounded 64-token LCS
window, retains source/provenance evidence, reports possible reading-order moves
as risks, and never reuses one occurrence. Multi-entry Docling provenance is
mapped by token `charspan`; ambiguous pages remain unknown. Figure and furniture
explanations require overlap between retained PDF character boxes and the
Docling region, rather than page-and-text equality alone. Visible URL and email
autolinks are tokenized while actual HTML tags remain syntax. V2 exposes
accepted transfer, accounted loss, unexplained loss, unexpected additions,
substitutions, and order risks without folding explanations into the transfer
rate. Zero denominators render as `n/a`. The old bag-of-words percentage remains
available only as `legacy_coverage` diagnostic history. The full operation and
metric contract, limits, and synthetic measurements are in
[`docs/ALIGNMENT.md`](docs/ALIGNMENT.md).

## Which profile?

| | `--fast` | default (`--quality`) |
|---|---|---|
| Speed (5 pages) | 13 s | 30 s |
| Text and images | same | same |
| Tables | rows/columns are lost, cells pile into one line | real rows and columns |
| Scanned page | comes out empty | OCR reads the text |

The difference is exactly two settings: `--fast` turns off OCR and the table
structure model.

**Rule of thumb:** keep the default when the document is scanned or has tables;
use `--fast` for plain text (novels, articles, contract text). When in doubt the
default loses nothing, it is only slower. In the latest warm-cache verification,
the 95-page, table-heavy NIST document converted in 276 seconds; end-to-end time
including model loading and CLI shutdown was 283.355 seconds.

`--formula` turns formulas into LaTeX. The first run downloads an extra 631 MB
model; if the download is interrupted it resumes on the next run. It can be
combined with either profile.

## What survives and what does not

The 95-page NIST SP 800-30 document was remeasured on September 8, 2026 with
cached models, offline, and the default `--quality` profile:

- Extraction transfer: **93.44%** (39,921/42,724), with 2.73% accounted loss,
  0.64% unexplained loss, and 1,364 reading-order risks.
- Serialization transfer: **98.37%** (40,680/41,355), with 0.11% unexplained
  loss, 0.23% unexpected additions, and 436 reading-order risks.
- Structural integrity: **PASS** — 152 headings, 40 lists/183 items, 55
  tables/1,274 cells, and 7/7 valid PNGs; no missing or stale artifacts.
- The latest warm-cache verification took 283.355 seconds end to end. The
  highest `PeakWorkingSet64` from valid process samples in the first two offline
  measurement runs was 3,587,977,216 bytes (3.342 GiB).

The historical **99.6%** Quality Report v1 value remains diagnostic history.
Its old counter omitted tokens shorter than three characters and did not account
for occurrences one-to-one, so it is not directly comparable with the v2
transfer rates. None of these values is a document-accuracy percentage because
the NIST run has no manually verified ground truth.

Kept: heading levels, paragraph and list structure, table data, the position of
images within the text, footnotes. Page headers and footers are dropped on
purpose.

Lost:

- **Italic and bold emphasis** become plain text.
- **Merged table cells** do not exist in Markdown, so the value is repeated: a
  header spanning three columns comes out as
  `| Provided To | Provided To | Provided To |`. The real structure stays in the
  `.json` file as `colspan`.
- **Drop caps** (the large letter at the start of a chapter) can become detached
  and misordered: `This` may be split into a standalone `T` and a later `his`
  block. The character remains in JSON/Markdown but its reading relationship is
  lost; see `docs/DROP_CAP_DIAGNOSIS.md`.
- **Superscript footnote numbers** drop into the line.
- **Text drawn inside figures** does not come out as text; it stays in the image.

## Project layout

```text
src/pdf_receipt/
├── __main__.py        entry point for `python -m pdf_receipt`
├── cli.py             arguments, progress messages, exit codes
├── converter.py       the Docling conversion and the output paths
├── quality_report.py  collects evidence and renders Quality Report v2
├── quality_metrics.py per-stage v2 counts, rates, and accounting identities
├── alignment.py       bounded two-stage occurrence alignment
└── structural_integrity.py  heading, list, table, link, and image integrity
tests/                 one test file per module
tests/fixtures/        PDF regression corpus and machine-checkable facts
docs/                  notes and open work
```

`pdf-receipt.bat` puts `src` on the import path and calls `python -m pdf_receipt`, so no
installation step is needed.

## Tests

```powershell
.venv\Scripts\python.exe -m unittest discover -s tests -t .
```

This fast command skips the live Docling corpus test. After the initial setup
has cached all models, the fully offline integration instructions are in
[`tests/fixtures/README.md`](tests/fixtures/README.md).

## License

[MIT](LICENSE). You may use, modify, and distribute this freely; the software is
provided without any warranty.

The conversion engine is [Docling](https://github.com/docling-project/docling),
which is distributed separately under its own license.
