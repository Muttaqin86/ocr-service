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
pip install -r backend/requirements.txt
```

Pastikan `tesseract` tersedia di PATH:

```bash
tesseract --version
```

## Menjalankan

### Backend (FastAPI)
Dari root repo:
```bash
uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
```
Atau dari folder backend:
```bash
cd backend
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
uvicorn backend.main:app --host 0.0.0.0 --port 8000
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

## Penyempurnaan OCR (baru)

Endpoint `/ocr/image`, `/ocr/pdf`, `/ocr` sekarang menerima parameter tambahan untuk meningkatkan akurasi:

- `preprocess` (bool, default true) — pipeline: perbaiki orientasi EXIF, grayscale, upscale gambar kecil, luruskan (deskew), auto-contrast, penajaman, kontras, (opsional) binarisasi.
- `deskew` (bool, default true) — luruskan halaman miring.
- `binarize` (bool, default false) — konversi ke hitam/putih (Otsu). Matikan untuk pencahayaan tidak merata (biarkan Tesseract menangani).
- `scale` (float, default 2.0) — faktor upscale untuk gambar kecil (Tesseract optimal ~300 DPI).
- `oem` (int, default 3) — engine mode Tesseract (0 legacy, 1 LSTM, 2 gabungan, 3 default).
- `psm` (int, default 6) — page segmentation mode.

Respons sekarang menyertakan `confidence` (0–100) per hasil/gambar dan per halaman PDF.

Daftar bahasa terpasang: `GET /languages`. Validasi bahasa dilakukan otomatis; jika paket bahasa belum terpasang (mis. `ind`), API mengembalikan 400 dengan petunjuk instalasi.

## Catatan

- Bahasa default `eng`. Tesseract bawaan hanya `eng` dan `osd`. Untuk bahasa lain, install `tesseract-lang` (`brew install tesseract-lang`) dan gunakan kode bahasa yang sesuai (mis. `ind` untuk Indonesia).
- PSM (Page Segmentation Mode) default 6; sesuaikan untuk layout berbeda.
