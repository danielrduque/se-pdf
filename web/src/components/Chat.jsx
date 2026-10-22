import { useEffect, useRef, useState } from 'react'
import ReactMarkdown from 'react-markdown'
import { api, linkifyCitations, parseOpenHref, zoneUrl } from '../api.js'
import { typeLabel, typeTag } from '../docs.js'
import MindMap from './MindMap.jsx'
import Quiz from './Quiz.jsx'
import Sources from './Sources.jsx'

function Message({ m, onOpen, onPick, onMore }) {
  const resolve = (doc, loc) => m.sources?.find((s) => s.doc === doc && s.loc === loc)?.id ?? null
  if (m.role === 'user') {
    return (
      <div className="msg user">
        <div className="bubble">
          {m.zone && <figure className="zone-ref"><img src={zoneUrl(m.zone, 90)} alt={`Zona marcada, pág. ${m.zone.page}`} /><figcaption>Zona · pág. {m.zone.page}</figcaption></figure>}
          {m.content}
        </div>
      </div>
    )
  }
  return (
    <div className="msg assistant">
      <div className={`bubble ${m.quiz ? 'quiz-bubble' : ''} ${m.map ? 'map-bubble' : ''}`}>
        {m.error ? (
          <p className="error-text">Error: {m.error}</p>
        ) : m.map ? (
          <MindMap map={m.map} onOpen={onOpen} />
        ) : m.quiz ? (
          <Quiz quiz={m.quiz} onPick={onPick} onOpen={onOpen} onMore={onMore} />
        ) : m.content ? (
          <ReactMarkdown
            components={{
              a: ({ href, children }) => {
                const t = parseOpenHref(href)
                return t ? (
                  <button className="cite" title="Abrir en el visor" onClick={() => onOpen(t.doc, t.loc, resolve(t.doc, t.loc), m.sources)}>{children}</button>
                ) : (
                  <a href={href} target="_blank" rel="noreferrer">{children}</a>
                )
              },
            }}
          >
            {linkifyCitations(m.content)}
          </ReactMarkdown>
        ) : (
          <span className="typing"><i /><i /><i />{m.status && <em>{m.status}</em>}</span>
        )}
        {m.streaming && m.content && <span className="cursor" />}
        <Sources sources={m.sources} onOpen={onOpen} />
        {m.model && !m.streaming && <div className="meta">Respondió {m.model}</div>}
      </div>
    </div>
  )
}

/** Preguntas para empezar con el documento elegido: «Resume…» al instante y el resto las genera el modelo (y quedan guardadas). */
function Suggestions({ doc, disabled, onSend }) {
  const [state, setState] = useState({ doc: null, questions: null })

  useEffect(() => {
    let alive = true
    setState({ doc, questions: null })
    api.suggestions(doc).then((r) => alive && setState({ doc, questions: r.questions })).catch(() => alive && setState({ doc, questions: [] }))
    return () => { alive = false }
  }, [doc])

  const loading = state.doc !== doc || state.questions === null
  return (
    <div className="examples">
      <button className="example" onClick={() => onSend(`Resume el documento ${doc}`)} disabled={disabled}>Resume este documento</button>
      {loading && <div className="example loading"><span className="typing"><i /><i /><i /><em>Preparando preguntas sobre este documento…</em></span></div>}
      {!loading && state.questions.map((q) => (
        <button key={q} className="example" onClick={() => onSend(q)} disabled={disabled}>{q}</button>
      ))}
    </div>
  )
}

export default function Chat({ messages, busy, disabled, noDocs, doc, docs, zone, onClearZone, hint, onSend, onAdd, onPickDoc, onOpenSource, onPick, onMore }) {
  const [text, setText] = useState('')
  const bottom = useRef(null)

  useEffect(() => {
    if (messages.length) bottom.current?.scrollIntoView({ behavior: 'smooth', block: 'end' }) // con la pantalla de inicio se queda arriba
  }, [messages])

  function submit(e) {
    e?.preventDefault()
    const q = text.trim()
    if (!q || busy || disabled) return
    setText('')
    onSend(q)
  }

  return (
    <main className="chat">
      <div className="messages">
        {messages.length === 0 ? (
          noDocs ? (
            <div className="empty">
              <h2>Empecemos con <mark>tus documentos</mark></h2>
              <ol className="steps">
                <li><b>Agrega documentos</b><span>PDFs, imágenes, audios, videos o textos.</span></li>
                <li><b>Escoge tu archivo</b><span>Con la lista de arriba eliges de cuál quieres hablar.</span></li>
                <li><b>Pregunta lo que quieras</b><span>Cada respuesta te dice de qué página o minuto salió.</span></li>
              </ol>
              <button className="btn primary big" onClick={onAdd}>+ Agregar documentos</button>
            </div>
          ) : !doc ? (
            <div className="empty">
              <h2>Escoge tu <mark>archivo</mark></h2>
              <p>Elige uno de los documentos ya cargados. Se abre junto al chat y las preguntas tratan solo de ese archivo.</p>
              <ul className="file-list">
                {docs.map((d) => (
                  <li key={d.name}>
                    <button onClick={() => onPickDoc(d.name)}>
                      <span className="tag" data-t={typeTag(d.ext)}>{typeTag(d.ext)}</span>
                      <span className="file-name">{d.name}</span>
                      <small>{typeLabel(d.ext)}</small>
                    </button>
                  </li>
                ))}
              </ul>
            </div>
          ) : (
            <div className="empty">
              <h2>¿Qué quieres saber de <mark>{doc}</mark>?</h2>
              <p>Empieza con una de estas preguntas o escribe la tuya abajo.</p>
              <Suggestions doc={doc} disabled={disabled || busy} onSend={onSend} />
            </div>
          )
        ) : (
          messages.map((m, i) => <Message key={i} m={m} onOpen={onOpenSource} onPick={(q, k) => onPick(i, q, k)} onMore={onMore} />)
        )}
        <div ref={bottom} />
      </div>

      <form className="composer" onSubmit={submit}>
        {hint && <div className="hint">{hint}</div>}
        {zone && (
          <div className="zone-chip">
            <img src={zoneUrl(zone, 110)} alt={`Zona marcada, pág. ${zone.page}`} />
            <div className="zone-info">
              <b>Zona marcada · pág. {zone.page}</b>
              <span>Las preguntas tratan solo de esta zona.</span>
              <div className="zone-quick">
                {['Explica esta zona', 'Resume esta zona', '¿Qué datos aparecen aquí?'].map((q) => <button key={q} className="chip-btn" onClick={() => onSend(q)} disabled={disabled || busy}>{q}</button>)}
              </div>
            </div>
            <button className="icon-btn" onClick={onClearZone} aria-label="Quitar la zona" title="Quitar la zona">×</button>
          </div>
        )}
        <div className="composer-row">
          <textarea
            value={text}
            rows={1}
            placeholder={zone ? `Pregunta sobre la zona de la pág. ${zone.page}…` : doc ? `Pregunta sobre ${doc}…` : 'Escoge un archivo para preguntar'}
            onChange={(e) => setText(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey) submit(e)
            }}
            disabled={disabled}
          />
          <button className="send" type="submit" disabled={busy || disabled || !text.trim()} aria-label="Enviar">↑</button>
        </div>
      </form>
    </main>
  )
}
