import { useEffect, useRef, useState } from 'react'
import { typeLabel, typeTag } from '../docs.js'

/** Barra superior: «Escoge tu archivo» (todos los documentos cargados) y las acciones del documento elegido. */
export default function DocBar({ docs, selected, viewing, busy, summarizing, onSelect, onAdd, onOpenViewer, onSummarize, onRemove, onNewChat, hasChat, onOpenSidebar, attention }) {
  const [open, setOpen] = useState(false)
  const [filter, setFilter] = useState('')
  const box = useRef(null)
  const current = docs.find((d) => d.name === selected)

  useEffect(() => {
    if (!open) { setFilter(''); return undefined } // al cerrarlo (con Esc, con un clic fuera o al elegir) se borra la búsqueda
    const away = (e) => { if (!box.current?.contains(e.target)) setOpen(false) }
    const esc = (e) => { if (e.key === 'Escape') setOpen(false) }
    document.addEventListener('mousedown', away)
    document.addEventListener('keydown', esc)
    return () => { document.removeEventListener('mousedown', away); document.removeEventListener('keydown', esc) }
  }, [open])

  const plain = (s) => s.normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase() // «ultima» encuentra «ÚLTIMA»
  const shown = docs.filter((d) => plain(d.name).includes(plain(filter.trim())))
  const choose = (name) => { setOpen(false); onSelect(name) }

  return (
    <header className="docbar">
      <button className="icon-btn menu-btn" onClick={onOpenSidebar} aria-label="Abrir panel de chats">☰{attention && <i className="dot corner" data-s={attention} aria-hidden />}</button>

      <div className="picker" ref={box}>
        <button className={`picker-btn ${current ? 'has' : ''}`} onClick={() => setOpen((o) => !o)} aria-haspopup="listbox" aria-expanded={open} disabled={docs.length === 0}>
          {current ? (
            <>
              <span className="tag" data-t={typeTag(current.ext)}>{typeTag(current.ext)}</span>
              <span className="picker-name">{current.name}</span>
            </>
          ) : (
            <span className="picker-name">{docs.length === 0 ? 'Aún no hay archivos' : 'Escoge tu archivo'}</span>
          )}
          <span className="caret" aria-hidden>▾</span>
        </button>

        {open && (
          <div className="picker-pop" role="listbox" aria-label="Archivos cargados">
            {docs.length > 7 && <input className="picker-filter" autoFocus placeholder="Buscar archivo…" value={filter} onChange={(e) => setFilter(e.target.value)} />}
            <ul>
              {shown.map((d) => (
                <li key={d.name}>
                  <button role="option" aria-selected={d.name === selected} className={d.name === selected ? 'on' : ''} onClick={() => choose(d.name)}>
                    <span className="tag" data-t={typeTag(d.ext)}>{typeTag(d.ext)}</span>
                    <span className="picker-name">{d.name}</span>
                    <small>{d.chunks} frag.</small>
                  </button>
                </li>
              ))}
              {shown.length === 0 && <li className="muted small picker-none">Ningún archivo coincide.</li>}
            </ul>
            <button className="picker-add" onClick={() => { setOpen(false); onAdd() }}>+ Agregar documentos</button>
          </div>
        )}
      </div>

      {current && (
        <details className="menu docmenu">
          <summary aria-label={`Opciones de ${current.name}`}>…</summary>
          <div className="menu-pop">
            {!viewing && <button onClick={(e) => { e.currentTarget.closest('details').open = false; onOpenViewer() }}>{['mp3', 'wav', 'm4a', 'flac', 'ogg', 'aac', 'mp4', 'mkv', 'mov', 'avi', 'webm'].includes(current.ext) ? 'Reproducir' : 'Ver documento'}</button>}
            <button disabled={!!summarizing || busy} onClick={(e) => { e.currentTarget.closest('details').open = false; onSummarize(current.name) }}>{summarizing === current.name ? 'Resumiendo…' : 'Resumir este documento'}</button>
            <button className="danger" onClick={(e) => { e.currentTarget.closest('details').open = false; onRemove(current.name) }}>Quitar de la lista</button>
          </div>
        </details>
      )}
      {current && <span className="docbar-type muted small">{typeLabel(current.ext)}</span>}

      {hasChat && <button className="btn small new-chat" onClick={onNewChat}>+ Nuevo chat</button>}
    </header>
  )
}
