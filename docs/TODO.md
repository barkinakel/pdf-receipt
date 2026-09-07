# Next up

Work that has not been scheduled or decided yet. Delete an entry once it is done.

## 1. `--html-tables` — tables with merged cells

Markdown pipe tables have no `colspan`, so a header spanning three columns is
repeated as `| Provided To | Provided To | Provided To |`. The real structure
sits in the `.json` file as `colspan="3"`, so no data is actually lost.

The fix would be to write those tables into the Markdown as HTML. Docling has a
`table_serializer` hook (`docling_core.transforms.serializer.markdown`), and
`TableItem.export_to_html(doc)` already produces merged cells and the table
caption (`<caption>`) correctly. Roughly 25 lines of work.

Suggested behaviour: mixed — only tables that actually contain merged cells
become HTML, ordinary tables stay pipe tables. Off by default, enabled by a flag.

**Decision: not doing it for now.** Measurements (NIST SP 800-30, 95 pages):

- 27 of the 55 tables contain merged cells, so half of the document's tables
  would turn into HTML blocks. That is not a rare exception.
- None of the 1211 table cells contain a line break, so HTML would **not** fix
  the real annoyance — bullet lists inside a cell collapsing into
  `- Outsider - Insider`. That information is already gone at extraction time.
- The current repetition is not a loss of information: every column carries its
  own header, which on the machine side (search, feeding an LLM) is more useful
  than a merged cell.

The only gain is visual: the merged header spans like it does in the PDF, and
the table caption sticks to the table. The cost is an unreadable `.md` source
and tables that vanish entirely in tools that strip HTML.

If it comes up again: worth it when the Markdown is meant to be shown or printed
as a document, not worth it for personal reading and lookup.

## 2. Image resolution

Extracted images are 72 DPI (`images_scale=1.0`). The figures in the NIST
document came out at 433x214 pixels, which is blurry when enlarged.
`images_scale=2.0` gives 144 DPI, `3.0` gives 216 DPI, at the cost of larger
files and a slower conversion.

## 3. Lost drop caps

The large decorative letter at the start of a chapter disappears:
`This chapter` becomes `his chapter`. It happens at a few chapter openings in
the NIST document. Why Docling does not keep that letter (is it treated as a
picture, or as a separate text block?) has not been investigated. Find the cause
first, then decide whether to fix it.

## 4. A real `--formula` test

Unit tests cover the flag and the pipeline wiring, but a live conversion has
never run: about 209 MB of the 631 MB CodeFormulaV2 model has been downloaded,
the rest is still pending. A ready test file lives at
`scratchpad/smoke/input/formulas.pdf` (inside the session folder, so it may be
gone — it can be regenerated).

## 5. Skip already converted files — possible follow-up

## 6. Quality Report v2

External tools, benchmarks, and the adoption decision are recorded in
[QUALITY_REPORT_RESEARCH.md](QUALITY_REPORT_RESEARCH.md).

Replace the single bag-of-words score with a two-stage report:

```text
PDF text layer -> DoclingDocument -> Markdown
 extraction quality                serialization quality
```

Phase 1 should add no dependencies:

- Normalize Unicode, ligatures, punctuation variants, and words hyphenated
  across line breaks before comparing.
- Align ordered tokens and retain PDF page provenance. This must count repeated
  words correctly and report deletions, substitutions, and unexpected additions.
- Show separate exact-transfer, accounted-for, unexplained-loss, and
  unexpected-addition rates. Expected figure text, page furniture, and glued
  footnote numbers should improve accounted-for coverage without hiding the raw
  transfer rate.
- Include surrounding text with each unexplained sample instead of listing an
  isolated word only.
- Compare Docling structure with the serialized Markdown: heading/list/table
  counts, table cell text, image link count, link targets, artifact existence,
  non-empty files, and decodable image dimensions.
- Preserve the current console summary and report path while expanding the
  detailed report. Keep old fields long enough for compatibility with tests.

Phase 2 can add optional scanned-document checks:

- Use OCR confidence metadata if Docling exposes it reliably.
- Optionally compare against a second OCR engine and flag disagreements.
- Mark OCR-only pages as unverified and provide page previews or review targets.

An OCR-only page has no independent ground truth, so no implementation should
present OCR agreement or confidence as a guaranteed accuracy percentage. Table
geometry and visual formatting also need their own structural metrics; word
coverage alone cannot validate them.
