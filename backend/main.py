"""FastAPI application exposing OCR endpoints for images and PDFs."""

from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse

try:
    from .ocr import ocr_image_bytes, ocr_pdf_bytes, ocr_image_with_confidence, validate_lang, available_languages
    from .ai_ocr import ocr_image_bytes as ai_ocr_image_bytes, ocr_pdf_bytes as ai_ocr_pdf_bytes, validate_lang as ai_validate_lang, available_languages as ai_available_languages
except ImportError:
    from ocr import ocr_image_bytes, ocr_pdf_bytes, ocr_image_with_confidence, validate_lang, available_languages
    from ai_ocr import ocr_image_bytes as ai_ocr_image_bytes, ocr_pdf_bytes as ai_ocr_pdf_bytes, validate_lang as ai_validate_lang, available_languages as ai_available_languages

try:
    from .parser import parse_hospital_invoice
except ImportError:
    from parser import parse_hospital_invoice

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


@app.get("/ai/languages")
async def ai_languages():
    return {"languages": ai_available_languages()}


@app.post("/ocr/ai/image")
async def ocr_ai_image(
    file: UploadFile = File(...),
    lang: str = Form("en"),
    preprocess: bool = Form(True),
    scale: float = Form(2.0),
    deskew: bool = Form(True),
    binarize: bool = Form(False),
):
    name = (file.filename or "").lower()
    IMAGE_MIMES = {"image/png", "image/jpeg", "image/jpg", "image/tiff", "image/bmp", "image/webp", "image/gif"}
    IMAGE_EXTS = (".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp", ".webp", ".gif")
    if file.content_type not in IMAGE_MIMES and not name.endswith(IMAGE_EXTS):
        raise HTTPException(status_code=400, detail="Unsupported image type")

    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="Empty file")

    try:
        ai_validate_lang(lang)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    try:
        text, conf = ai_ocr_image_bytes(
            data, lang=lang,
            preprocess=preprocess, scale=scale, deskew=deskew, binarize=binarize,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"AI OCR failed: {exc}")

    return JSONResponse(
        {
            "filename": file.filename,
            "language": lang,
            "text": text,
            "char_count": len(text),
            "confidence": round(conf, 2),
        }
    )


@app.post("/ocr/ai/pdf")
async def ocr_ai_pdf(
    file: UploadFile = File(...),
    lang: str = Form("en"),
    dpi: int = Form(200),
    force_ocr: bool = Form(False),
    preprocess: bool = Form(True),
    scale: float = Form(2.0),
    deskew: bool = Form(True),
    binarize: bool = Form(False),
):
    name = (file.filename or "").lower()
    PDF_MIMES = {"application/pdf", "application/x-pdf"}
    if file.content_type not in PDF_MIMES and not name.endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Unsupported file type (expected PDF)")

    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="Empty file")

    try:
        ai_validate_lang(lang)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    try:
        result = ai_ocr_pdf_bytes(
            data, lang=lang, dpi=dpi, force_ocr=force_ocr,
            preprocess=preprocess, scale=scale, deskew=deskew, binarize=binarize,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"AI PDF processing failed: {exc}")

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


@app.post("/ocr/ai/parse")
async def ocr_ai_parse_invoice(
    file: UploadFile = File(...),
    lang: str = Form("id+en"),
    preprocess: bool = Form(True),
    scale: float = Form(1.5),
):
    """
    Melakukan AI OCR sekaligus memparsing hasilnya menjadi JSON terstruktur (Data Pasien & Tabel Biaya).
    """
    name = (file.filename or "").lower()
    IMAGE_MIMES = {"image/png", "image/jpeg", "image/jpg", "image/tiff", "image/bmp", "image/webp", "image/gif"}
    IMAGE_EXTS = (".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp", ".webp", ".gif")
    
    if file.content_type not in IMAGE_MIMES and not name.endswith(IMAGE_EXTS):
        raise HTTPException(status_code=400, detail="Unsupported image type")

    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="Empty file")

    try:
        # 1. Jalankan AI OCR yang sudah dioptimalkan
        text, conf = ai_ocr_image_bytes(data, lang=lang, preprocess=preprocess, scale=scale)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"AI OCR failed: {exc}")

    # 2. Parsing teks mentah menjadi struktur data JSON
    structured_data = parse_hospital_invoice(text)
    structured_data["raw_ocr_confidence"] = conf
    structured_data["filename"] = file.filename

    return JSONResponse(structured_data)


