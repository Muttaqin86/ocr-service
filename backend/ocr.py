"""Core OCR helpers for images and PDFs."""

from __future__ import annotations

import io
from dataclasses import dataclass, field
from typing import List, Tuple

import fitz  # PyMuPDF
import numpy as np
import pytesseract
from PIL import Image, ImageEnhance, ImageFilter, ImageOps


@dataclass
class PageResult:
    page: int
    text: str
    method: str  # "text" | "ocr" | "mixed"
    char_count: int = 0
    confidence: float = 0.0

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


def available_languages() -> List[str]:
    """Return the list of Tesseract language packs installed on the system."""
    try:
        return list(pytesseract.get_languages(config=""))
    except Exception:
        return []


def validate_lang(lang: str) -> None:
    """Raise ValueError if any requested language pack is missing."""
    langs = available_languages()
    if not langs:
        return
    for part in (lang or "").replace(" ", "").split("+"):
        if part and part not in langs:
            raise ValueError(
                f"Language pack '{part}' is not installed. "
                f"Available: {', '.join(langs)}. "
                "Install extra packs, e.g. `brew install tesseract-lang` (macOS)."
            )


def _otsu_threshold(arr: np.ndarray) -> int:
    hist, _ = np.histogram(arr, bins=256, range=(0, 256))
    total = arr.size
    sum_total = float(np.dot(np.arange(256), hist))
    sum_b = 0.0
    w_b = 0
    max_var = 0.0
    threshold = 127
    for t in range(256):
        w_b += int(hist[t])
        if w_b == 0:
            continue
        w_f = total - w_b
        if w_f == 0:
            break
        sum_b += t * int(hist[t])
        m_b = sum_b / w_b
        m_f = (sum_total - sum_b) / w_f
        var_between = w_b * w_f * (m_b - m_f) ** 2
        if var_between > max_var:
            max_var = var_between
            threshold = t
    return threshold


def _estimate_skew_angle(gray_small: Image.Image) -> float:
    """Estimate skew angle using horizontal projection variance."""
    best_angle = 0.0
    best_score = -1.0
    for i in range(-20, 21):
        angle = i * 0.5
        rotated = gray_small.rotate(angle, resample=Image.BILINEAR, expand=False, fillcolor=255)
        arr = np.asarray(rotated, dtype=np.float64)
        proj = arr.mean(axis=1)
        score = float(np.var(proj))
        if score > best_score:
            best_score = score
            best_angle = angle
    for d in range(-5, 6):
        angle = best_angle + d * 0.1
        rotated = gray_small.rotate(angle, resample=Image.BILINEAR, expand=False, fillcolor=255)
        arr = np.asarray(rotated, dtype=np.float64)
        proj = arr.mean(axis=1)
        score = float(np.var(proj))
        if score > best_score:
            best_score = score
            best_angle = angle
    return best_angle


def preprocess_image(
    image: Image.Image,
    scale: float = 2.0,
    deskew: bool = True,
    binarize: bool = False,
) -> Image.Image:
    """Improve OCR accuracy: EXIF fix, grayscale, upscale, deskew, denoise, enhance, binarize."""
    image = ImageOps.exif_transpose(image)

    if image.mode not in ("L", "I", "F"):
        image = image.convert("RGB").convert("L")
    else:
        image = image.convert("L")

    w, h = image.size
    if max(w, h) < 1000 and scale and scale > 1.0:
        image = image.resize((int(w * scale), int(h * scale)), Image.LANCZOS)
        w, h = image.size

    if deskew:
        if w > 400:
            small = image.resize((400, int(h * (400.0 / w))), Image.BILINEAR)
        else:
            small = image.copy()
        if small.size[0] >= 2:
            angle = _estimate_skew_angle(small)
            if abs(angle) > 0.3:
                image = image.rotate(angle, resample=Image.BILINEAR, expand=True, fillcolor=255)

    image = ImageOps.autocontrast(image, cutoff=0)
    image = image.filter(ImageFilter.MedianFilter(size=3))
    image = ImageEnhance.Sharpness(image).enhance(1.6)
    image = ImageEnhance.Contrast(image).enhance(1.6)

    if binarize:
        arr = np.asarray(image, dtype=np.uint8)
        thr = _otsu_threshold(arr)
        binary = (arr > thr).astype(np.uint8) * 255
        image = Image.fromarray(binary, mode="L")

    return image


def _confidence_from_data(data: dict) -> float:
    confs = []
    for c in data.get("conf", []):
        try:
            ci = int(float(c))
        except (TypeError, ValueError):
            continue
        if ci >= 0:
            confs.append(ci)
    if not confs:
        return 0.0
    return float(np.mean(confs))


def ocr_image_bytes(
    data: bytes,
    lang: str = "eng",
    psm: int = 6,
    oem: int = 3,
    preprocess: bool = True,
    scale: float = 2.0,
    deskew: bool = True,
    binarize: bool = False,
) -> str:
    """Run Tesseract OCR on raw image bytes."""
    image = Image.open(io.BytesIO(data))
    if preprocess:
        image = preprocess_image(image, scale=scale, deskew=deskew, binarize=binarize)
    else:
        image = ImageOps.exif_transpose(image)
        if image.mode not in ("RGB", "L"):
            image = image.convert("RGB").convert("L")
        else:
            image = image.convert("L")

    config = f"--oem {oem} --psm {psm} -c preserve_interword_spaces=1"
    return pytesseract.image_to_string(image, lang=lang, config=config).strip()


def ocr_image_with_confidence(
    data: bytes,
    lang: str = "eng",
    psm: int = 6,
    oem: int = 3,
    preprocess: bool = True,
    scale: float = 2.0,
    deskew: bool = True,
    binarize: bool = False,
) -> Tuple[str, float]:
    """Like ocr_image_bytes but also returns mean confidence (0-100)."""
    image = Image.open(io.BytesIO(data))
    if preprocess:
        image = preprocess_image(image, scale=scale, deskew=deskew, binarize=binarize)
    else:
        image = ImageOps.exif_transpose(image)
        if image.mode not in ("RGB", "L"):
            image = image.convert("RGB").convert("L")
        else:
            image = image.convert("L")

    config = f"--oem {oem} --psm {psm} -c preserve_interword_spaces=1"
    text = pytesseract.image_to_string(image, lang=lang, config=config).strip()
    try:
        d = pytesseract.image_to_data(image, lang=lang, config=config, output_type=pytesseract.Output.DICT)
        conf = _confidence_from_data(d)
    except Exception:
        conf = 0.0
    return text, conf


def ocr_pdf_bytes(
    data: bytes,
    lang: str = "eng",
    dpi: int = 200,
    force_ocr: bool = False,
    preprocess: bool = True,
    scale: float = 2.0,
    deskew: bool = True,
    binarize: bool = False,
) -> OcrResult:
    """Extract text from a PDF, falling back to OCR for scanned pages."""
    doc = fitz.open(stream=data, filetype="pdf")
    pages: List[PageResult] = []

    for i, page in enumerate(doc):
        text = page.get_text("text").strip()

        if force_ocr or len(text) < MIN_TEXT_CHARS:
            pix = page.get_pixmap(dpi=dpi)
            img_bytes = pix.tobytes("png")
            ocr_text, conf = ocr_image_with_confidence(
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
