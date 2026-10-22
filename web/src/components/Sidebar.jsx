import ChatList from './ChatList.jsx'

const firstModel = (m) => m.split(',')[0].trim()

/** Barra lateral: solo el historial de chats. Los documentos se escogen arriba, en «Escoge tu archivo». */
export default function Sidebar({ status, kb, jobRunning, chats, chatId, busy, onOpenChat, onNewChat, onRenameChat, onDeleteChat, onAdd, onSyncNow, onSettings, onClose }) {
  const pending = kb ? kb.new.length + kb.changed.length : 0
  const removed = kb ? kb.removed.length : 0

  return (
    <aside className="sidebar">
      <div className="brand">
        <span className="logo" aria-hidden />
        <strong>{status.app}</strong>
        <button className="icon-btn close" onClick={onClose} aria-label="Cerrar panel">×</button>
      </div>

      {(pending > 0 || removed > 0) && (
        <div className="notice">
          <p>
            {pending > 0
              ? <>Hay <b>{pending}</b> documento{pending === 1 ? '' : 's'} {kb.changed.length && !kb.new.length ? 'modificado' : 'nuevo'}{pending === 1 ? '' : 's'} en la carpeta.</>
              : <><b>{removed}</b> documento{removed === 1 ? '' : 's'} ya no está{removed === 1 ? '' : 'n'} en la carpeta.</>}
          </p>
          <button className="btn small primary" onClick={onSyncNow} disabled={jobRunning}>{pending > 0 ? 'Leer ahora' : 'Actualizar'}</button>
        </div>
      )}

      <ChatList chats={chats} activeId={chatId} busy={busy} onOpen={onOpenChat} onNew={onNewChat} onRename={onRenameChat} onDelete={onDeleteChat} />

      <button className="btn add-docs" onClick={onAdd}>+ Agregar documentos</button>

      <footer className="side-foot">
        <span className="where" data-cloud={status.cloud ? 'true' : 'false'}>{status.cloud ? 'En la nube' : 'Todo en tu PC'}<small>{firstModel(status.chat.model)}</small></span>
        <button className="btn small" onClick={onSettings}>Ajustes</button>
      </footer>
    </aside>
  )
}
