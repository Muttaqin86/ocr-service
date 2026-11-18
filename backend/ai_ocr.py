"""AI-based OCR helpers using EasyOCR (deep learning) with Tesseract fallback."""

from __future__ import annotations

import io
import os
from dataclasses import dataclass, field
from typing import List, Tuple

import fitz  # PyMuPDF
import numpy as np
from PIL import Image, ImageOps

# Lokasi tessdata Tesseract (macOS Homebrew)
TESSDATA_DIR = "/opt/homebrew/share/tessdata"
if not os.path.isdir(TESSDATA_DIR):
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
    language: str = "id+en"
    total_chars: int = 0

    def __post_init__(self):
        self.total_chars = sum(p.char_count for p in self.pages)


MIN_TEXT_CHARS = 20
_easyocr_reader = None
_easyocr_lang_cache = None


def _get_easyocr_reader(langs: str):
    """Lazy-load EasyOCR reader with Apple Silicon GPU (MPS) acceleration if available."""
    global _easyocr_reader, _easyocr_lang_cache
    try:
        import easyocr  # type: ignore
    except ImportError:
        return None

    lang_list = [l.strip() for l in (langs or "").replace(" ", "").split("+") if l.strip()]
    if not lang_list:
        lang_list = ["id", "en"]
    lang_key = "+".join(sorted(lang_list))

    if _easyocr_reader is None or _easyocr_lang_cache != lang_key:
        try:
            _easyocr_reader = easyocr.Reader(lang_list, gpu=True)
            _easyocr_lang_cache = lang_key
        except Exception:
            try:
                _easyocr_reader = easyocr.Reader(lang_list, gpu=False)
                _easyocr_lang_cache = lang_key
            except Exception:
                _easyocr_reader = None
                return None

    return _easyocr_reader


def available_languages() -> List[str]:
    """Return common EasyOCR language codes if installed."""
    try:
        import easyocr  # type: ignore
        return ["id", "en", "ar", "ch_sim", "ja", "ko", "th", "vi"]
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


def _group_boxes_into_lines(results) -> Tuple[str, float]:
    """
    Mengelompokkan bounding box EasyOCR ke dalam baris horizontal dengan toleransi ketat
    agar baris tabel yang rapat tidak saling bertabrakan.
    """
    if not results:
        return "", 0.0

    items = []
    confs = []
    for bbox, text, conf in results:
        clean_text = text.strip()
        if not clean_text:
            continue
        x_min = min(pt[0] for pt in bbox)
        x_max = max(pt[0] for pt in bbox)
        y_min = min(pt[1] for pt in bbox)
        y_max = max(pt[1] for pt in bbox)
        y_center = (y_min + y_max) / 2.0
        height = max(1.0, y_max - y_min)
        items.append({
            "x_min": x_min,
            "x_max": x_max,
            "y_min": y_min,
            "y_max": y_max,
            "y_center": y_center,
            "height": height,
            "text": clean_text,
        })
        confs.append(conf)

    if not items:
        return "", 0.0

    # Urutkan dari atas ke bawah berdasarkan y_center
    items.sort(key=lambda it: it["y_center"])

    lines = []
    current_line = [items[0]]

    for item in items[1:]:
        # Bandingkan dengan kotak terakhir atau rata-rata baris aktif
        ref_y = sum(x["y_center"] for x in current_line) / len(current_line)
        ref_h = min(x["height"] for x in current_line)

        # Toleransi diperketat ke 38% dari tinggi huruf terkecil (mencegah 2 baris rapat menyatu)
        if abs(item["y_center"] - ref_y) <= (ref_h * 0.38):
            current_line.append(item)
        else:
            lines.append(current_line)
            current_line = [item]

    lines.append(current_line)

    # Susun teks tiap baris dari kiri ke kanan (x_min)
    formatted_lines = []
    for line in lines:
        line.sort(key=lambda x: x["x_min"])
        line_parts = [line[0]["text"]]
        for i in range(1, len(line)):
            gap = line[i]["x_min"] - line[i - 1]["x_max"]
            avg_h = line[i]["height"]
            if gap > avg_h * 1.8:
                line_parts.append("   |   " + line[i]["text"])
            else:
                line_parts.append(" " + line[i]["text"])
        formatted_lines.append("".join(line_parts))

    avg_conf = (sum(confs) / len(confs) * 100) if confs else 0.0
    return "\n".join(formatted_lines).strip(), round(avg_conf, 2)


