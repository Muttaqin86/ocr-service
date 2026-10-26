"""Core OCR helpers for images and PDFs."""

from __future__ import annotations

import io
from dataclasses import dataclass, field
from typing import List

import fitz  # PyMuPDF
import pytesseract
from PIL import Image


@dataclass
class PageResult:
    page: int
    text: str
    method: str  # "text" | "ocr" | "mixed"
    char_count: int = 0

    def __post_init__(self):
        self.char_count = len(self.text.strip())


@dataclass
class OcrResult:
    filename: str
    pages: List[PageResult] = field(default_factory=list)
    language: str = "eng"
    total_chars: int = 0

    def __post_init__(self):
        self.total_chars = sum(p.char_count for p in self.pages)


MIN_TEXT_CHARS = 20  # below this, treat page as scanned and run OCR


def ocr_image_bytes(data: bytes, lang: str = "eng", psm: int = 6) -> str:
    """Run Tesseract OCR on raw image bytes."""
    image = Image.open(io.BytesIO(data))
    if image.mode not in ("RGB", "L"):
        image = image.convert("RGB")
    config = f"--psm {psm}"
    return pytesseract.image_to_string(image, lang=lang, config=config).strip()


def ocr_pdf_bytes(
    data: bytes,
    lang: str = "eng",
    dpi: int = 200,
    force_ocr: bool = False,
) -> OcrResult:
    """Extract text from a PDF, falling back to OCR for scanned pages."""
    doc = fitz.open(stream=data, filetype="pdf")
    pages: List[PageResult] = []

    for i, page in enumerate(doc):
        text = page.get_text("text").strip()

        if force_ocr or len(text) < MIN_TEXT_CHARS:
            pix = page.get_pixmap(dpi=dpi)
            img_bytes = pix.tobytes("png")
            ocr_text = ocr_image_bytes(img_bytes, lang=lang)
            if text and ocr_text:
                if text.strip() in ocr_text or ocr_text in text.strip():
                    combined = text if len(text) >= len(ocr_text) else ocr_text
                    method = "text" if len(text) >= len(ocr_text) else "ocr"
                else:
                    combined = text + "\n" + ocr_text
                    method = "mixed"
            elif ocr_text:
                combined = ocr_text
                method = "ocr"
            else:
                combined = text
                method = "text"
            pages.append(PageResult(page=i + 1, text=combined.strip(), method=method))
        else:
            pages.append(PageResult(page=i + 1, text=text, method="text"))

    filename = getattr(doc, "name", None) or "document.pdf"
    doc.close()
    return OcrResult(filename=filename, pages=pages, language=lang)


def pdf_page_count(data: bytes) -> int:
    doc = fitz.open(stream=data, filetype="pdf")
    n = doc.page_count
    doc.close()
    return n
