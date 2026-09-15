# pdf-receipt

Converts PDF files to Markdown locally, and reports **exactly what it lost** —
page by page, with evidence.

pdf-receipt runs on [Docling](https://github.com/docling-project/docling), which
uses machine learning models to read page layout, tables, and scanned text.
Everything runs on your own machine. No file is ever uploaded, and once the
models are cached the tool works fully offline.

## Installation

You need Windows and Python 3.10 or newer. When installing Python from
python.org, tick **Add python.exe to PATH**.

Then run `install.bat` once. It creates a virtual environment, installs Docling,
and adds a `pdf-receipt` entry to the Windows **Send to** menu. Expect it to take
a few minutes.

Docling downloads its own models during your first conversion, so setup and the
first run need an internet connection. Everything after that is offline. Running
`install.bat` again reuses the existing environment rather than reinstalling it.

## Usage

**Drag and drop.** Drop one or more PDFs onto `pdf-receipt.bat`. A console window
opens, prints its progress, and opens the output folder in Explorer when it
finishes. If something fails, the window stays open so you can read the error.

**Send to menu.** Select any number of PDFs in Explorer, right-click, and choose
Send to → pdf-receipt. On Windows 11 you may need to open **Show more options**
first. Only the files you selected are converted, so you can pick two PDFs out of
a folder of four. If you installed the tool before this shortcut existed, run
`install.bat` again — your installed packages are reused.

**Command line.**

```powershell
.\pdf-receipt.bat                                    # every PDF in this folder
.\pdf-receipt.bat --yes                              # same, without confirmation
.\pdf-receipt.bat "C:\Docs\sample.pdf"               # a single file
.\pdf-receipt.bat --fast "C:\Docs\sample.pdf"        # fast profile
.\pdf-receipt.bat "C:\Docs\a.pdf" "C:\Docs\b.pdf"    # several files
.\pdf-receipt.bat "C:\Docs\sample.pdf" -o "C:\out"   # choose the output folder
.\pdf-receipt.bat --no-open "C:\Docs\sample.pdf"     # skip the Explorer window
.\pdf-receipt.bat --no-report "C:\Docs\sample.pdf"   # skip the quality report
.\pdf-receipt.bat --help                             # all options
```

**Current folder.** Given no path, the tool converts every `.pdf` file directly
inside the folder it was launched from. Matching ignores case, and subfolders are
not searched:

```powershell
cd "C:\Docs"
C:\path\to\pdf-receipt.bat
```

The folder and file names are printed first. If it finds more than one PDF in an
interactive console, type `yes` to start or anything else to cancel. Use `--yes`
to skip that prompt. Scripts and other non-interactive runs never stop to ask.

## Output

For a single PDF, the output folder is created next to the source file:

```text
sample_markdown/
├── sample.md          the readable document
├── sample.json        Docling's structural record
├── sample_report.md   what the conversion lost
└── sample_artifacts/  images extracted from the document (PNG)
```

Images are **not embedded** in the Markdown; they are separate files that the
`.md` links to. If you move the Markdown somewhere else, take the `_artifacts`
folder with it or the images will break.

The `.json` file holds everything Markdown cannot express: which page each block
came from and where it sits on that page, the cell-by-cell structure of tables
including merged cells, and block types. It is what you want for a search or RAG
system, or for answering "which page is this sentence on?". If you only plan to
read the document, you can delete it — the Markdown stands on its own.

Given several PDFs and no `-o`, a shared folder is created next to the first PDF,
and files with the same name are separated by `_2`, `_3`:

```text
pdfmd_output/
├── one_markdown/
└── two_markdown/
```

With `-o`, a single PDF writes straight into that folder, while several PDFs each
get their own document folder inside it. If one file fails, the rest continue and
a summary is printed at the end.

## Quality report

Every conversion prints a short Quality Report v2 summary. The numbers below are
illustrative, not a real measurement:

```text
Quality Report v2 | Extraction: transfer 98.0% (980/1000); unexplained 10; order risks 2 | Serialization: transfer 99.0% (990/1000); unexpected 5; order risks 1
Structure: PASS | headings 12/12; lists 3/3 (items 18/18); tables 4/4 (cells 86/86); links 2/2; images 5/5; stale 0
```

The details go into `<name>_report.md`. Pass `--no-report` to turn it off.

The report is most valuable on scanned documents. Converting a PDF that has no
text layer with `--fast` quietly produces an empty file, and the report says so
instead of claiming success:

```text
Quality Report v2 | Extraction: transfer n/a (no source tokens); unexplained 0; order risks 0 | Serialization: transfer n/a (no source tokens); unexpected 0; order risks 0
Structure: PASS | headings 0/0; lists 0/0 (items 0/0); tables 0/0 (cells 0/0); links 0/0; images 0/0; stale 0
WARNING: 2 pages without a text layer are unverified; --fast turned OCR off, so they may have come out empty. Coverage cannot be measured. Try again with --quality.
```

### Two stages, measured separately

The tool never scores the PDF against the Markdown directly. It runs two
comparisons instead:

```text
PDF text layer  ->  DoclingDocument  ->  Markdown and artifacts
        extraction              serialization
```

Each stage gets its own token counts, rates, and issue samples. This is evidence
of agreement with the PDF text layer — **not** verified document accuracy, since
the text layer itself can be wrong.

The structural section compares headings, lists, table cells, and links between
the DoclingDocument and the Markdown. It resolves local links only inside the
output folder, decodes every image to record its real format and dimensions, and
flags missing, empty, invalid, or stale artifacts. It never opens external links
over the network. These checks prove the Markdown matches the DoclingDocument;
they say nothing about whether Docling read the PDF correctly.

### How tokens are compared

- **Nothing is too short to count.** Unicode letters and digits of every length
  are included, so values like `A`, `ve`, `7`, and `42` are never dropped.
- **Ligatures compare equal.** Unicode compatibility normalization makes `ﬁ`
  match the ordinary letters.
- **Every occurrence is consumed once.** Alignment is page-partitioned and uses a
  bounded 64-token window, so one Markdown word can never explain two PDF words.
- **Reading-order changes are risks, not errors.** The PDF text layer is
  unreliable on multi-column pages, so a disagreement is reported rather than
  blamed on Docling.
- **Figures and page furniture must overlap.** A figure only explains a token
  when the retained PDF character boxes overlap the Docling region; matching page
  and text alone is not enough.

Case handling follows an explicit document-level policy. The default `unicode`
profile uses locale-free case folding, so `RISK`/`risk` and `I`/`i` match. A
`turkic` profile is also available, where `İ`/`i` and `I`/`ı` are the pairs
instead. The converter never guesses a document's language, because no
locale-free rule can satisfy both readings of `I` safely.

Hyphens are handled conservatively. A compound on one line, such as
`risk-based`, keeps its hyphen. A hyphen at the end of a line is ambiguous — it
may be a wrapped compound — so each token keeps its raw span alongside both a
hyphen-preserving and a joined form. The aligner joins the two halves only when
the neighbouring tokens support it, and records that decision separately from an
ordinary match.

The metrics report accepted transfer, accounted loss, unexplained loss,
unexpected additions, substitutions, and order risks as distinct numbers.
Explaining a loss never quietly improves the transfer rate. Empty denominators
render as `n/a`. The old bag-of-words percentage survives only as
`legacy_coverage`, kept as diagnostic history. The full metric contract, its
limits, and synthetic measurements are in
[`docs/ALIGNMENT.md`](docs/ALIGNMENT.md).

## Reusing completed conversions

```powershell
.\pdf-receipt.bat --skip-existing "C:\Documents\example.pdf"
```

Every conversion now writes `<name>_manifest.json` beside its outputs.
`--skip-existing` skips a document only when this completion record matches the
source path, size, modification time, SHA-256 content hash, application/Docling
versions, and all conversion settings (profile, formula, image scale, report).
Local source-code changes also invalidate records. Without the flag, conversion
always runs. Older outputs without a compatible manifest are converted again.

Reuse checks hash every required Markdown, JSON, report, and referenced image;
validate the Docling JSON schema; decode referenced images; and check local
Markdown links. These are local checks, with no model loading when all documents
can be skipped. Reading and hashing large files still takes work. The manifest
records relative output paths, file sizes, and hashes. A report is required only
when enabled; a failed report stays a warning but prevents reuse of that run.
These checks establish output integrity, not extraction accuracy.

Before touching outputs, conversion atomically marks the record incomplete.
Only after exports and checks succeed is it atomically replaced by a completed
record. An interrupted conversion may leave partial outputs, but they cannot
be reused as complete. This is completion safety, not a rollback of old outputs.
Completion-write failures warn and leave the record incomplete; inability to
invalidate an old record stops the conversion before changing its outputs.

A `<name>_conversion.lock` file prevents concurrent writers to the same document
output. Normal exits and Ctrl+C remove it. If the process is forcibly terminated,
first confirm no conversion is running, then remove only that lock file from the
output directory and retry. A leftover `.pdf-receipt-*.tmp` file is never a
completion record and does not enable skipping.

Unrelated files and old unreferenced artifacts are preserved, not cleaned up or
listed as required manifest outputs. The quality report can still flag stale
artifacts. Batch summaries show converted, skipped, and failed counts separately;
an all-skipped run succeeds and can open the existing output folder.

## Image resolution

Use `--image-scale 2` for higher-resolution image artifacts with either profile.
The default is `1.0`, preserving the existing resolution. Any finite number from
`1.0` to `3.0` inclusive is accepted, including `1.5`; values outside that range,
NaN, and infinity are rejected before loading models.

Higher scales increase image width and height, with pixel rounding, and may use
more memory, conversion time, and disk space. They do not recover detail missing
from the source image. Markdown still uses relative, forward-slash image links.

The completion line and each successful batch-summary entry show elapsed seconds
and total artifact bytes, also with `--no-report`. Duration covers conversion,
exports, the optional report, and completion checks. Runtime object creation is excluded, but
Docling's lazy pipeline/model initialization during the first conversion is
included, so the first document can take longer. Artifact bytes
count all files currently under the document's artifact folder, including stale
files from earlier runs; Markdown, JSON, and the report are excluded. An empty
or absent artifact folder counts as zero. A measurement error shows a warning
and an unavailable size without failing the conversion.

## Which profile?

| | `--fast` | default (`--quality`) |
|---|---|---|
| Text and images | same | same |
| Tables | rows and columns are lost, cells pile into one line | real rows and columns |
| Scanned page | comes out empty | OCR reads the text |

The difference is exactly two settings: `--fast` turns off OCR and the table
structure model, which is the only reason it finishes sooner.

**Rule of thumb:** keep the default for anything scanned or table-heavy, and use
`--fast` for plain prose such as novels, articles, and contract text. When in
doubt, the default loses nothing — it is only slower.

`--formula` converts formulas to LaTeX. Its first run downloads an extra 631 MB
model, and resumes the download if it is interrupted. It works with either
profile.

## What survives and what does not

Benchmark numbers are being re-measured and will be published here once that run
is finished. Note in advance that no transfer rate this tool reports is a
document-accuracy percentage: measuring that would need manually verified ground
truth, which no benchmark run here has.

The qualitative picture does not depend on those numbers:

**Kept:** heading levels, paragraph and list structure, table data, the position
of images within the text, and footnotes. Page headers and footers are dropped on
purpose.

**Lost:**

- **Italic and bold emphasis** become plain text.
- **Merged table cells** cannot exist in Markdown, so the value repeats: a header
  spanning three columns comes out as `| Provided To | Provided To | Provided To |`.
  The real structure stays in the `.json` file as `colspan`.
- **Drop caps** — the oversized letter opening a chapter — can end up detached
  and out of order: `This` may split into a lone `T` and a later `his`. The
  character survives in both JSON and Markdown, but its reading relationship does
  not. See [`docs/DROP_CAP_DIAGNOSIS.md`](docs/DROP_CAP_DIAGNOSIS.md).
- **Superscript footnote numbers** drop down into the line.
- **Text drawn inside figures** stays part of the image and never becomes text.

## Project layout

```text
src/pdf_receipt/
├── __main__.py              entry point for `python -m pdf_receipt`
├── cli.py                   arguments, progress messages, exit codes
├── converter.py             the Docling conversion and the output paths
├── quality_report.py        collects evidence and renders Quality Report v2
├── quality_metrics.py       per-stage counts, rates, and accounting identities
├── alignment.py             bounded two-stage occurrence alignment
└── structural_integrity.py  heading, list, table, link, and image integrity
tests/                       one test file per module
tests/fixtures/              PDF regression corpus and machine-checkable facts
docs/                        notes and open work
```

`pdf-receipt.bat` puts `src` on the import path and calls
`python -m pdf_receipt`, so there is no installation step.

## Tests

```powershell
.venv\Scripts\python.exe -m unittest discover -s tests -t .
```

This skips the live Docling corpus test, which is slower. Once the initial setup
has cached every model, the fully offline integration instructions are in
[`tests/fixtures/README.md`](tests/fixtures/README.md).

## License

[MIT](LICENSE). Use, modify, and distribute it freely; it comes with no warranty.

The conversion engine is [Docling](https://github.com/docling-project/docling),
distributed separately under its own license.