def _ocr_image_easyocr(
    data: bytes,
    lang: str = "id+en",
    preprocess: bool = True,
    scale: float = 1.5,
) -> Tuple[str, float]:
    """Run EasyOCR on image bytes with layout line reconstruction."""
    reader = _get_easyocr_reader(lang)
    if reader is None:
        raise RuntimeError("EasyOCR tidak tersedia. Install: pip install easyocr")

    image = Image.open(io.BytesIO(data))
    image = ImageOps.exif_transpose(image)
    if image.mode != "RGB":
        image = image.convert("RGB")

    # Upscale gambar resolusi kecil/sedang saat preprocess aktif agar angka kecil terbaca jelas
    if preprocess and scale > 1.0:
        w, h = image.size
        if max(w, h) < 2500:
            new_size = (int(w * scale), int(h * scale))
            image = image.resize(new_size, Image.Resampling.LANCZOS)

    arr = np.array(image)
    results = reader.readtext(arr, detail=1, paragraph=False, width_ths=0.4, height_ths=0.4)

    return _group_boxes_into_lines(results)


# Mapping kode bahasa EasyOCR -> Tesseract
_LANG_MAP = {
    "en": "eng",
    "id": "ind",
    "id+en": "ind+eng",
    "en+id": "eng+ind",
    "ar": "ara",
    "zh": "chi_sim",
    "ch_sim": "chi_sim",
    "ja": "jpn",
    "ko": "kor",
    "ru": "rus",
    "th": "tha",
    "vi": "vie",
}


def _ocr_image_tesseract_fallback(data: bytes, lang: str = "eng") -> Tuple[str, float]:
    """Fallback to Tesseract if EasyOCR fails or is not installed."""
    import pytesseract

    image = Image.open(io.BytesIO(data))
    image = ImageOps.exif_transpose(image)
    if image.mode not in ("RGB", "L"):
        image = image.convert("RGB").convert("L")
    else:
        image = image.convert("L")

    tesseract_lang = _LANG_MAP.get(lang, lang)
    tess_cfg = f"--tessdata-dir {TESSDATA_DIR}"
    text = pytesseract.image_to_string(image, lang=tesseract_lang, config=tess_cfg).strip()
    try:
        d = pytesseract.image_to_data(
            image, lang=tesseract_lang, config=tess_cfg, output_type=pytesseract.Output.DICT
        )
        confs = [float(c) for c in d["conf"] if float(c) > 0]
        avg_conf = (sum(confs) / len(confs)) if confs else 0.0
    except Exception:
        avg_conf = 0.0
    return text, round(avg_conf, 2)


def ocr_image_bytes(
    data: bytes,
    lang: str = "id+en",
    preprocess: bool = True,
    scale: float = 1.5,
    deskew: bool = True,
    binarize: bool = False,
) -> Tuple[str, float]:
    """OCR image using AI (EasyOCR) with Tesseract fallback."""
    try:
        return _ocr_image_easyocr(data, lang=lang, preprocess=preprocess, scale=scale)
    except Exception:
        return _ocr_image_tesseract_fallback(data, lang=lang)


def ocr_pdf_bytes(
    data: bytes,
    lang: str = "id+en",
    dpi: int = 200,
    force_ocr: bool = False,
    preprocess: bool = True,
    scale: float = 1.5,
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