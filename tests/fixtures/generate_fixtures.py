r"""Rebuild the tiny Milestone A PDF fixture corpus using only Python stdlib.

Run from the repository root:

    .venv\Scripts\python.exe tests\fixtures\generate_fixtures.py

The writer intentionally emits a small, fixed PDF 1.4 subset. It uses the PDF
standard Helvetica fonts, a ToUnicode map for the non-ASCII test characters,
and Flate-compressed RGB data for image-only content. No model, network access,
PDF package, or platform font is needed.
"""

from __future__ import annotations

import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PAGE_WIDTH = 612
PAGE_HEIGHT = 792


class PdfBuilder:
    def __init__(self) -> None:
        self.objects: list[bytes | None] = []

    def reserve(self) -> int:
        self.objects.append(None)
        return len(self.objects)

    def add(self, value: bytes) -> int:
        reference = self.reserve()
        self.set(reference, value)
        return reference

    def set(self, reference: int, value: bytes) -> None:
        self.objects[reference - 1] = value

    def stream(self, data: bytes, extra: bytes = b"") -> int:
        dictionary = b"<< /Length %d%s >>" % (len(data), extra)
        return self.add(dictionary + b"\nstream\n" + data + b"\nendstream")

    def write(self, path: Path, root_reference: int) -> None:
        if any(value is None for value in self.objects):
            raise RuntimeError("a reserved PDF object was not populated")
        output = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
        offsets = [0]
        for number, value in enumerate(self.objects, start=1):
            offsets.append(len(output))
            output.extend(f"{number} 0 obj\n".encode("ascii"))
            output.extend(value or b"")
            output.extend(b"\nendobj\n")
        xref = len(output)
        output.extend(f"xref\n0 {len(offsets)}\n".encode("ascii"))
        output.extend(b"0000000000 65535 f \n")
        for offset in offsets[1:]:
            output.extend(f"{offset:010d} 00000 n \n".encode("ascii"))
        output.extend(
            (
                f"trailer\n<< /Size {len(offsets)} /Root {root_reference} 0 R >>\n"
                f"startxref\n{xref}\n%%EOF\n"
            ).encode("ascii")
        )
        path.write_bytes(output)


def pdf_text(value: str) -> bytes:
    escaped = value.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
    return escaped.encode("cp1252")


SPECIAL_BYTES = {"İ": 128, "ı": 129, "ﬁ": 130, "ﬂ": 131, "ﬀ": 132}


def encoded_hex(value: str) -> bytes:
    data = bytes(SPECIAL_BYTES.get(character, ord(character)) for character in value)
    return data.hex().upper().encode("ascii")


def show(font: str, size: int, x: int, y: int, value: str) -> bytes:
    return (
        f"BT /{font} {size} Tf 1 0 0 1 {x} {y} Tm ".encode("ascii")
        + b"("
        + pdf_text(value)
        + b") Tj ET\n"
    )


def show_unicode(size: int, x: int, y: int, value: str) -> bytes:
    return (
        f"BT /FU {size} Tf 1 0 0 1 {x} {y} Tm <".encode("ascii")
        + encoded_hex(value)
        + b"> Tj ET\n"
    )


