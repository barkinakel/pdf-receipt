"""Generate an original formula PDF using only the existing stdlib PDF writer."""

from __future__ import annotations

import sys
from pathlib import Path

FIXTURES = Path(__file__).resolve().parents[1]
if str(FIXTURES) not in sys.path:
    sys.path.insert(0, str(FIXTURES))

from generate_fixtures import PdfBuilder, add_page, finish_document, show


def generate(path: Path) -> None:
    pdf = PdfBuilder()
    pages = pdf.reserve()
    regular = pdf.add(b"<< /Type /Font /Subtype /Type1 /BaseFont /Times-Roman >>")
    italic = pdf.add(b"<< /Type /Font /Subtype /Type1 /BaseFont /Times-Italic >>")
    bold = pdf.add(b"<< /Type /Font /Subtype /Type1 /BaseFont /Times-Bold >>")
    resources = f"<< /Font << /F1 {regular} 0 R /FI {italic} 0 R /FB {bold} 0 R >> >>".encode()
    content = b"".join([
        show("FB", 20, 60, 730, "Formula Conversion Fixture"),
        show("F1", 12, 60, 680, "The first equation states the relation between three squared lengths."),
        show("FI", 22, 220, 620, "a"), show("F1", 12, 232, 631, "2"),
        show("F1", 22, 248, 620, "+"), show("FI", 22, 272, 620, "b"),
        show("F1", 12, 284, 631, "2"), show("F1", 22, 302, 620, "="),
        show("FI", 22, 328, 620, "c"), show("F1", 12, 340, 631, "2"),
        show("F1", 12, 60, 560, "The squared terms belong to the equation above, not this sentence."),
        show("F1", 12, 60, 500, "The second equation divides one sum by another sum."),
        show("FI", 22, 222, 426, "x"), show("F1", 22, 246, 426, "="),
        show("FI", 20, 281, 443, "a + b"),
        b"0.8 w 276 436 m 337 436 l S\n",
        show("FI", 20, 281, 413, "c + d"),
        show("F1", 12, 60, 350, "The denominator is the sum of c and d. This concludes the example."),
    ])
    page = add_page(pdf, pages, content, resources)
    finish_document(pdf, pages, [page], path)


if __name__ == "__main__":
    generate(Path(__file__).with_name("formula_equations.pdf"))
