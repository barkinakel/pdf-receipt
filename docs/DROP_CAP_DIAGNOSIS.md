# Decorative drop-cap diagnosis

## Outcome

The known `This chapter` → detached `T` / `his chapter` fixture behavior has two
distinct failure boundaries. Docling parsing/layout already represents the word
as two adjacent cells or blocks. Page-level and conversion-level assembly retain
that adjacency, but final DoclingDocument construction places unrelated content
between the fragments. The character is not absent from the PDF text layer, the
DoclingDocument, Docling JSON, or Markdown. Markdown serialization is faithful
to the final document and is not an additional failing stage.

No local repair is applied. Docling labels both fragments as ordinary BODY
`TextItem`s and exposes no drop-cap relationship. A generic size-and-proximity
heuristic could silently join legitimate one-letter labels, initials, chart
text, or column content. The single synthetic positive fixture is not enough
evidence to make false insertions unlikely, and the project must not guess a
leading letter.

## Captured evidence

The deterministic fixture draws `T` separately at 46 pt and
`his chapter begins with a decorative drop cap.` at 14 pt on the same baseline.
The checked-in PDF remains unchanged.

Measured offline on 2026-09-08 with Python 3.12.0, Docling 2.124.0,
Docling Core 2.93.0, and pypdfium2 5.13.0:

| Stage | Evidence | Result |
|---|---|---|
| PDF text layer | Offset 229 contains `This chapter begins with a decorative drop cap.` | Intact |
| PDF character geometry | `T`: `(54.966, 430.000)–(81.140, 462.936)`; `h`: `(86.924, 430.000)–(92.832, 440.024)` | Same baseline, adjacent |
| Parsed text-line cells | Cell 14 is `T`; cell 15 is `his chapter…` | Split, adjacent |
| Parsed word cells | Cell 33 is `T`; cell 34 is `his` | Split, adjacent |
| Layout clusters | Cluster positions 8 and 9 contain `T` and `his chapter…` | Split, adjacent |
| Page/conversion assembly | Body positions 8 and 9 contain the two fragments | Split, still adjacent |
| Final DoclingDocument | Both fragments are BODY `TextItem`s; a picture plus `Right column third` and `Right column fourth` occur between them | Reading-order adjacency lost |
| Markdown | Contains standalone `T`, then intervening blocks, then `his chapter…` | Faithful serialization of detached order |
| Docling JSON | Contains both text items | Raw evidence retained |

The Quality Report v2 extraction stage can expose the split/order mismatch. The
structural-integrity section correctly passes because its contract begins at the
already assembled DoclingDocument and checks serialization into Markdown.

## Reproduction

The source-layer assertion runs in the normal unit suite. The opt-in offline
integration test enables Docling's `generate_parsed_pages` diagnostic output and
checks parsed text lines, layout clusters, both assembled bodies, the final
document/JSON order, and the corresponding Markdown order:

```powershell
$env:HF_HUB_OFFLINE = "1"
$env:TRANSFORMERS_OFFLINE = "1"
$env:PDFTOMD_RUN_DOCLING_FIXTURES = "1"
.venv\Scripts\python.exe -m unittest discover -s tests\integration -t .
```

Missing cached models must remain a visible test failure; this diagnosis does
not authorize a download.

## Upstream report notes

If reported upstream, include the fixture PDF and these minimal facts:

- a large single-letter text object and its lowercase continuation share a
  baseline and are horizontally adjacent;
- PDFium returns the intact word with per-character boxes;
- Docling parsing/layout emits two adjacent fragments and page/conversion
  assembly retains their adjacency;
- final DoclingDocument construction moves a picture and right-column content
  between the two BODY text items; and
- the Markdown exporter reproduces that document order without further loss.

An upstream fix that emits the complete opening remains an accepted fixture
outcome. If a future local correction is considered, it needs several real
positive documents plus negative cases for initials, labels, charts, columns,
and intentionally separate one-letter paragraphs.
