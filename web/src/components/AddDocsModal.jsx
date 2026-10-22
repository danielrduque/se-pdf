import { useRef, useState } from 'react'

export default function AddDocsModal({ status, kb, opts, setOpts, jobRunning, onUpload, onSync, onOpenFolder, onClose }) {
  const input = useRef(null)
  const [drag, setDrag] = useState(false)
  const [folderMsg, setFolderMsg] = useState('')
  const pending = kb ? kb.new.length + kb.changed.length : 0
  const removed = kb ? kb.removed.length : 0

  function pick(files) {
    const list = [...files]
    if (list.length) onUpload(list)
  }

  async function openFolder() {
    setFolderMsg('')
    try {
      await onOpenFolder()
    } catch (e) {
      setFolderMsg(e.message)
    }
  }

  return (
    <div className="overlay" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <div className="modal wide" role="dialog" aria-modal="true" aria-label="Agregar documentos">
        <div className="modal-head">
          <h2>Agregar documentos</h2>
          <button className="icon-btn" onClick={onClose} aria-label="Cerrar">×</button>
        </div>
        <p className="muted">Elige cómo quieres agregarlos. Cuando termines, podrás hacer preguntas sobre ellos.</p>

        <div className="choices">
          <section className="choice">
            <h3><span>1</span> Desde tu computador</h3>
            <p className="muted small">Elige uno o varios archivos. Sirve para algo puntual.</p>
            <div
              className={`drop ${drag ? 'over' : ''}`}
              onClick={() => input.current?.click()}
              onDragOver={(e) => { e.preventDefault(); setDrag(true) }}
              onDragLeave={() => setDrag(false)}
              onDrop={(e) => { e.preventDefault(); setDrag(false); pick(e.dataTransfer.files) }}
              role="button"
              tabIndex={0}
              onKeyDown={(e) => e.key === 'Enter' && input.current?.click()}
            >
              <span className="drop-icon" aria-hidden>↑</span>
              <span>Arrastra archivos aquí o <u>búscalos</u></span>
              <small>PDF, imágenes, audios, videos y textos</small>
              <input ref={input} type="file" multiple hidden accept={status.extensions.join(',')} onChange={(e) => { pick(e.target.files); e.target.value = '' }} />
            </div>
          </section>

          <section className="choice">
            <h3><span>2</span> Desde la carpeta de documentos</h3>
            <p className="muted small">
              Copia tus archivos dentro de esta carpeta del proyecto y la app los lee. Sirve para dejar una colección fija:
            </p>
            <code className="path">{kb?.folder || status.kb_dir}</code>
            {kb && (
              <p className="kb-counts">
                <span className="chip ok">{kb.ok.length} ya leídos</span>
                <span className={`chip ${pending ? 'warn' : 'soft'}`}>{pending} nuevos</span>
                {removed > 0 && <span className="chip warn">{removed} borrados</span>}
              </p>
            )}
            {kb?.duplicates?.length > 0 && <p className="warn small">Hay nombres repetidos en subcarpetas; solo se lee el primero: {kb.duplicates.join(', ')}</p>}
            <div className="btn-row">
              <button className="btn" onClick={openFolder}>Abrir carpeta</button>
              <button className="btn primary" onClick={onSync} disabled={jobRunning || !(pending || removed)}>
                {pending || removed ? 'Leer la carpeta ahora' : 'Todo está al día'}
              </button>
            </div>
            {folderMsg && <p className="warn small">{folderMsg}</p>}
          </section>
        </div>

        <details className="more">
          <summary>Opciones de lectura</summary>
          <label className="check">
            <input type="checkbox" checked={opts.vision} onChange={(e) => setOpts({ ...opts, vision: e.target.checked })} />
            Entender también las imágenes y los gráficos <small>(más lento, pero necesario para PDFs escaneados y fotos)</small>
          </label>
          <label className="field">Idioma de los audios y videos
            <select value={opts.lang} onChange={(e) => setOpts({ ...opts, lang: e.target.value })}>
              <option value="">Detectarlo solo</option>
              <option value="es">Español</option>
              <option value="en">Inglés</option>
            </select>
          </label>
        </details>
      </div>
    </div>
  )
}
