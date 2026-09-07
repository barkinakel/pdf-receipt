# PDF to Markdown

A personal tool that converts PDF files to Markdown locally. It runs on Docling,
so page layout, tables and scanned text are handled by machine learning models.
Nothing is uploaded anywhere; everything happens on this computer.

This is the English version of the documentation. The Turkish original is
[README.md](README.md).

## Installation

You need Python 3.10+ on Windows (tick "Add python.exe to PATH" when installing
it from python.org). Then run `install.bat` once: it creates the virtual
environment, downloads Docling, and adds `pdftomd` to the Windows "Send to"
menu. This can take a few minutes the first time. Docling also downloads its own
models during the first conversion, so setup and the first run need an internet
connection; everything after that is offline. Running `install.bat` again keeps
the existing environment and packages; it does not reinstall them from scratch.

## Usage

**Drag and drop:** drop one or more PDFs onto `pdftomd.bat`. A console window
opens, prints its progress, and opens the output folder in Explorer when it is
done. If something fails the window stays open so you can read the message.

**Selected files anywhere:** `install.bat` adds a `pdftomd` shortcut to the
Windows "Send to" menu. Select any number of PDFs in Explorer, right-click, then
choose Send to → pdftomd. On Windows 11, "Send to" may be under "Show more
options". Only the selected files are converted, so if a folder contains four
PDFs you can select two and process just those two. If you installed the tool
before this shortcut was added, run `install.bat` again; installed dependencies
are reused.

**Command line:**

```powershell
.\pdftomd.bat                                             # every PDF in this folder
.\pdftomd.bat --yes                                       # same, without confirmation
.\pdftomd.bat "C:\Docs\sample.pdf"                     # a single file
.\pdftomd.bat --fast "C:\Docs\sample.pdf"              # fast profile
.\pdftomd.bat "C:\Docs\a.pdf" "C:\Docs\b.pdf"          # several files
.\pdftomd.bat "C:\Docs\sample.pdf" -o "C:\out"         # output folder
.\pdftomd.bat --no-open "C:\Docs\sample.pdf"           # no Explorer window
.\pdftomd.bat --no-report "C:\Docs\sample.pdf"         # no quality report
.\pdftomd.bat --help                                   # all options
```

**Current folder:** when no PDF path is supplied, the tool finds every `.pdf`
file directly in the folder it was launched from. Matching is case-insensitive,
and subfolders are not searched. For example, to convert the PDFs in `C:\Docs`
from anywhere the batch file is installed:

```powershell
cd "C:\Docs"
C:\path\to\pdftomd.bat
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

After every conversion the tool compares the PDF text layer with the Markdown it
produced and prints a one-line summary:

```text
Quality: 99.6% word coverage | 55 tables, 7 images
```

The details go into `<name>_report.md`: how many words carried over, where the
missing ones ended up (inside a figure, in a page header, glued to a footnote
number), the pages with the most unexplained loss, and what Markdown could not
carry for that document.

It earns its keep on scanned documents. Converting a PDF without a text layer
using `--fast` silently produces an empty file, and the report says so:

```text
Quality: the PDF has no text layer (scanned document), coverage cannot be measured
WARNING: 2 pages have no text layer and --fast turned OCR off; those pages may
have come out empty. Try again with --quality.
```

Pass `--no-report` if you do not want it.

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
default loses nothing, it is only slower. Measured: a 95-page table-heavy
document took about 5 minutes on the default profile.

`--formula` turns formulas into LaTeX. The first run downloads an extra 631 MB
model; if the download is interrupted it resumes on the next run. It can be
combined with either profile.

## What survives and what does not

Measured on a 95-page NIST document: **99.6%** of the words in the PDF text
layer made it into the Markdown.

Kept: heading levels, paragraph and list structure, table data, the position of
images within the text, footnotes. Page headers and footers are dropped on
purpose.

Lost:

- **Italic and bold emphasis** become plain text.
- **Merged table cells** do not exist in Markdown, so the value is repeated: a
  header spanning three columns comes out as
  `| Provided To | Provided To | Provided To |`. The real structure stays in the
  `.json` file as `colspan`.
- **Drop caps** (the large letter at the start of a chapter) disappear:
  `This` becomes `his`.
- **Superscript footnote numbers** drop into the line.
- **Text drawn inside figures** does not come out as text; it stays in the image.

## Project layout

```text
src/pdftomd/
├── __main__.py        entry point for `python -m pdftomd`
├── cli.py             arguments, progress messages, exit codes
├── converter.py       the Docling conversion and the output paths
└── quality_report.py  compares the PDF with the Markdown
tests/                 one test file per module
docs/                  notes and open work
```

`pdftomd.bat` puts `src` on the import path and calls `python -m pdftomd`, so no
installation step is needed.

## Tests

```powershell
.venv\Scripts\python.exe -m unittest discover -s tests -t .
```
