const TITLES = { upload: 'Leyendo tus documentos…', kb_sync: 'Leyendo la carpeta…' }

function fmtEta(s) {
  if (s == null || s < 4) return ''
  return s >= 60 ? ` · ~${Math.floor(s / 60)} min ${s % 60} s restantes` : ` · ~${s} s restantes`
}

/** Resultado normalizado: la subida devuelve {archivo: {chunks|error}} y la sincronización {indexed, removed, errors}. */
function outcome(job) {
  const r = job.result || {}
  if (job.kind === 'kb_sync') return { indexed: r.indexed || [], removed: r.removed || [], errors: r.errors || {} }
  const entries = Object.entries(r)
  return {
    indexed: entries.filter(([, v]) => !v.error).map(([k]) => k),
    removed: [],
    errors: Object.fromEntries(entries.filter(([, v]) => v.error).map(([k, v]) => [k, v.error])),
  }
}

export default function JobPanel({ job, onCancel, onDismiss }) {
  if (!job) return null
  const running = job.state === 'running' || job.state === 'queued'
  const { indexed, removed, errors } = outcome(job)
  const title = job.state === 'queued' ? 'En cola…' : running ? TITLES[job.kind] : { done: 'Listo, ya puedes preguntar', cancelled: 'Cancelado', error: 'Hubo un problema' }[job.state]

  return (
    <section className={`job ${job.state}`} aria-live="polite">
      <div className="job-head">
        <strong>{title}</strong>
        {running ? <button className="link danger" onClick={onCancel}>Cancelar lectura</button> : <button className="link" onClick={onDismiss}>Cerrar</button>}
      </div>
      {running && (
        <>
          <div className="bar"><div style={{ width: `${Math.round(job.progress * 100)}%` }} /></div>
          <div className="job-msg">
            {job.total > 1 && `[${Math.min(job.done + 1, job.total)}/${job.total}] `}
            {job.current && <b>{job.current}: </b>}
            {job.message}
            {fmtEta(job.eta_seconds)}
          </div>
        </>
      )}
      {job.state === 'done' && <div className="job-msg">{indexed.length} documento{indexed.length === 1 ? '' : 's'} leído{indexed.length === 1 ? '' : 's'}{removed.length ? ` · ${removed.length} quitado${removed.length === 1 ? '' : 's'} de la lista` : ''}.</div>}
      {job.state === 'cancelled' && <div className="job-msg">{job.message}</div>}
      {job.state === 'error' && <div className="job-msg error-text">{job.error}</div>}
      {Object.entries(errors).map(([name, err]) => (
        <div key={name} className="job-msg error-text">Error en {name}: {err}</div>
      ))}
    </section>
  )
}