def common_fonts(pdf: PdfBuilder) -> tuple[int, int, int]:
    regular = pdf.add(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")
    bold = pdf.add(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold >>")
    cmap = b"""/CIDInit /ProcSet findresource begin
12 dict begin
begincmap
/CIDSystemInfo << /Registry (Adobe) /Ordering (UCS) /Supplement 0 >> def
/CMapName /FixtureUnicode def
/CMapType 2 def
1 begincodespacerange
<00> <FF>
endcodespacerange
5 beginbfchar
<80> <0130>
<81> <0131>
<82> <FB01>
<83> <FB02>
<84> <FB00>
endbfchar
endcmap
CMapName currentdict /CMap defineresource pop
end
end
"""
    cmap_reference = pdf.stream(cmap)
    unicode_font = pdf.add(
        (
            "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica "
            "/Encoding << /Type /Encoding /BaseEncoding /WinAnsiEncoding "
            "/Differences [128 /Idotaccent /dotlessi /fi /fl /ff] >> "
            f"/ToUnicode {cmap_reference} 0 R >>"
        ).encode("ascii")
    )
    return regular, bold, unicode_font


def resources(regular: int, bold: int, unicode_font: int, image: int | None = None) -> bytes:
    value = (
        f"<< /Font << /F1 {regular} 0 R /FB {bold} 0 R /FU {unicode_font} 0 R >>"
    )
    if image is not None:
        value += f" /XObject << /Im1 {image} 0 R >>"
    return (value + " >>").encode("ascii")


def add_page(
    pdf: PdfBuilder,
    pages_reference: int,
    content: bytes,
    page_resources: bytes,
    annotations: tuple[int, ...] = (),
) -> int:
    content_reference = pdf.stream(content)
    annotation_value = ""
    if annotations:
        annotation_value = " /Annots [" + " ".join(f"{ref} 0 R" for ref in annotations) + "]"
    return pdf.add(
        (
            f"<< /Type /Page /Parent {pages_reference} 0 R "
            f"/MediaBox [0 0 {PAGE_WIDTH} {PAGE_HEIGHT}] "
            f"/Resources "
        ).encode("ascii")
        + page_resources
        + f" /Contents {content_reference} 0 R{annotation_value} >>".encode("ascii")
    )


def finish_document(pdf: PdfBuilder, pages_reference: int, page_references: list[int], path: Path) -> None:
    kids = " ".join(f"{reference} 0 R" for reference in page_references)
    pdf.set(
        pages_reference,
        f"<< /Type /Pages /Kids [{kids}] /Count {len(page_references)} >>".encode("ascii"),
    )
    catalog = pdf.add(f"<< /Type /Catalog /Pages {pages_reference} 0 R >>".encode("ascii"))
    pdf.write(path, catalog)


def make_text_tokens() -> None:
    pdf = PdfBuilder()
    pages = pdf.reserve()
    regular, bold, unicode_font = common_fonts(pdf)
    page_resources = resources(regular, bold, unicode_font)

    first = bytearray()
    first += show("FB", 22, 54, 738, "Token Regression Fixture")
    first += show("F1", 12, 54, 706, "Turkish dotted and dotless forms:")
    first += show_unicode(16, 245, 706, "İ I i ı")
    first += show("F1", 12, 54, 678, "Unicode ligatures:")
    first += show_unicode(16, 165, 678, "ﬁ ﬂ ﬀ")
    first += show("F1", 12, 54, 644, "A ve 7 42 are short and numeric tokens.")
    first += show("F1", 12, 54, 616, "A genuine risk-based compound keeps its hyphen.")
    first += show("F1", 12, 54, 576, "Line-end hyphen-")
    first += show("F1", 12, 54, 550, "ation joins conservatively.")
    first += show("F1", 12, 54, 512, "echo echo occur twice on this page.")
    page_one = add_page(pdf, pages, bytes(first), page_resources)

    second = bytearray()
    second += show("FB", 18, 54, 738, "Second Page")
    second += show("F1", 12, 54, 704, "echo occurs again across a page boundary.")
    page_two = add_page(pdf, pages, bytes(second), page_resources)
    finish_document(pdf, pages, [page_one, page_two], ROOT / "text_tokens.pdf")


def illustration_pixels(width: int, height: int) -> bytes:
    output = bytearray()
    for y in range(height):
        for x in range(width):
            if (x // 12 + y // 12) % 2:
                output.extend((39, 103, 173))
            else:
                output.extend((242, 190, 52))
    return bytes(output)


def add_rgb_image(pdf: PdfBuilder, width: int, height: int, pixels: bytes) -> int:
    compressed = zlib.compress(pixels, level=9)
    extra = (
        f" /Type /XObject /Subtype /Image /Width {width} /Height {height} "
        "/ColorSpace /DeviceRGB /BitsPerComponent 8 /Filter /FlateDecode"
    ).encode("ascii")
    return pdf.stream(compressed, extra)


def make_structure_layout() -> None:
    pdf = PdfBuilder()
    pages = pdf.reserve()
    regular, bold, unicode_font = common_fonts(pdf)
    image = add_rgb_image(pdf, 96, 72, illustration_pixels(96, 72))
    annotation = pdf.add(
        b"<< /Type /Annot /Subtype /Link /Rect [54 575 245 592] /Border [0 0 0] "
        b"/A << /S /URI /URI (https://example.com/fixture) >> >>"
    )

    content = bytearray()
    content += show("FB", 24, 54, 742, "Fixture Structure")
    content += show("F1", 12, 54, 710, "- first retained list item")
    content += show("F1", 12, 54, 690, "- second retained list item")
    content += show("F1", 12, 54, 650, "Metric")
    content += show("F1", 12, 210, 650, "Small")
    content += show("F1", 12, 330, 650, "Large")
    content += show("F1", 12, 54, 628, "Count")
    content += show("F1", 12, 210, 628, "7")
    content += show("F1", 12, 330, 628, "42")
    content += b"0.5 w 50 618 m 430 618 l 430 668 l 50 668 l h S\n"
    content += b"195 618 m 195 668 l S 315 618 m 315 668 l S 50 642 m 430 642 l S\n"
    content += show("F1", 12, 54, 578, "Project site: https://example.com/fixture")
    content += b"q 120 0 0 90 430 570 cm /Im1 Do Q\n"
    # Deliberately scramble content-stream order. A converter must recover the
    # spatial order (left column top-to-bottom, then right column) from layout.
    content += show("FB", 14, 330, 520, "Right column third")
    content += show("FB", 14, 54, 520, "Left column first")
    content += show("F1", 11, 330, 500, "Right column fourth")
    content += show("F1", 11, 54, 500, "Left column second")
    content += show("FB", 46, 54, 430, "T")
    content += show("F1", 14, 86, 430, "his chapter begins with a decorative drop cap.")

    page = add_page(
        pdf,
        pages,
        bytes(content),
        resources(regular, bold, unicode_font, image),
        (annotation,),
    )
    finish_document(pdf, pages, [page], ROOT / "structure_layout.pdf")


GLYPHS = {
    "A": ("01110", "10001", "10001", "11111", "10001", "10001", "10001"),
    "C": ("01111", "10000", "10000", "10000", "10000", "10000", "01111"),
    "D": ("11110", "10001", "10001", "10001", "10001", "10001", "11110"),
    "E": ("11111", "10000", "10000", "11110", "10000", "10000", "11111"),
    "G": ("01111", "10000", "10000", "10111", "10001", "10001", "01111"),
    "N": ("10001", "11001", "10101", "10011", "10001", "10001", "10001"),
    "P": ("11110", "10001", "10001", "11110", "10000", "10000", "10000"),
    "S": ("01111", "10000", "10000", "01110", "00001", "00001", "11110"),
}


def scanned_pixels(width: int, height: int) -> bytes:
    pixels = bytearray([255] * (width * height * 3))
    phrase = "SCANNED PAGE"
    scale = 12
    advance = 6 * scale
    total_width = sum(advance if character != " " else 4 * scale for character in phrase)
    x = (width - total_width) // 2
    y = (height - 7 * scale) // 2
    for character in phrase:
        if character == " ":
            x += 4 * scale
            continue
        for row, pattern in enumerate(GLYPHS[character]):
            for column, bit in enumerate(pattern):
                if bit == "0":
                    continue
                for dy in range(scale):
                    for dx in range(scale):
                        px = x + column * scale + dx
                        py = y + row * scale + dy
                        offset = (py * width + px) * 3
                        pixels[offset : offset + 3] = b"\x00\x00\x00"
        x += advance
    return bytes(pixels)


def make_scanned_page() -> None:
    width, height = 1000, 500
    pdf = PdfBuilder()
    pages = pdf.reserve()
    regular, bold, unicode_font = common_fonts(pdf)
    image = add_rgb_image(pdf, width, height, scanned_pixels(width, height))
    content = b"q 540 0 0 270 36 250 cm /Im1 Do Q\n"
    page = add_page(
        pdf,
        pages,
        content,
        resources(regular, bold, unicode_font, image),
    )
    finish_document(pdf, pages, [page], ROOT / "scanned_page.pdf")


def main() -> None:
    make_text_tokens()
    make_structure_layout()
    make_scanned_page()


if __name__ == "__main__":
    main()
