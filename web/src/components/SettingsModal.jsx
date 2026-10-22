import { useState } from 'react'

const PRESETS = {
  chat: { ollama: 'gemma3:4b', llamacpp: 'local', openai: 'gemini-3-flash-preview, gemini-3.5-flash-lite' },
  embed: { ollama: 'embeddinggemma-2:740m', llamacpp: 'embeddinggemma-2', openai: 'text-embedding-3-small' },
}

// el llama-server de embeddings va en su propio puerto (el del chat es el 8080)
const URLS = { chat: {}, embed: { llamacpp: 'http://127.0.0.1:8081/v1' } }

function ModelFields({ role, label, help, value, onChange, backends }) {
  const set = (patch) => onChange({ ...value, ...patch })
  return (
    <fieldset>
      <legend>{label}</legend>
      <p className="muted small">{help}</p>
      <label>
        ¿Dónde corre?
        <select value={value.backend} onChange={(e) => set({ backend: e.target.value, model: PRESETS[role][e.target.value], base_url: URLS[role][e.target.value] ?? '' })}>
          {Object.entries(backends).map(([k, v]) => (
            <option key={k} value={k}>{v.label}</option>
          ))}
        </select>
      </label>
      <label>
        Nombre del modelo{role === 'chat' && <span className="muted"> · puedes poner varios separados por coma: si uno falla se usa el siguiente</span>}
        <input value={value.model} onChange={(e) => set({ model: e.target.value })} spellCheck={false} />
      </label>
      <label>
        Dirección <span className="muted">(déjala vacía para usar la habitual)</span>
        <input value={value.base_url} placeholder={backends[value.backend].default_url} onChange={(e) => set({ base_url: e.target.value })} spellCheck={false} />
      </label>
    </fieldset>
  )
}

export default function SettingsModal({ status, opts, setOpts, onSave, onClose }) {
  const [chat, setChat] = useState(status.chat)
  const [embed, setEmbed] = useState(status.embed)
  const [key, setKey] = useState('')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const cloud = chat.backend === 'openai' || embed.backend === 'openai'

  async function save() {
    setSaving(true)
    setError('')
    try {
      await onSave({ chat, embed, api_key: key || undefined })
      onClose()
    } catch (e) {
      setError(e.message)
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="overlay" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <div className="modal" role="dialog" aria-modal="true" aria-label="Ajustes">
        <div className="modal-head">
          <h2>Ajustes</h2>
          <button className="icon-btn" onClick={onClose} aria-label="Cerrar">×</button>
        </div>

        <ModelFields role="chat" label="Modelo de respuestas e imágenes" help="Escribe las respuestas y entiende imágenes, gráficos y PDFs escaneados (Chat y visión)." value={chat} onChange={setChat} backends={status.backends} />
        <ModelFields role="embed" label="Modelo de búsqueda" help="Encuentra qué partes de tus documentos se parecen a tu pregunta. Con EmbeddingGemma 2 en llama.cpp (puerto 8081) la pregunta se compara directamente con las imágenes y el audio, sin pasar por texto." value={embed} onChange={setEmbed} backends={status.backends} />

        {cloud && (
          <fieldset>
            <legend>Clave de la API en la nube</legend>
            <label>
              API key <span className="muted">{status.has_key ? '(ya hay una cargada; escribe otra solo si quieres cambiarla)' : ''}</span>
              <input type="password" value={key} onChange={(e) => setKey(e.target.value)} placeholder={status.has_key ? '••••••••' : 'Pega tu clave'} autoComplete="off" />
            </label>
            <p className="warn small">Con la nube, tus preguntas y el contenido de los documentos se envían a ese proveedor. La clave no se guarda en disco: para dejarla fija, ponla en el archivo <code>.env</code>.</p>
          </fieldset>
        )}
        <p className="muted small">Si cambias el modelo de búsqueda, hay que recalcular los vectores de lo ya leído: ejecuta <code>python tools/reembed.py</code>.</p>
        {error && <p className="error-text">{error}</p>}
        <div className="modal-actions">
          <button className="btn ghost" onClick={onClose}>Cancelar</button>
          <button className="btn primary" onClick={save} disabled={saving}>{saving ? 'Guardando…' : 'Guardar modelos'}</button>
        </div>

        <hr />
        <label className="check">
          <input type="checkbox" checked={opts.rerank} onChange={(e) => setOpts({ ...opts, rerank: e.target.checked })} />
          Búsqueda más precisa <small>(para documentos muy grandes; tarda unos segundos más por pregunta)</small>
        </label>
      </div>
    </div>
  )
}
