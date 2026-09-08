# Regression fixtures

This directory is the small, checked-in Milestone A corpus. Each PDF has an
adjacent `*.facts.json` file containing explicit content, order, structure, link,
and artifact assertions. The normal unit suite validates the corpus and the
fact harness without loading Docling.

The PDFs are deterministic outputs of `generate_fixtures.py`. The generator
uses only the Python standard library and PDF standard fonts; it needs no
network access, model, package, or platform font. Rebuild them from the
repository root with:

```powershell
.venv\Scripts\python.exe tests\fixtures\generate_fixtures.py
```

Live Docling checks are deliberately separate from fast unit tests. Complete
the documented first conversion so the models are cached, force Hugging Face
offline mode, and opt in explicitly:

```powershell
$env:HF_HUB_OFFLINE = "1"
$env:TRANSFORMERS_OFFLINE = "1"
$env:PDFTOMD_RUN_DOCLING_FIXTURES = "1"
.venv\Scripts\python.exe -m unittest discover -s tests\integration -t .
```

With offline mode set, a missing model is a visible test failure instead of a
surprise download. The scanned fixture requires the quality profile; the two
born-digital fixtures use the same profile so the run shares one runtime.

The structure fixture deliberately places its two-column text in scrambled PDF
content-stream order; its ordered fact requires the spatial reading order. Its
current Docling output also records two explicit, accepted limitations rather
than treating them as successes:

- the PDF link annotation is not serialized as a Markdown link, and its literal
  URL is folded into a table row and repeated in all three cells;
- the decorative `T` is detached from `his chapter...`. The PDF text layer has
  the intact phrase. Docling 2.124.0 parsing/layout creates two adjacent pieces;
  page and conversion assembly keep them adjacent, but final document assembly
  puts unrelated blocks between the BODY `TextItem`s. Markdown faithfully
  serializes that detached document order. See `docs/DROP_CAP_DIAGNOSIS.md`.

Each limitation fact also accepts the corrected outcome, so a future upstream
or project fix will not permanently bake the loss into the corpus contract.
