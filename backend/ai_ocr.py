
"""AI-based OCR helpers using EasyOCR (deep learning) with Tesseract fallback."""

from __future__ import annotations

import os
import io
import shutil
from dataclasses import dataclass, field
from typing import List, Tuple

import fitz  # PyMuPDF
import numpy as np
from PIL import Image

# Lokasi tessdata Tesseract (macOS Homebrew)
TESSDATA_DIR = "/opt/homebrew/share/tessdata"
if not os.path.isdir(TESSDATA_DIR):
    # Coba lokasi alternatif
    for cand in ["/usr/local/share/tessdata", "/usr/share/tessdata"]:
        if os.path.isdir(cand):
            TESSDATA_DIR = cand
            break


@dataclass
class PageResult:
    page: int
    text: str
    method: str  # "ai" | "text" | "mixed"
    char_count: int = 0
    confidence: float = 0.0

    def __post_init__(self):
        self.char_count = len(self.text.strip())


@dataclass
class OcrResult:
    filename: str
    pages: List[PageResult] = field(default_factory=list)
    language: str = "en"
    total_chars: int = 0

    def __post_init__(self):
        self.total_chars = sum(p.char_count for p in self.pages)


MIN_TEXT_CHARS = 20
_easyocr_reader = None
_easyocr_lang_cache = None


def _get_easyocr_reader(langs: str):
    """Lazy-load EasyOCR reader. Returns None if EasyOCR not installed."""
    global _easyocr_reader, _easyocr_lang_cache
    try:
        import easyocr  # type: ignore
    except ImportError:
        return None

    lang_list = [l.strip() for l in langs.replace(" ", "").split("+") if l.strip()]
    if not lang_list:
        lang_list = ["en"]
    lang_key = "+".join(sorted(lang_list))

    if _easyocr_reader is None or _easyocr_lang_cache != lang_key:
        try:
            _easyocr_reader = easyocr.Reader(lang_list, gpu=False)
            _easyocr_lang_cache = lang_key
        except Exception:
            _easyocr_reader = None
            return None

    return _easyocr_reader


def available_languages() -> List[str]:
    """Return EasyOCR languages if installed, otherwise empty list."""
    try:
        import easyocr  # type: ignore
        return []
    except ImportError:
        return []
    except Exception:
        return []


def validate_lang(lang: str) -> None:
    """EasyOCR supports many languages; validate loosely."""
    langs = available_languages()
    if not langs:
        return
    for part in (lang or "").replace(" ", "").split("+"):
        if part and part not in langs:
            raise ValueError(
                f"Language pack '{part}' is not installed for AI OCR. "
                f"Available: {', '.join(langs)}"
            )


def _ocr_image_easyocr(data: bytes, lang: str = "en") -> Tuple[str, float]:
    """Run EasyOCR on image bytes. Returns (text, confidence)."""
    reader = _get_easyocr_reader(lang)
    if reader is None:
        raise RuntimeError("EasyOCR tidak tersedia. Install: pip install easyocr")

    image = Image.open(io.BytesIO(data))
    if image.mode not in ("RGB", "L"):
        image = image.convert("RGB")

    arr = np.array(image)
    results = reader.readtext(arr)

    texts = []
    confs = []
    for bbox, text, conf in results:
        texts.append(text)
        confs.append(conf)

    full_text = "\n".join(texts)
    avg_conf = (sum(confs) / len(confs) * 100) if confs else 0.0
    return full_text.strip(), round(avg_conf, 2)


# Mapping kode bahasa EasyOCR -> Tesseract
_LANG_MAP = {
    "en": "eng",
    "id": "ind",
    "ar": "ara",
    "zh": "chi_sim",
    "ja": "jpn",
    "ko": "kor",
    "ru": "rus",
    "th": "th",
    "vi": "vie",
}


def _ocr_image_tesseract_fallback(data: bytes, lang: str = "eng") -> Tuple[str, float]:
    """Fallback to Tesseract if EasyOCR is not installed."""
    import pytesseract
    from PIL import Image, ImageOps

    image = Image.open(io.BytesIO(data))
    if image.mode not in ("RGB", "L"):
        image = image.convert("RGB").convert("L")
    else:
        image = image.convert("L")

    image = ImageOps.exif_transpose(image)
    tesseract_lang = _LANG_MAP.get(lang, lang)
    tess_cfg = f"--tessdata-dir {TESSDATA_DIR}"
    text = pytesseract.image_to_string(image, lang=tesseract_lang, config=tess_cfg).strip()
    try:
        d = pytesseract.image_to_data(image, lang=tesseract_lang, config=tess_cfg, output_type=pytesseract.Output.DICT)
        confs = [float(c) for c in d['conf'] if float(c) > 0]
        avg_conf = (sum(confs) / len(confs)) if confs else 0.0
    except Exception:
        avg_conf = 0.0
    return text, round(avg_conf, 2)


def ocr_image_bytes(
    data: bytes,
    lang: str = "en",
    preprocess: bool = True,
    scale: float = 2.0,
    deskew: bool = True,
    binarize: bool = False,
) -> Tuple[str, float]:
    """OCR image using AI (EasyOCR) with Tesseract fallback."""
    try:
        return _ocr_image_easyocr(data, lang=lang)
    except Exception:
        # Fallback to Tesseract LSTM
        return _ocr_image_tesseract_fallback(data, lang=lang)


def ocr_pdf_bytes(
    data: bytes,
    lang: str = "en",
    dpi: int = 200,
    force_ocr: bool = False,
    preprocess: bool = True,
    scale: float = 2.0,
    deskew: bool = True,
    binarize: bool = False,
) -> OcrResult:
    """OCR PDF using AI (EasyOCR), extracting native text first where available."""
    doc = fitz.open(stream=data, filetype="pdf")
    pages: List[PageResult] = []

    for i, page in enumerate(doc):
        text = page.get_text("text").strip()

        if force_ocr or len(text) < MIN_TEXT_CHARS:
            pix = page.get_pixmap(dpi=dpi)
            img_bytes = pix.tobytes("png")
            ocr_text, conf = ocr_image_bytes(
                img_bytes,
                lang=lang,
                preprocess=preprocess,
                scale=scale,
                deskew=deskew,
                binarize=binarize,
            )
            if text and ocr_text:
                if text.strip() in ocr_text or ocr_text in text.strip():
                    combined = text if len(text) >= len(ocr_text) else ocr_text
                    method = "text" if len(text) >= len(ocr_text) else "ai"
                else:
                    combined = text + "\n" + ocr_text
                    method = "mixed"
            elif ocr_text:
                combined = ocr_text
                method = "ai"
            else:
                combined = text
                method = "text"
            pages.append(PageResult(page=i + 1, text=combined.strip(), method=method, confidence=conf))
        else:
            pages.append(PageResult(page=i + 1, text=text, method="text", confidence=100.0))

    filename = getattr(doc, "name", None) or "document.pdf"
    doc.close()
    return OcrResult(filename=filename, pages=pages, language=lang)


def pdf_page_count(data: bytes) -> int:
    doc = fitz.open(stream=data, filetype="pdf")
    n = doc.page_count
    doc.close()
    return n
