"""FastAPI application exposing OCR endpoints for images and PDFs."""

from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

try:
    from .ocr import ocr_image_bytes, ocr_pdf_bytes, ocr_image_with_confidence, validate_lang, available_languages
except ImportError:
    from ocr import ocr_image_bytes, ocr_pdf_bytes, ocr_image_with_confidence, validate_lang, available_languages

app = FastAPI(
    title="OCR Service",
    description="Extract text from images and PDFs using Tesseract + PyMuPDF.",
    version="1.0.0",
)

# Serve built React frontend assets (resolved relative to this file's location)
BASE_DIR = Path(__file__).resolve().parent
FRONTEND_DIST = BASE_DIR.parent / "frontend" / "dist"
if FRONTEND_DIST.is_dir():
    app.mount("/assets", StaticFiles(directory=str(FRONTEND_DIST / "assets")), name="assets")


IMAGE_EXTS = (".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp", ".webp", ".gif")
IMAGE_MIMES = {"image/png", "image/jpeg", "image/jpg", "image/tiff", "image/bmp", "image/webp", "image/gif"}
PDF_MIMES = {"application/pdf", "application/x-pdf"}


@app.get("/", response_class=HTMLResponse)
async def index():
    index_file = FRONTEND_DIST / "index.html"
    try:
        with open(index_file, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return "<h1>OCR Service</h1><p>Frontend belum di-build. Jalankan: cd frontend && npm run build</p><p>API: POST /ocr/image atau /ocr/pdf</p>"


@app.get("/languages")
async def languages():
    return {"languages": available_languages()}
@app.get("/health")
async def health():
    return {"status": "ok"}



@app.post("/ocr/image")
async def ocr_image(
    file: UploadFile = File(...),
    lang: str = Form("eng"),
    psm: int = Form(6),
    oem: int = Form(3),
    preprocess: bool = Form(True),
    scale: float = Form(2.0),
    deskew: bool = Form(True),
    binarize: bool = Form(False),
):
    name = (file.filename or "").lower()
    if file.content_type not in IMAGE_MIMES and not name.endswith(IMAGE_EXTS):
        raise HTTPException(status_code=400, detail="Unsupported image type")

    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="Empty file")

    try:
        validate_lang(lang)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    try:
        text, conf = ocr_image_with_confidence(
            data, lang=lang, psm=psm, oem=oem,
            preprocess=preprocess, scale=scale, deskew=deskew, binarize=binarize,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"OCR failed: {exc}")

    return JSONResponse(
        {
            "filename": file.filename,
            "language": lang,
            "text": text,
            "char_count": len(text),
            "confidence": round(conf, 2),
        }
    )
@app.post("/ocr/pdf")
async def ocr_pdf(
    file: UploadFile = File(...),
    lang: str = Form("eng"),
    dpi: int = Form(200),
    force_ocr: bool = Form(False),
    preprocess: bool = Form(True),
    scale: float = Form(2.0),
    deskew: bool = Form(True),
    binarize: bool = Form(False),
):
    name = (file.filename or "").lower()
    if file.content_type not in PDF_MIMES and not name.endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Unsupported file type (expected PDF)")

    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="Empty file")

    try:
        validate_lang(lang)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    try:
        result = ocr_pdf_bytes(
            data, lang=lang, dpi=dpi, force_ocr=force_ocr,
            preprocess=preprocess, scale=scale, deskew=deskew, binarize=binarize,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"PDF processing failed: {exc}")

    fname = file.filename or "document.pdf"
    return JSONResponse(
        {
            "filename": fname,
            "language": result.language,
            "total_chars": result.total_chars,
            "pages": [
                {
                    "page": p.page,
                    "method": p.method,
                    "char_count": p.char_count,
                    "confidence": round(p.confidence, 2),
                    "text": p.text,
                }
                for p in result.pages
            ],
        }
    )


@app.post("/ocr")
async def ocr_auto(
    file: UploadFile = File(...),
    lang: str = Form("eng"),
    dpi: int = Form(200),
    force_ocr: bool = Form(False),
    psm: int = Form(6),
    oem: int = Form(3),
    preprocess: bool = Form(True),
    scale: float = Form(2.0),
    deskew: bool = Form(True),
    binarize: bool = Form(False),
):
    name = (file.filename or "").lower()
    ctype = file.content_type or ""
    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="Empty file")

    try:
        validate_lang(lang)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    if ctype in PDF_MIMES or name.endswith(".pdf"):
        try:
            result = ocr_pdf_bytes(
                data, lang=lang, dpi=dpi, force_ocr=force_ocr,
                preprocess=preprocess, scale=scale, deskew=deskew, binarize=binarize,
            )
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"PDF processing failed: {exc}")
        fname = file.filename or "document.pdf"
        return JSONResponse(
            {
                "filename": fname,
                "language": result.language,
                "total_chars": result.total_chars,
                "pages": [
                    {
                        "page": p.page, "method": p.method, "char_count": p.char_count,
                        "confidence": round(p.confidence, 2), "text": p.text,
                    }
                    for p in result.pages
                ],
            }
        )

    # image
    try:
        text, conf = ocr_image_with_confidence(
            data, lang=lang, psm=psm, oem=oem,
            preprocess=preprocess, scale=scale, deskew=deskew, binarize=binarize,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"OCR failed: {exc}")
    return JSONResponse(
        {"filename": file.filename, "language": lang, "text": text, "char_count": len(text), "confidence": round(conf, 2)}
    )