@app.post("/ocr/ai/table", response_class=HTMLResponse)
async def ocr_ai_table_view(
    file: UploadFile = File(...),
    lang: str = Form("id+en"),
    preprocess: bool = Form(True),
    scale: float = Form(1.5),
):
    """
    Melakukan AI OCR dan merender hasilnya langsung sebagai tabel HTML yang rapi.
    """
    name = (file.filename or "").lower()
    IMAGE_MIMES = {"image/png", "image/jpeg", "image/jpg", "image/tiff", "image/bmp", "image/webp", "image/gif"}
    IMAGE_EXTS = (".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp", ".webp", ".gif")
    
    if file.content_type not in IMAGE_MIMES and not name.endswith(IMAGE_EXTS):
        raise HTTPException(status_code=400, detail="Unsupported image type")

    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="Empty file")

    try:
        # 1. Jalankan AI OCR
        text, conf = ai_ocr_image_bytes(data, lang=lang, preprocess=preprocess, scale=scale)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"AI OCR failed: {exc}")

    # 2. Parsing teks mentah menjadi struktur data
    parsed_data = parse_hospital_invoice(text)

    # 3. Render ke dalam template HTML berformat Tabel
    html_content = f"""
    <!DOCTYPE html>
    <html lang="id">
    <head>
        <meta charset="UTF-8">
        <title>Hasil OCR Invoice - {file.filename}</title>
        <style>
            body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; margin: 40px; background: #f8f9fa; color: #333; }}
            .container {{ max-width: 900px; margin: auto; background: white; padding: 30px; border-radius: 12px; box-shadow: 0 4px 12px rgba(0,0,0,0.05); }}
            h2 {{ color: #1a73e8; border-bottom: 2px solid #eee; padding-bottom: 10px; }}
            .badge {{ display: inline-block; padding: 4px 10px; background: #e8f0fe; color: #1a73e8; border-radius: 6px; font-weight: 600; font-size: 14px; }}
            table {{ width: 100%; border-collapse: collapse; margin-top: 20px; }}
            th, td {{ padding: 12px 15px; border: 1px solid #dee2e6; text-align: left; font-size: 14px; }}
            th {{ background-color: #f1f3f5; color: #495057; font-weight: 600; }}
            tr:nth-child(even) {{ background-color: #f8f9fa; }}
            .summary-box {{ margin-top: 25px; background: #f1f3f5; padding: 20px; border-radius: 8px; }}
            .summary-row {{ display: flex; justify-content: space-between; margin-bottom: 8px; font-size: 15px; }}
            .summary-row.total {{ font-weight: bold; border-top: 1px solid #ced4da; padding-top: 8px; color: #2b8a3e; }}
        </style>
    </head>
    <body>
        <div class="container">
            <h2>📄 Hasil Ekstraksi Invoice Rumah Sakit</h2>
            <p><strong>File:</strong> {file.filename} &nbsp;|&nbsp; <strong>Confidence OCR:</strong> <span class="badge">{conf}%</span></p>
            
            <h3>📋 Informasi Pasien & Jaminan</h3>
            <table>
                <tr><th>Rumah Sakit</th><td>{parsed_data['hospital_name']}</td></tr>
                <tr><th>Nama Pasien</th><td><strong>{parsed_data['patient']['name'] or '-'}</strong></td></tr>
                <tr><th>No. Registrasi / MR</th><td>{parsed_data['patient']['reg_number'] or '-'}</td></tr>
                <tr><th>Penjamin (Asuransi)</th><td>{parsed_data['patient']['insurance'] or '-'}</td></tr>
                <tr><th>No. Peserta</th><td>{parsed_data['patient']['participant_number'] or '-'}</td></tr>
            </table>

            <h3>💳 Rincian Biaya</h3>
            <table>
                <thead>
                    <tr>
                        <th>No</th>
                        <th>Keterangan Item</th>
                        <th style="text-align: right;">Sub Total (IDR)</th>
                    </tr>
                </thead>
                <tbody>
    """
    
    # Masukkan baris item biaya ke dalam tabel HTML
    for idx, item in enumerate(parsed_data['items'], 1):
        formatted_price = f"{item['sub_total']:,.2f}"
        html_content += f"""
                    <tr>
                        <td>{idx}</td>
                        <td>{item['description']}</td>
                        <td style="text-align: right;">{formatted_price}</td>
                    </tr>
        """
        
    html_content += f"""
                </tbody>
            </table>

            <div class="summary-box">
                <div class="summary-row"><span>Sub Total Keseluruhan:</span> <strong>Rp {parsed_data['summary']['sub_total']:,.2f}</strong></div>
                <div class="summary-row"><span>Ditanggung Asuransi:</span> <strong>Rp {parsed_data['summary']['insurance_covered']:,.2f}</strong></div>
                <div class="summary-row total"><span>Selisih Ditanggung Pasien:</span> <strong>Rp {parsed_data['summary']['patient_pay']:,.2f}</strong></div>
            </div>
        </div>
    </body>
    </html>
    """

    return HTMLResponse(content=html_content)