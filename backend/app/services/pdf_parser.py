"""Native PDF text extraction with PyMuPDF. Rebuilds table rows from word coordinates."""
from dataclasses import dataclass

import pymupdf as fitz  # PyMuPDF


@dataclass
class PageText:
    page: int
    text: str
    needs_ocr: bool


def _rows_from_words(page: "fitz.Page") -> str:
    words = page.get_text("words")  # x0, y0, x1, y1, word, block, line, wno
    if not words:
        return ""
    heights = sorted(w[3] - w[1] for w in words)
    tol = max(2.0, heights[len(heights) // 2] * 0.6)
    words = sorted(words, key=lambda w: ((w[1] + w[3]) / 2, w[0]))
    rows: list[list] = []
    centers: list[float] = []
    for w in words:
        cy = (w[1] + w[3]) / 2
        if rows and abs(cy - centers[-1]) <= tol:
            rows[-1].append(w)
            centers[-1] = (centers[-1] * (len(rows[-1]) - 1) + cy) / len(rows[-1])
        else:
            rows.append([w])
            centers.append(cy)
    return "\n".join(" ".join(x[4] for x in sorted(r, key=lambda w: w[0])) for r in rows)


def parse_pdf(path: str, min_chars: int, max_pages: int) -> list[PageText]:
    doc = fitz.open(path)
    try:
        if doc.needs_pass:
            raise ValueError("The PDF is password protected.")
        if doc.page_count > max_pages:
            raise ValueError(f"The PDF has {doc.page_count} pages; the limit is {max_pages}.")
        pages = []
        for i, page in enumerate(doc, start=1):
            text = _rows_from_words(page)
            pages.append(PageText(i, text, needs_ocr=len(text.strip()) < min_chars))
        return pages
    finally:
        doc.close()


def render_page_png(path: str, page_number: int, dpi: int = 300) -> bytes:
    doc = fitz.open(path)
    try:
        return doc[page_number - 1].get_pixmap(dpi=dpi).tobytes("png")
    finally:
        doc.close()
