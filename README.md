# OCR Service

Aplikasi OCR (Optical Character Recognition) untuk mengekstrak teks dari gambar dan PDF, termasuk PDF hasil scan, menggunakan **Tesseract** + **PyMuPDF** dengan backend **FastAPI**.

## Fitur

- Ekstrak teks dari gambar (PNG, JPG, TIFF, BMP, WEBP, GIF).
- Ekstrak teks dari PDF: teks native diekstrak langsung; halaman scan (sedikit/ tanpa teks) di-render dan di-OCR otomatis.
- Opsi `force_ocr` untuk memaksa OCR seluruh halaman.
- Antarmuka web sederhana di `/`.
- Endpoint REST: `/ocr/image`, `/ocr/pdf`, `/ocr` (auto-detect).

## Persyaratan

- Python 3.10+
- Tesseract OCR (`brew install tesseract` di macOS)
- Paket Python (lihat `requirements.txt`)

## Instalasi

```bash
cd /Users/muttaqin/Documents/Workspace/Xperiments/ocr
pip install -r requirements.txt
```

Pastikan `tesseract` tersedia di PATH:

```bash
tesseract --version
```

## Menjalankan

### Backend (FastAPI)
```bash
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

### Frontend (React + Vite)
Mode development (hot reload, proxy ke backend):
```bash
cd frontend
npm install
npm run dev   # http://localhost:5173
```

Build untuk produksi (output ke `frontend/dist`, disajikan oleh FastAPI):
```bash
cd frontend
npm run build
# lalu jalankan backend; root "/" akan memuat React build
uvicorn main:app --host 0.0.0.0 --port 8000
```

Buka http://localhost:8000 di browser.

## Penggunaan API

### Gambar

```bash
curl -X POST http://localhost:8000/ocr/image -F "file=@gambar.png" -F "lang=eng"
```

### PDF

```bash
curl -X POST http://localhost:8000/ocr/pdf -F "file=@dokumen.pdf" -F "lang=eng" -F "dpi=200"
```

### Auto-detect

```bash
curl -X POST http://localhost:8000/ocr -F "file=@file"
```

## Catatan

- Bahasa default `eng`. Tesseract bawaan hanya `eng` dan `osd`. Untuk bahasa lain, install `tesseract-lang` (`brew install tesseract-lang`) dan gunakan kode bahasa yang sesuai (mis. `ind` untuk Indonesia).
- PSM (Page Segmentation Mode) default 6; sesuaikan untuk layout berbeda.
