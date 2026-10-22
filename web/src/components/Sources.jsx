import { AUDIO, IMAGE, VIDEO, extOf, parseLoc } from '../api.js'

const KIND_LABEL = { texto: 'Texto', visión: 'Imagen', audio: 'Audio' }

/** La evidencia de una fuente: página del PDF resaltada, imagen, o audio/video en el segundo citado. */
function Evidence({ source }) {
  const ext = extOf(source.doc)
  const loc = parseLoc(source.loc)
  const file = `/api/files/${encodeURIComponent(source.doc)}`
  if (ext === 'pdf' && loc?.kind === 'page') {
    return (
      <img
        className="evidence page"
        loading="lazy"
        alt={`${source.doc}, ${source.loc}`}
        src={`/api/page/${encodeURIComponent(source.doc)}/${loc.value}?chunk=${source.id}`}
      />
    )
  }
  if (AUDIO.includes(ext) && loc?.kind === 'time') return <audio className="evidence" controls preload="metadata" src={`${file}#t=${loc.value}`} />
  if (VIDEO.includes(ext) && loc?.kind === 'time') return <video className="evidence video" controls preload="metadata" src={`${file}#t=${loc.value}`} />
  if (IMAGE.includes(ext)) return <img className="evidence image" loading="lazy" alt={source.doc} src={file} />
  return null
}

export default function Sources({ sources, onOpen }) {
  if (!sources?.length) return null
  return (
    <details className="sources">
      <summary>
        Fuentes <span className="count">{sources.length}</span>
      </summary>
      <div className="source-list">
        {sources.map((s, i) => (
          <article key={s.id} className="source">
            <header>
              <strong>{s.doc}</strong>
              <span className="chip">{s.loc}</span>
              <span className="chip soft">{KIND_LABEL[s.kind] || s.kind}</span>
              {s.via === 'media' && <span className="chip via" title="La pregunta coincidió directamente con la imagen o el audio (embeddings multimodales), no con su descripción o transcripción">por {s.kind === 'audio' ? 'el audio' : 'la imagen'}</span>}
              {s.score != null && <span className="score" title="Similitud con la pregunta">{Math.round(s.score * 100)} %</span>}
              <button className="link open-src" onClick={() => onOpen(s.doc, s.loc, s.id, sources)}>Abrir en el visor →</button>
            </header>
            {i < 3 && <Evidence source={s} />}
            <p className="snippet">{s.text}</p>
          </article>
        ))}
      </div>
    </details>
  )
}
