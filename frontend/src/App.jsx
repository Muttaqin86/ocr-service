import React, { useState, useRef, useCallback } from 'react'

const isPdf = (f) => f && (f.type === 'application/pdf' || f.name.toLowerCase().endsWith('.pdf'))

export default function App() {
  const [file, setFile] = useState(null)
  const [drag, setDrag] = useState(false)
  const [lang, setLang] = useState('eng')
  const [dpi, setDpi] = useState(200)
  const [force, setForce] = useState('false')
  const [psm, setPsm] = useState(6)
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState(null)
  const [toast, setToast] = useState(null)
  const inputRef = useRef(null)

  const showToast = (msg, ok = false) => {
    setToast({ msg, ok })
    setTimeout(() => setToast(null), 4000)
  }

  const pickFile = useCallback((f) => {
    if (!f) return
    setFile(f)
    setResult(null)
  }, [])

  const onDrop = (e) => {
    e.preventDefault()
    setDrag(false)
    const f = e.dataTransfer.files?.[0]
    pickFile(f)
  }

  const submit = async (e) => {
    e?.preventDefault()
    if (!file) { showToast('Pilih file dulu'); return }
    setLoading(true)
    setResult(null)
    const fd = new FormData()
    fd.append('file', file)
    fd.append('lang', lang)
    const pdf = isPdf(file)
    if (pdf) {
      fd.append('dpi', String(dpi))
      fd.append('force_ocr', force)
    } else {
      fd.append('psm', String(psm))
    }
    const endpoint = pdf ? '/ocr/pdf' : '/ocr/image'
    try {
      const res = await fetch(endpoint, { method: 'POST', body: fd })
      const data = await res.json()
      if (!res.ok) throw new Error(data.detail || 'Gagal memproses')
      setResult({ pdf, data })
      showToast('Selesai', true)
    } catch (err) {
      showToast(err.message)
    } finally {
      setLoading(false)
    }
  }

  const copyText = async () => {
    let text = ''
    if (result.pdf) text = result.data.pages.map(p => `--- Halaman ${p.page} ---\n${p.text}`).join('\n\n')
    else text = result.data.text
    try {
      await navigator.clipboard.writeText(text)
      showToast('Teks disalin', true)
    } catch {
      showToast('Gagal menyalin')
    }
  }

  const downloadText = () => {
    let text = ''
    if (result.pdf) text = result.data.pages.map(p => `--- Halaman ${p.page} ---\n${p.text}`).join('\n\n')
    else text = result.data.text
    const blob = new Blob([text], { type: 'text/plain' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = (file?.name || 'hasil') + '.txt'
    a.click()
    URL.revokeObjectURL(url)
  }

  const downloadJson = () => {
    const blob = new Blob([JSON.stringify(result.data, null, 2)], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = (file?.name || 'hasil') + '.json'
    a.click()
    URL.revokeObjectURL(url)
  }

  const reset = () => { setFile(null); setResult(null); if (inputRef.current) inputRef.current.value = '' }


// placeholder
  return (
    <div className="container">
      <h1>OCR Service</h1>
      <p className="subtitle">Ekstrak teks dari gambar atau PDF (termasuk PDF scan) dengan Tesseract + PyMuPDF.</p>

      <div className="card">
        <div
          className={`dropzone ${drag ? 'drag' : ''} ${file ? 'has-file' : ''}`}
          onDragOver={(e) => { e.preventDefault(); setDrag(true) }}
          onDragLeave={() => setDrag(false)}
          onDrop={onDrop}
          onClick={() => inputRef.current?.click()}
        >
          {file ? (
            <>
              <strong>{file.name}</strong>
              <div className="fileinfo">{(file.size / 1024).toFixed(1)} KB · {file.type || 'unknown'}</div>
            </>
          ) : (
            <>
              <div>Seret & lepas file di sini</div>
              <div className="fileinfo">atau klik untuk memilih (gambar/PDF)</div>
            </>
          )}
        </div>
        <input
          ref={inputRef}
          type="file"
          accept="image/*,.pdf"
          style={{ display: 'none' }}
          onChange={(e) => pickFile(e.target.files?.[0])}
        />

        <div className="row" style={{ marginTop: 14 }}>
          <div>
            <label>Bahasa (lang)</label>
            <input value={lang} onChange={(e) => setLang(e.target.value)} placeholder="eng" />
          </div>
          {isPdf(file) ? (
            <>
              <div>
                <label>DPI (PDF)</label>
                <input type="number" value={dpi} min={100} max={400} onChange={(e) => setDpi(Number(e.target.value))} />
              </div>
              <div>
                <label>Force OCR</label>
                <select value={force} onChange={(e) => setForce(e.target.value)}>
                  <option value="false">false</option>
                  <option value="true">true</option>
                </select>
              </div>
            </>
          ) : (
            <div>
              <label>PSM (image)</label>
              <input type="number" value={psm} min={0} max={13} onChange={(e) => setPsm(Number(e.target.value))} />
            </div>
          )}
        </div>

        <div className="actions" style={{ marginTop: 14 }}>
          <button onClick={submit} disabled={loading || !file}>
            {loading && <span className="spinner" />}
            {loading ? 'Memproses...' : 'Proses'}
          </button>
          <button className="secondary" onClick={reset} disabled={loading}>Reset</button>
        </div>
      </div>

      {file && !isPdf(file) && (
        <div className="card preview">
          <img src={URL.createObjectURL(file)} alt="preview" />
        </div>
      )}

      {result && (
        <div className="card">
          <h3>Hasil</h3>
          <div>
            <strong>{result.data.filename}</strong>
            {result.pdf ? (
              <span className="badge">{result.data.pages.length} halaman · {result.data.total_chars} char</span>
            ) : (
              <span className="badge">{result.data.char_count} char</span>
            )}
          </div>

          {result.pdf ? (
            result.data.pages.map((p) => (
              <div className="page" key={p.page}>
                <h4>
                  Halaman {p.page}
                  <span className="badge">{p.method} · {p.char_count} char</span>
                </h4>
                <pre>{p.text || '(kosong)'}</pre>
              </div>
            ))
          ) : (
            <pre style={{ marginTop: 12 }}>{result.data.text || '(kosong)'}</pre>
          )}

          <div className="actions">
            <button className="secondary" onClick={copyText}>Copy teks</button>
            <button className="secondary" onClick={downloadText}>Download .txt</button>
            <button className="secondary" onClick={downloadJson}>Download .json</button>
          </div>
        </div>
      )}

      {toast && <div className={`toast ${toast.ok ? 'ok' : ''}`}>{toast.msg}</div>}
    </div>
  )
}

