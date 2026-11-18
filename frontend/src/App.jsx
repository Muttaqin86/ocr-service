import React, { useState, useRef, useCallback, useEffect } from 'react'

const isPdf = (f) => f && (f.type === 'application/pdf' || f.name.toLowerCase().endsWith('.pdf'))

export default function App() {
  const [file, setFile] = useState(null)
  const [drag, setDrag] = useState(false)
  const [lang, setLang] = useState('eng')
  const [dpi, setDpi] = useState(200)
  const [force, setForce] = useState('false')
  const [psm, setPsm] = useState(6)
  const [oem, setOem] = useState(3)
  const [preprocess, setPreprocess] = useState(true)
  const [deskew, setDeskew] = useState(true)
  const [binarize, setBinarize] = useState(false)
  const [scale, setScale] = useState(2)
  const [langs, setLangs] = useState([])
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState(null)
  const [resultType, setResultType] = useState(null) // 'ocr' | 'ai'
  const [toast, setToast] = useState(null)
  const inputRef = useRef(null)

  // ========== AI OCR STATE ==========
  const [activeTab, setActiveTab] = useState('ocr') // 'ocr' | 'ai'
  const [aiFile, setAiFile] = useState(null)
  const [aiDrag, setAiDrag] = useState(false)
  const [aiLang, setAiLang] = useState('en')
  const [aiLangs, setAiLangs] = useState([])
  const [aiLoading, setAiLoading] = useState(false)
  const [aiResult, setAiResult] = useState(null)
  const aiInputRef = useRef(null)

  useEffect(() => {
    fetch('/languages').then(r => r.json()).then(d => setLangs(d.languages || [])).catch(() => {})
    fetch('/ai/languages').then(r => r.json()).then(d => setAiLangs(d.languages || [])).catch(() => {})
  }, [])

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
      fd.append('preprocess', String(preprocess))
      fd.append('deskew', String(deskew))
      fd.append('binarize', String(binarize))
      fd.append('scale', String(scale))
    } else {
      fd.append('psm', String(psm))
      fd.append('oem', String(oem))
      fd.append('preprocess', String(preprocess))
      fd.append('deskew', String(deskew))
      fd.append('binarize', String(binarize))
      fd.append('scale', String(scale))
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

  const reset = () => { setFile(null); setResult(null); setResultType(null); if (inputRef.current) inputRef.current.value = '' }

  // ========== AI OCR FUNCTIONS ==========
  const pickAiFile = useCallback((f) => {
    if (!f) return
    setAiFile(f)
    setAiResult(null)
  }, [])

  const onAiDrop = (e) => {
    e.preventDefault()
    setAiDrag(false)
    const f = e.dataTransfer.files?.[0]
    pickAiFile(f)
  }

  const submitAi = async (e) => {
    e?.preventDefault()
    if (!aiFile) { showToast('Pilih file dulu'); return }
    setAiLoading(true)
    setAiResult(null)
    const fd = new FormData()
    fd.append('file', aiFile)
    fd.append('lang', aiLang)
    const pdf = isPdf(aiFile)
    const endpoint = pdf ? '/ocr/ai/pdf' : '/ocr/ai/image'
    try {
      const res = await fetch(endpoint, { method: 'POST', body: fd })
      const data = await res.json()
      if (!res.ok) throw new Error(data.detail || 'Gagal memproses')
      setAiResult({ pdf, data })
      showToast('AI Selesai', true)
    } catch (err) {
      showToast(err.message)
    } finally {
      setAiLoading(false)
    }
  }

  const copyAiText = async () => {
    let text = ''
    if (aiResult.pdf) text = aiResult.data.pages.map(p => `--- Halaman ${p.page} ---\n${p.text}`).join('\n\n')
    else text = aiResult.data.text
    try {
      await navigator.clipboard.writeText(text)
      showToast('Teks AI disalin', true)
    } catch {
      showToast('Gagal menyalin')
    }
  }

  const downloadAiText = () => {
    let text = ''
    if (aiResult.pdf) text = aiResult.data.pages.map(p => `--- Halaman ${p.page} ---\n${p.text}`).join('\n\n')
    else text = aiResult.data.text
    const blob = new Blob([text], { type: 'text/plain' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = (aiFile?.name || 'hasil-ai') + '.txt'
    a.click()
    URL.revokeObjectURL(url)
  }

  const downloadAiJson = () => {
    const blob = new Blob([JSON.stringify(aiResult.data, null, 2)], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = (aiFile?.name || 'hasil-ai') + '.json'
    a.click()
    URL.revokeObjectURL(url)
  }

  const resetAi = () => { setAiFile(null); setAiResult(null); if (aiInputRef.current) aiInputRef.current.value = '' }

  const currentResult = activeTab === 'ocr' ? result : aiResult
  const currentLoading = activeTab === 'ocr' ? loading : aiLoading

  return (
    <div className="container">
      <div className="tabs">
        <button
          className={activeTab === 'ocr' ? 'tab-active' : ''}
          onClick={() => setActiveTab('ocr')}
        >
          📄 OCR (Tesseract)
        </button>
        <button
          className={activeTab === 'ai' ? 'tab-active' : ''}
          onClick={() => setActiveTab('ai')}
        >
          🤖 OCR AI
        </button>
      </div>

      {activeTab === 'ocr' && (
        <>
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
            <input value={lang} onChange={(e) => setLang(e.target.value)} placeholder="eng" list="langlist" />
            <datalist id="langlist">{langs.map(l => <option key={l} value={l} />)}</datalist>
            {langs.length > 0 && <div className="fileinfo">Tersedia: {langs.join(', ')}</div>}
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
            <>
              <div>
                <label>PSM (image)</label>
                <input type="number" value={psm} min={0} max={13} onChange={(e) => setPsm(Number(e.target.value))} />
              </div>
              <div>
                <label>OEM (engine)</label>
                <select value={oem} onChange={(e) => setOem(Number(e.target.value))}>
                  <option value={0}>0 (legacy)</option>
                  <option value={1}>1 (LSTM)</option>
                  <option value={2}>2 (legacy+LSTM)</option>
                  <option value={3}>3 (default)</option>
                </select>
              </div>
            </>
          )}
        </div>

        <div className="row" style={{ marginTop: 10 }}>
          <div>
            <label>Preprocessing</label>
            <select value={preprocess ? 'true' : 'false'} onChange={(e) => setPreprocess(e.target.value === 'true')}>
              <option value="true">On (recommended)</option>
              <option value="false">Off</option>
            </select>
          </div>
          <div>
            <label>Deskew (luruskan)</label>
            <select value={deskew ? 'true' : 'false'} onChange={(e) => setDeskew(e.target.value === 'true')}>
              <option value="true">On</option>
              <option value="false">Off</option>
            </select>
          </div>
          <div>
            <label>Binarize (hitam/putih)</label>
            <select value={binarize ? 'true' : 'false'} onChange={(e) => setBinarize(e.target.value === 'true')}>
              <option value="true">On</option>
              <option value="false">Off</option>
            </select>
          </div>
          <div>
            <label>Scale (upscale)</label>
            <input type="number" value={scale} min={1} max={4} step={0.5} onChange={(e) => setScale(Number(e.target.value))} />
          </div>
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

          {activeTab === 'ocr' && result && (
        <div className="card">
          <h3>Hasil OCR</h3>
          <div>
            <strong>{result.data.filename}</strong>
            {result.pdf ? (
              <span className="badge">{result.data.pages.length} halaman · {result.data.total_chars} char</span>
            ) : (
              <span className="badge">{result.data.char_count} char{result.data.confidence != null ? ` · conf ${result.data.confidence}%` : ''}</span>
            )}
          </div>

          {result.pdf ? (
            result.data.pages.map((p) => (
              <div className="page" key={p.page}>
                <h4>
                  Halaman {p.page}
                  <span className="badge">{p.method} · {p.char_count} char{p.confidence != null ? ` · conf ${p.confidence}%` : ''}</span>
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
        </>
      )}

      {activeTab === 'ai' && (
        <>
          <h1>OCR AI</h1>
          <p className="subtitle">Ekstrak teks menggunakan AI (EasyOCR / Deep Learning). Cocok untuk tulisan tangan dan teks bervariasi.</p>

          <div className="card">
            <div
              className={`dropzone ${aiDrag ? 'drag' : ''} ${aiFile ? 'has-file' : ''}`}
              onDragOver={(e) => { e.preventDefault(); setAiDrag(true) }}
              onDragLeave={() => setAiDrag(false)}
              onDrop={onAiDrop}
              onClick={() => aiInputRef.current?.click()}
            >
              {aiFile ? (
                <>
                  <strong>{aiFile.name}</strong>
                  <div className="fileinfo">{(aiFile.size / 1024).toFixed(1)} KB · {aiFile.type || 'unknown'}</div>
                </>
              ) : (
                <>
                  <div>Seret & lepas file di sini</div>
                  <div className="fileinfo">atau klik untuk memilih (gambar/PDF)</div>
                </>
              )}
            </div>
            <input
              ref={aiInputRef}
              type="file"
              accept="image/*,.pdf"
              style={{ display: 'none' }}
              onChange={(e) => pickAiFile(e.target.files?.[0])}
            />

            <div className="row" style={{ marginTop: 14 }}>
              <div>
                <label>Bahasa (lang)</label>
                <input value={aiLang} onChange={(e) => setAiLang(e.target.value)} placeholder="en" list="ailanglist" />
                <datalist id="ailanglist">{aiLangs.map(l => <option key={l} value={l} />)}</datalist>
                {aiLangs.length > 0 && <div className="fileinfo">Tersedia: {aiLangs.join(', ')}</div>}
              </div>
            </div>

            <div className="actions" style={{ marginTop: 14 }}>
              <button onClick={submitAi} disabled={aiLoading || !aiFile}>
                {aiLoading && <span className="spinner" />}
                {aiLoading ? 'Memproses AI...' : 'Proses AI'}
              </button>
              <button className="secondary" onClick={resetAi} disabled={aiLoading}>Reset</button>
            </div>
          </div>

          {aiFile && !isPdf(aiFile) && (
            <div className="card preview">
              <img src={URL.createObjectURL(aiFile)} alt="preview" />
            </div>
          )}

          {aiResult && (
            <div className="card">
              <h3>Hasil OCR AI</h3>
              <div>
                <strong>{aiResult.data.filename}</strong>
                {aiResult.pdf ? (
                  <span className="badge">{aiResult.data.pages.length} halaman · {aiResult.data.total_chars} char</span>
                ) : (
                  <span className="badge">{aiResult.data.char_count} char{aiResult.data.confidence != null ? ` · conf ${aiResult.data.confidence}%` : ''}</span>
                )}
              </div>

              {aiResult.pdf ? (
                aiResult.data.pages.map((p) => (
                  <div className="page" key={p.page}>
                    <h4>
                      Halaman {p.page}
                      <span className="badge">{p.method || 'ai'} · {p.char_count} char{p.confidence != null ? ` · conf ${p.confidence}%` : ''}</span>
                    </h4>
                    <pre>{p.text || '(kosong)'}</pre>
                  </div>
                ))
              ) : (
                <pre style={{ marginTop: 12 }}>{aiResult.data.text || '(kosong)'}</pre>
              )}

              <div className="actions">
                <button className="secondary" onClick={copyAiText}>Copy teks</button>
                <button className="secondary" onClick={downloadAiText}>Download .txt</button>
                <button className="secondary" onClick={downloadAiJson}>Download .json</button>
              </div>
            </div>
          )}
        </>
      )}

      {toast && <div className={`toast ${toast.ok ? 'ok' : ''}`}>{toast.msg}</div>}
    </div>
  )
}

