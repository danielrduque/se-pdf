const DAY = 86400
const STATE_TEXT = { running: 'Respondiendo…', done: 'Respuesta lista', error: 'Terminó con error' }

function groupOf(updated) {
  const now = new Date()
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime() / 1000
  if (updated >= today) return 'Hoy'
  if (updated >= today - DAY) return 'Ayer'
  if (updated >= today - 7 * DAY) return 'Últimos 7 días'
  return 'Antes'
}

function whenLabel(updated) {
  const d = new Date(updated * 1000)
  return groupOf(updated) === 'Hoy'
    ? d.toLocaleTimeString('es', { hour: '2-digit', minute: '2-digit' })
    : d.toLocaleDateString('es', { day: 'numeric', month: 'short' })
}

export default function ChatList({ chats, activeId, onOpen, onNew, onRename, onDelete }) {
  const closeMenu = (e) => { e.currentTarget.closest('details').open = false }
  const groups = []
  for (const c of chats) {
    const g = groupOf(c.updated)
    const last = groups[groups.length - 1]
    if (last?.name === g) last.items.push(c)
    else groups.push({ name: g, items: [c] })
  }

  return (
    <section className="chats">
      <button className="btn primary add" onClick={onNew}>+ Nuevo chat</button>
      {chats.length === 0 ? (
        <p className="muted small empty-docs">Todavía no hay chats. Tus conversaciones se guardan solas y aparecerán aquí.</p>
      ) : (
        <div className="chat-groups">
          {groups.map((g) => (
            <div key={g.name}>
              <h4>{g.name}</h4>
              <ul>
                {g.items.map((c) => (
                  <li key={c.key ?? c.id} className={c.key === activeId ? 'active' : ''}>
                    <button className="chat-open" onClick={() => onOpen(c.key ?? c.id)} title={c.title}>
                      <span className="chat-title">{c.state && <i className="dot" data-s={c.state} role="img" aria-label={STATE_TEXT[c.state]} />}{c.title}</span>
                      <small className={c.state ? `st-${c.state}` : ''}>{c.state ? `${STATE_TEXT[c.state]} · ` : ''}{c.doc ? `${c.doc} · ` : ''}{Math.ceil(c.count / 2)} pregunta{Math.ceil(c.count / 2) === 1 ? '' : 's'} · {whenLabel(c.updated)}</small>
                    </button>
                    {!c.local && (
                      <details className="menu">
                        <summary aria-label={`Opciones del chat ${c.title}`}>…</summary>
                        <div className="menu-pop">
                          <button onClick={(e) => { closeMenu(e); onRename(c) }}>Cambiar nombre</button>
                          <button className="danger" onClick={(e) => { closeMenu(e); onDelete(c) }}>Borrar chat</button>
                        </div>
                      </details>
                    )}
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
      )}
    </section>
  )
}
