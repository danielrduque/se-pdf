import { useEffect, useRef, useState } from 'react'
import { api, AUDIO, IMAGE, VIDEO, extOf, parseLoc } from '../api.js'

const KIND = { texto: 'Texto', visión: 'Imagen', audio: 'Audio' }
const enc = encodeURIComponent

/** Lo que la app entendió del documento: cada página, minuto o escena. Pulsar uno lleva el visor a ese punto. */
function ReadText({ chunks, active, onPick, title }) {  // active: ids de los fragmentos citados (se marcan)
  return (
    <section className="read">
      <h4>{title}</h4>
      <p className="muted small">Esto es lo que la app extrajo y usa para responder. Compáralo con el documento.</p>
      <ul>
        {chunks.map((c) => (
          <li key={c.id} className={active.has(c.id) ? 'active' : ''}>
            <button onClick={() => onPick(c)} title="Ir a este punto">
              <span className="chip">{c.loc}</span>
              <span className="chip soft">{KIND[c.kind] || c.kind}</span>
            </button>
            <p>{c.text}</p>
          </li>
        ))}
      </ul>
    </section>
  )
}

export default function Viewer({ target, zone, onZone, onClearZone, onClose }) {
  const { doc, loc, chunk, nonce } = target
  const ext = extOf(doc)
  const isPdf = ext === 'pdf'
  const isAudio = AUDIO.includes(ext)
  const isVideo = VIDEO.includes(ext)
  const isImage = IMAGE.includes(ext)
  const file = `/api/files/${enc(doc)}`

  const [info, setInfo] = useState(null)
  const [error, setError] = useState('')
  const [tab, setTab] = useState('doc') // PDF: 'doc' | 'text'
  const [page, setPage] = useState(1)
  const [play, setPlay] = useState(null) // estado de reproducción de audio/video: original | converting | ready | error
  const [picking, setPicking] = useState(false) // herramienta «marcar zona» activa
  const [drag, setDrag] = useState(null) // rectángulo que se está dibujando: {page, x0, y0, x1, y1} en fracciones de la página
  const retry = useRef(() => {})
  const triedForce = useRef(false)
  const media = useRef(null)
  const scroller = useRef(null)
  const goal = parseLoc(loc || '')
  const hlPage = goal?.kind === 'page' ? goal.value : null

  // Todo lo que la respuesta citó de este documento (no solo el fragmento pulsado): se pinta de amarillo
  const cited = target.sources ?? []
  const activeIds = new Set([...cited.map((s) => s.id), ...(chunk != null ? [chunk] : [])])
  const idsByPage = {}
  for (const s of cited) {
    const g = parseLoc(s.loc)
    if (g?.kind === 'page') (idsByPage[g.value] ||= []).push(s.id)
  }
  const citedPages = Object.keys(idsByPage).map(Number).sort((a, b) => a - b)
  if (hlPage && chunk != null && !(idsByPage[hlPage] || []).includes(chunk)) (idsByPage[hlPage] ||= []).push(chunk)

  useEffect(() => {
    setInfo(null)
    setError('')
    setTab('doc')
    setPage(1)
    api.content(doc).then(setInfo).catch((e) => setError(e.message))
  }, [doc])

  // Audio y video: la app comprueba si el navegador los puede reproducir. Si no (p. ej. HEVC de TikTok: se ve negro),
  // el servidor prepara una copia H.264 y aquí se espera a que esté lista.
  useEffect(() => {
    if (!(isAudio || isVideo)) return undefined
    let alive = true
    let timer
    triedForce.current = false
    const check = async (force = false) => {
      try {
        const p = await api.playback(doc, force)
        if (!alive) return
        setPlay(p)
        if (p.state === 'converting') timer = setTimeout(() => check(false), 1500)
      } catch (e) {
        if (alive) setPlay({ state: 'error', message: e.message })
      }
    }
    retry.current = () => check(true)
    setPlay(null)
    check()
    return () => { alive = false; clearTimeout(timer) }
  }, [doc, isAudio, isVideo])

  const mediaReady = !(isAudio || isVideo) || play?.state === 'original' || play?.state === 'ready'
  const mediaSrc = play ? `${play.url}?v=${play.state}` : file // «?v=» evita que el navegador reutilice el archivo original ya guardado en caché
  // El video se pide con «#t=0.1» para que el navegador pinte un primer fotograma en vez de dejar el cuadro negro
  // Si el navegador abre el video pero no tiene imagen (videoWidth = 0), se pide la copia compatible
  const onVideoMeta = (e) => {
    if (e.currentTarget.videoWidth === 0 && !triedForce.current) {
      triedForce.current = true
      setPlay({ state: 'converting', reason: 'formato que este navegador no muestra', url: file })
      retry.current()
    }
  }

  function seek(sec) {
    const el = media.current
    if (!el) return
    const go = () => {
      el.currentTime = sec
      el.play().catch(() => {}) // el navegador puede exigir un clic previo: no pasa nada si lo rechaza
    }
    if (el.readyState >= 1) go()
    else el.addEventListener('loadedmetadata', go, { once: true })
  }

  // Marcar una zona: se arrastra un rectángulo sobre la página; al soltar se avisa a la app (que la manda con cada pregunta)
  useEffect(() => {
    if (!picking) return undefined
    const esc = (e) => { if (e.key === 'Escape') { setPicking(false); setDrag(null) } }
    document.addEventListener('keydown', esc)
    return () => document.removeEventListener('keydown', esc)
  }, [picking])

  const clamp01 = (v) => Math.min(1, Math.max(0, v))
  const pointIn = (e) => {
    const b = e.currentTarget.getBoundingClientRect()
    return { x: clamp01((e.clientX - b.left) / b.width), y: clamp01((e.clientY - b.top) / b.height) }
  }
  function startDrag(e, n) {
    if (!picking || e.button > 0) return
    const p = pointIn(e)
    e.currentTarget.setPointerCapture(e.pointerId)
    setDrag({ page: n, x0: p.x, y0: p.y, x1: p.x, y1: p.y })
    e.preventDefault()
  }
  function moveDrag(e, n) {
    if (!drag || drag.page !== n) return
    const p = pointIn(e)
    setDrag((d) => d && { ...d, x1: p.x, y1: p.y })
  }
  function endDrag(e, n) {
    if (!drag || drag.page !== n) return
    const r = [Math.min(drag.x0, drag.x1), Math.min(drag.y0, drag.y1), Math.max(drag.x0, drag.x1), Math.max(drag.y0, drag.y1)]
    setDrag(null)
    if (r[2] - r[0] < 0.02 || r[3] - r[1] < 0.02) return // un clic suelto no es una zona
    setPicking(false)
    onZone({ doc, page: n, rect: r.map((v) => Math.round(v * 10000) / 10000) })
  }
  const boxOf = (n) => {
    const r = drag?.page === n ? [Math.min(drag.x0, drag.x1), Math.min(drag.y0, drag.y1), Math.max(drag.x0, drag.x1), Math.max(drag.y0, drag.y1)] : zone?.doc === doc && zone.page === n ? zone.rect : null
    return r && { left: `${r[0] * 100}%`, top: `${r[1] * 100}%`, width: `${(r[2] - r[0]) * 100}%`, height: `${(r[3] - r[1]) * 100}%` }
  }

  function goToPage(n) {
    const el = scroller.current?.querySelector(`[data-page="${n}"]`)
    el?.scrollIntoView({ block: 'start' })
    setPage(n)
  }

  // Al abrir una cita: saltar al minuto o a la página indicados
  useEffect(() => {
    if (!info || !goal || !mediaReady) return
    if (goal.kind === 'time') seek(goal.value)
    if (goal.kind === 'page' && isPdf) {
      setTab('doc')
      setTimeout(() => goToPage(goal.value), 60)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [info, loc, nonce, mediaReady])

  function pick(c) {
    const g = parseLoc(c.loc)
    if (!g) return
    if (g.kind === 'time') seek(g.value)
    if (g.kind === 'page') {
      setTab('doc')
      setTimeout(() => goToPage(g.value), 60)
    }
  }

  function onScroll() {
    const box = scroller.current
    if (!box) return
    const top = box.getBoundingClientRect().top
    for (const el of box.querySelectorAll('[data-page]')) {
      if (el.getBoundingClientRect().bottom > top + 60) {
        setPage(Number(el.dataset.page))
        break
      }
    }
  }

  const label = isPdf ? 'PDF' : isAudio ? 'Audio' : isVideo ? 'Video' : isImage ? 'Imagen' : 'Texto'

  return (
    <aside className="viewer" aria-label={`Visor de ${doc}`}>
      <header className="viewer-head">
        <div className="viewer-title">
          <strong title={doc}>{doc}</strong>
          <small>{label}{info?.pages ? ` · ${info.pages} páginas` : ''}</small>
        </div>
        {isPdf && info && (
          <div className="pager">
            <button className="icon-btn" onClick={() => goToPage(Math.max(1, page - 1))} aria-label="Página anterior">‹</button>
            <input
              value={page}
              inputMode="numeric"
              aria-label="Página"
              onChange={(e) => setPage(Number(e.target.value.replace(/\D/g, '')) || 1)}
              onKeyDown={(e) => e.key === 'Enter' && goToPage(Math.min(info.pages, Math.max(1, page)))}
            />
            <span>/ {info.pages}</span>
            <button className="icon-btn" onClick={() => goToPage(Math.min(info.pages, page + 1))} aria-label="Página siguiente">›</button>
          </div>
        )}
        <button className="icon-btn" onClick={onClose} aria-label="Cerrar visor" title="Cerrar visor">×</button>
      </header>

      {cited.length > 0 && info && (
        <div className="cited-bar">
          <span>La respuesta usó:</span>
          {cited.map((s) => (
            <button key={s.id} className="chip cited-chip" onClick={() => pick(s)} title="Ir a este punto">{s.loc}</button>
          ))}
        </div>
      )}

      {isPdf && info && (
        <>
        <div className="tabs" role="tablist">
          <button role="tab" aria-selected={tab === 'doc'} className={tab === 'doc' ? 'on' : ''} onClick={() => setTab('doc')}>Documento</button>
          <button role="tab" aria-selected={tab === 'text'} className={tab === 'text' ? 'on' : ''} onClick={() => setTab('text')}>Texto leído</button>
          {tab === 'doc' && (
            <span className="zone-tools">
              {zone?.doc === doc && <button className="link" onClick={onClearZone}>Quitar zona</button>}
              <button className={`btn small ${picking ? 'primary' : ''}`} aria-pressed={picking} onClick={() => { setPicking((p) => !p); setDrag(null) }}>{picking ? 'Cancelar' : zone?.doc === doc ? 'Marcar otra zona' : 'Marcar zona'}</button>
            </span>
          )}
        </div>
        {picking && tab === 'doc' && <div className="zone-hint">Arrastra sobre la página para marcar la zona sobre la que quieres preguntar. Esc para cancelar.</div>}
        </>
      )}

      <div className="viewer-body" ref={scroller} onScroll={isPdf && tab === 'doc' ? onScroll : undefined}>
        {error && <p className="error-text pad">{error}</p>}
        {!info && !error && <p className="muted pad">Abriendo…</p>}

        {info && isPdf && tab === 'doc' && (
          <div className="pdf-pages">
            {Array.from({ length: info.pages }, (_, i) => i + 1).map((n) => (
              <div
                key={`${doc}-${n}-${nonce}`} className={`pdf-page ${idsByPage[n] ? 'cited' : ''} ${picking ? 'picking' : ''}`} data-page={n}
                onPointerDown={(e) => startDrag(e, n)} onPointerMove={(e) => moveDrag(e, n)} onPointerUp={(e) => endDrag(e, n)} onPointerCancel={() => setDrag(null)}
              >
                <img
                  draggable={false}
                  loading={n === hlPage || citedPages.includes(n) || n <= 2 ? 'eager' : 'lazy'}
                  alt={`Página ${n}`}
                  src={`/api/page/${enc(doc)}/${n}?dpi=130${(idsByPage[n] || []).map((id) => `&chunk=${id}`).join('')}`}
                />
                {boxOf(n) && <div className={`zone-box ${drag?.page === n ? 'drawing' : ''}`} style={boxOf(n)}><span>Zona</span></div>}
                {idsByPage[n] && <span className="cited-badge">Citado en la respuesta</span>}
                <span className="page-no">{n}</span>
              </div>
            ))}
          </div>
        )}

        {info && isPdf && tab === 'text' && <ReadText chunks={info.chunks} active={activeIds} onPick={pick} title="Texto leído del PDF" />}

        {info && (isAudio || isVideo) && play && !mediaReady && (
          <div className={`convert-note ${play.state}`}>
            {play.state === 'converting' ? (
              <>
                <span className="spinner" aria-hidden />
                <div>
                  <strong>Preparando una versión que tu navegador pueda reproducir…</strong>
                  <p>Este video usa el formato {play.reason || 'no compatible'}, que muchos navegadores no leen (se ve la pantalla en negro). Tarda unos segundos y tu archivo original no se modifica.</p>
                </div>
              </>
            ) : (
              <div>
                <strong>No se pudo preparar el video para verlo aquí</strong>
                <p>{play.message || 'Error desconocido'}</p>
                <button className="btn small" onClick={() => { setPlay({ state: 'converting', reason: play.reason, url: file }); retry.current() }}>Reintentar</button>{' '}
                <a className="btn small" href={file} download>Descargar el original</a>
              </div>
            )}
          </div>
        )}
        {info && isAudio && mediaReady && (
          <>
            <audio key={`${doc}-${play?.state}`} ref={media} className="viewer-audio" controls preload="metadata" src={mediaSrc} />
            <ReadText chunks={info.chunks} active={activeIds} onPick={pick} title="Transcripción" />
          </>
        )}
        {info && isVideo && mediaReady && (
          <>
            <video key={`${doc}-${play?.state}`} ref={media} className="viewer-video" controls preload="metadata" src={`${mediaSrc}#t=0.1`} onLoadedMetadata={onVideoMeta} />
            <ReadText chunks={info.chunks} active={activeIds} onPick={pick} title="Lo que se dice y lo que se ve" />
          </>
        )}
        {info && isImage && (
          <>
            <img className="viewer-image" alt={doc} src={file} />
            <ReadText chunks={info.chunks} active={activeIds} onPick={pick} title="Lo que la app entendió de la imagen" />
          </>
        )}
        {info && !isPdf && !isAudio && !isVideo && !isImage && <ReadText chunks={info.chunks} active={activeIds} onPick={pick} title="Texto leído" />}
      </div>
    </aside>
  )
}
