import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { api, streamChat } from './api.js'
import AddDocsModal from './components/AddDocsModal.jsx'
import Chat from './components/Chat.jsx'
import DocBar from './components/DocBar.jsx'
import JobPanel from './components/JobPanel.jsx'
import SettingsModal from './components/SettingsModal.jsx'
import Sidebar from './components/Sidebar.jsx'
import Viewer from './components/Viewer.jsx'

const TERMINAL = ['done', 'error', 'cancelled']
const EXAM_CMD = /^\/examen\b/i
const MAP_CMD = /^\/mapa\b/i
const COMMAND = /^\/(examen|mapa)\b/i
const wide = () => window.matchMedia('(min-width: 901px)').matches // en pantallas chicas el visor tapa el chat: no se abre solo

const stored = (k) => { try { return localStorage.getItem(k) } catch { return null } }
const store = (k, v) => { try { v ? localStorage.setItem(k, v) : localStorage.removeItem(k) } catch { /* sin almacenamiento local: no pasa nada */ } }

// Cada conversación vive por su cuenta: puedes cambiar de chat mientras otro sigue respondiendo.
const newKey = () => `n-${Math.random().toString(36).slice(2, 9)}`
const emptyConv = (doc = null) => ({ key: newKey(), id: null, doc, messages: [], busy: false, summarizing: '', unseen: false, failed: false })
const signature = (ms) => `${ms.length}:${ms.at(-1)?.content?.length ?? 0}:${ms.at(-1)?.error ? 1 : 0}:${ms.map((m) => m.quiz?.picked.filter((p) => p != null).length ?? '').join(',')}`
const stateOf = (c) => (!c ? undefined : c.busy || c.summarizing ? 'running' : c.unseen ? (c.failed ? 'error' : 'done') : undefined)
const deriveTitle = (ms) => {
  const first = (ms.find((m) => m.role === 'user' && m.content)?.content ?? '').split(/\s+/).join(' ')
  return first.length > 60 ? `${first.slice(0, 60)}…` : first || 'Nuevo chat'
}

export default function App() {
  const [status, setStatus] = useState(null)
  const [kb, setKb] = useState(null)
  const [loadError, setLoadError] = useState('')
  const [selectedDoc, setSelectedDoc] = useState(null) // el archivo sobre el que se pregunta: todo el chat trata de él
  const [init] = useState(() => emptyConv())
  const [convs, setConvs] = useState(() => ({ [init.key]: init })) // todas las conversaciones abiertas en esta sesión, por clave
  const [activeKey, setActiveKeyState] = useState(init.key)
  const [job, setJob] = useState(null)
  const [modal, setModal] = useState(null) // null | 'add' | 'settings'
  const [drawer, setDrawer] = useState(false)
  const [viewer, setViewer] = useState(null) // {doc, loc, chunk, nonce}: documento abierto junto al chat
  const [opts, setOpts] = useState({ vision: true, rerank: false, lang: '' })
  const [zone, setZone] = useState(null) // zona del PDF marcada a mano: {doc, page, rect}; las preguntas tratan solo de ella
  const [chats, setChats] = useState([]) // los chats guardados en la base de datos
  const activeRef = useRef(init.key)
  const sigs = useRef({}) // clave -> firma de lo último que se guardó
  const queues = useRef({}) // clave -> guardados encadenados, para que dos seguidos no creen dos chats
  const ids = useRef({}) // clave -> id del chat ya creado en la base
  const restored = useRef(false)

  const active = convs[activeKey] ?? init
  const { messages, busy, summarizing } = active
  const chatId = active.id

  const upd = useCallback((key, fn) => setConvs((cs) => (cs[key] ? { ...cs, [key]: fn(cs[key]) } : cs)), [])
  const patchLast = useCallback((key, fn) => upd(key, (c) => {
    const ms = [...c.messages]
    ms[ms.length - 1] = { ...ms.at(-1), ...fn(ms.at(-1)) }
    return { ...c, messages: ms }
  }), [upd])
  // Al terminar: si el chat no es el que estás viendo, queda marcado para que lo notes
  const finish = useCallback((key) => upd(key, (c) => ({ ...c, busy: false, summarizing: '', unseen: activeRef.current !== key, failed: !!c.messages.at(-1)?.error })), [upd])

  const activate = useCallback((key) => {
    activeRef.current = key
    setActiveKeyState(key)
    upd(key, (c) => (c.unseen ? { ...c, unseen: false, failed: false } : c))
  }, [upd])

  // Agrega una conversación y descarta las vacías que ya no se usan
  const addConv = useCallback((c) => {
    setConvs((cs) => ({ ...Object.fromEntries(Object.entries(cs).filter(([k, x]) => x.messages.length || x.busy || k === activeRef.current)), [c.key]: c }))
    activate(c.key)
  }, [activate])

  const refreshChats = useCallback(() => api.chats().then(setChats).catch(() => {}), [])
  useEffect(() => { refreshChats() }, [refreshChats])

  function persist(c) {
    const body = { doc: c.doc ?? null, messages: c.messages.map(({ role, content, sources, model, error, quiz, map, zone: z }) => ({ role, content, sources, model, error, quiz, map, zone: z })) }
    queues.current[c.key] = (queues.current[c.key] ?? Promise.resolve()).then(async () => {
      try {
        const id = ids.current[c.key] ?? c.id
        if (id) await api.saveChat(id, body)
        else {
          const created = await api.createChat(body)
          ids.current[c.key] = created.id
          upd(c.key, (x) => ({ ...x, id: created.id }))
        }
        refreshChats()
      } catch { /* si falla el guardado no se interrumpe la conversación */ }
    })
  }

  // Guarda cada conversación cuando termina de responder (las que siguen en curso esperan)
  useEffect(() => {
    for (const c of Object.values(convs)) {
      if (c.busy || c.summarizing || c.messages.length === 0) continue
      const sig = signature(c.messages)
      if (sigs.current[c.key] === sig) continue
      sigs.current[c.key] = sig
      persist(c)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [convs])

  const refresh = useCallback(async () => {
    try {
      const [s, k] = await Promise.all([api.status(), api.kb()])
      setStatus(s)
      setKb(k)
      setLoadError('')
    } catch (e) {
      setLoadError(e.message)
    }
  }, [])

  useEffect(() => { refresh() }, [refresh])

  // Mientras hay un trabajo en marcha se consulta su progreso; al terminar se actualiza todo.
  useEffect(() => {
    if (!job || TERMINAL.includes(job.state)) return undefined
    const timer = setInterval(async () => {
      try {
        const j = await api.job(job.id)
        setJob(j)
        if (TERMINAL.includes(j.state)) refresh()
      } catch (e) {
        setJob((cur) => (cur ? { ...cur, state: 'error', error: e.message } : cur))
      }
    }, 700)
    return () => clearInterval(timer)
  }, [job?.id, job?.state, refresh])

  const docs = status?.docs ?? []

  // Al abrir la app se vuelve al último archivo escogido; si ese archivo ya no existe, se deja de apuntar a él.
  useEffect(() => {
    if (!status) return
    const names = status.docs.map((d) => d.name)
    if (!restored.current) {
      restored.current = true
      const saved = stored('chatdd.doc')
      if (saved && names.includes(saved)) {
        upd(activeRef.current, (c) => ({ ...c, doc: saved }))
        setSelectedDoc(saved)
        if (wide()) setViewer({ doc: saved, loc: null, chunk: null, nonce: Date.now(), sources: [] })
      }
    } else if (selectedDoc && !names.includes(selectedDoc)) {
      setSelectedDoc(null)
      setViewer(null)
      store('chatdd.doc', '')
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [status])

  function showDoc(name) {
    setZone(null)
    setSelectedDoc(name)
    store('chatdd.doc', name)
    setViewer(wide() ? { doc: name, loc: null, chunk: null, nonce: Date.now(), sources: [] } : null)
  }

  function newChat() {
    setDrawer(false)
    setZone(null)
    if (!active.messages.length) return // ya estás en uno vacío
    addConv(emptyConv(selectedDoc))
  }

  // Escoger un archivo: se abre junto al chat y empieza una conversación nueva sobre él (el chat anterior no se toca)
  function selectDoc(name) {
    if (name === selectedDoc) return
    showDoc(name)
    if (!active.messages.length) upd(activeKey, (c) => ({ ...c, doc: name }))
    else addConv(emptyConv(name))
  }

  async function openChat(key) {
    setDrawer(false)
    let conv = Object.values(convs).find((c) => c.key === key || c.id === key)
    if (!conv) {
      try {
        const data = await api.getChat(key)
        const messagesLoaded = data.messages.map((m) => ({ ...m, streaming: false }))
        conv = { ...emptyConv(data.doc ?? selectedDoc), key, id: key, messages: messagesLoaded }
        sigs.current[key] = signature(messagesLoaded)
        addConv(conv)
      } catch (e) {
        setLoadError(e.message)
        refreshChats()
        return
      }
    } else {
      activate(conv.key)
    }
    if (conv.doc && conv.doc !== selectedDoc && docs.some((d) => d.name === conv.doc)) showDoc(conv.doc) // el chat trata de otro archivo: se vuelve a él
  }

  async function renameChat(c) {
    const title = window.prompt('Nuevo nombre del chat', c.title)
    if (title === null || !title.trim()) return
    try { await api.renameChat(c.id, title); refreshChats() } catch (e) { setLoadError(e.message) }
  }

  async function deleteChat(c) {
    if (!window.confirm(`¿Borrar el chat «${c.title}»? No se puede deshacer.`)) return
    try {
      await api.deleteChat(c.id)
      const mine = Object.values(convs).find((x) => x.id === c.id)
      if (mine) {
        setConvs((cs) => Object.fromEntries(Object.entries(cs).filter(([k]) => k !== mine.key)))
        if (activeKey === mine.key) addConv(emptyConv(selectedDoc))
      }
      refreshChats()
    } catch (e) { setLoadError(e.message) }
  }

  // Lista del panel: los chats guardados más los que todavía no se guardaron (la primera respuesta en curso), con su estado
  const entries = useMemo(() => {
    const byId = new Map(Object.values(convs).filter((c) => c.id).map((c) => [c.id, c]))
    const saved = chats.map((c) => { const cv = byId.get(c.id); return { ...c, key: cv?.key ?? c.id, state: stateOf(cv), count: cv ? Math.max(cv.messages.length, c.count) : c.count } })
    const local = Object.values(convs).filter((c) => !c.id && c.messages.length).map((c) => ({ id: c.key, key: c.key, title: deriveTitle(c.messages), updated: Date.now() / 1000, count: c.messages.length, doc: c.doc, local: true, state: stateOf(c) }))
    return [...local, ...saved]
  }, [convs, chats])

  const jobRunning = !!job && !TERMINAL.includes(job.state)
  const others = entries.filter((e) => e.state && e.key !== activeKey)
  const attention = others.find((e) => e.state === 'error')?.state ?? others.find((e) => e.state === 'done')?.state ?? others[0]?.state

  // Lo que la respuesta citó de este documento: el visor lo pinta de amarillo (como «Fuentes», pero sobre el documento completo)
  const citedOf = (doc, sources) => (sources ?? []).filter((s) => s.doc === doc).map(({ id, loc, kind }) => ({ id, loc, kind }))
  const latestSources = () => [...messages].reverse().find((m) => m.role === 'assistant' && m.sources?.length)?.sources ?? []

  function openDoc(doc, loc = null, chunk = null, sources = null) {
    setDrawer(false)
    setViewer({ doc, loc, chunk, nonce: Date.now(), sources: citedOf(doc, sources ?? latestSources()) })
  }

  // Al terminar una respuesta nueva (o al cambiar de chat), el visor abierto marca lo que la última respuesta citó
  useEffect(() => {
    if (busy || !viewer) return
    const marks = citedOf(viewer.doc, latestSources())
    setViewer((v) => (v && JSON.stringify(v.sources) !== JSON.stringify(marks) ? { ...v, sources: marks } : v))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [busy, activeKey])

  async function startJob(promise) {
    setModal(null)
    setDrawer(false)
    try {
      setJob(await promise)
    } catch (e) {
      setJob({ id: 'x', kind: 'upload', state: 'error', error: e.message, progress: 0, result: {} })
    }
  }

  async function send(question) {
    const key = activeKey
    const doc = selectedDoc
    if (!doc || convs[key].busy) return
    if (EXAM_CMD.test(question)) return exam(question)
    if (MAP_CMD.test(question)) return mindmap(question)
    const z = zone && zone.doc === doc ? zone : null // con una zona marcada, la pregunta trata solo de esa zona
    const history = messages.filter((m) => !m.error && m.content && !COMMAND.test(m.content)).map(({ role, content }) => ({ role, content }))
    upd(key, (c) => ({ ...c, doc: c.doc ?? doc, busy: true, unseen: false, messages: [...c.messages, { role: 'user', content: question, ...(z ? { zone: z } : {}) }, { role: 'assistant', content: '', sources: [], streaming: true }] }))
    const patch = (fn) => patchLast(key, fn)
    try {
      await streamChat(
        { question, history, docs: [doc], rerank: opts.rerank, zone: z ? { page: z.page, rect: z.rect } : undefined },
        {
          sources: (sources) => patch(() => ({ sources })),
          status: ({ message }) => patch(() => ({ status: message })),
          token: ({ t }) => patch((b) => ({ content: b.content + t, status: '' })),
          done: ({ model }) => patch(() => ({ streaming: false, status: '', model })),
          error: ({ message }) => patch(() => ({ streaming: false, error: message })),
        },
      )
    } catch (e) {
      patch(() => ({ streaming: false, error: e.message }))
    } finally {
      patch((b) => ({ streaming: false, ...(b.content || b.error ? {} : { error: 'No hubo respuesta.' }) }))
      finish(key)
    }
  }

  // Con qué trabajan /examen y /mapa: el archivo escogido
  const studyTarget = (topic, n) => (selectedDoc ? { doc: selectedDoc, question: topic, n } : null)

  // «/mapa [tema]»: mapa mental del archivo escogido
  async function mindmap(command, repeat = null) {
    const key = activeKey
    const topic = command.replace(MAP_CMD, '').trim()
    const req = repeat ?? studyTarget(topic, 0)
    upd(key, (c) => ({ ...c, busy: true, unseen: false, messages: [...c.messages, { role: 'user', content: command }, { role: 'assistant', content: '', status: 'Dibujando el mapa mental…', streaming: true }] }))
    const patch = (fields) => patchLast(key, () => ({ streaming: false, status: '', ...fields }))
    try {
      if (!req) throw new Error('Escoge un archivo y vuelve a escribir /mapa.')
      const { map } = await api.mindmap(req)
      patch({ map })
    } catch (e) {
      patch({ error: e.message })
    } finally {
      finish(key)
    }
  }

  // «/examen [n] [tema]»: preguntas de selección múltiple del archivo escogido
  async function exam(command, repeat = null) {
    const key = activeKey
    const arg = command.replace(EXAM_CMD, '').trim()
    const num = arg.match(/^\d+/)
    const n = repeat?.n ?? Math.min(Math.max(num ? Number(num[0]) : 5, 1), 10)
    const topic = repeat?.question ?? arg.replace(/^\d+\s*/, '')
    const req = repeat ?? studyTarget(topic, n)
    upd(key, (c) => ({ ...c, busy: true, unseen: false, messages: [...c.messages, ...(repeat ? [] : [{ role: 'user', content: command }]), { role: 'assistant', content: '', status: 'Preparando las preguntas…', streaming: true }] }))
    const patch = (fields) => patchLast(key, () => ({ streaming: false, status: '', ...fields }))
    try {
      if (!req) throw new Error('Escoge un archivo y vuelve a escribir /examen.')
      const { questions } = await api.quiz(req)
      patch({ quiz: { questions, picked: questions.map(() => null), req } })
    } catch (e) {
      patch({ error: e.message })
    } finally {
      finish(key)
    }
  }

  const pick = (msgIndex, q, k) => upd(activeKey, (c) => ({ ...c, messages: c.messages.map((m, i) => (i === msgIndex && m.quiz ? { ...m, quiz: { ...m.quiz, picked: m.quiz.picked.map((p, j) => (j === q ? k : p)) } } : m)) }))

  async function summarize(doc) {
    const key = activeKey
    setDrawer(false)
    upd(key, (c) => ({ ...c, summarizing: doc, unseen: false, messages: [...c.messages, { role: 'user', content: `Resume el documento «${doc}»` }] }))
    try {
      const { summary } = await api.summarize(doc)
      upd(key, (c) => ({ ...c, messages: [...c.messages, { role: 'assistant', content: summary }] }))
    } catch (e) {
      upd(key, (c) => ({ ...c, messages: [...c.messages, { role: 'assistant', content: '', error: e.message }] }))
    } finally {
      finish(key)
    }
  }

  async function remove(name) {
    if (!window.confirm(`¿Quitar «${name}» de la lista? El archivo original no se borra.`)) return
    try {
      await api.deleteDoc(name)
      setViewer((v) => (v?.doc === name ? null : v))
      await refresh()
    } catch (e) {
      setLoadError(e.message)
    }
  }

  if (!status) {
    return <div className="boot">{loadError ? <><h2>No se pudo conectar con el servidor</h2><p>{loadError}</p><button className="btn primary" onClick={refresh}>Reintentar</button></> : 'Cargando…'}</div>
  }

  const noDocs = docs.length === 0
  const hasProblems = status.problems.length > 0
  // Un chat guardado puede tratar de un archivo que ya no está cargado: se avisa y no se deja preguntar (iría a otro archivo sin que se note)
  const missingDoc = active.doc && !docs.some((d) => d.name === active.doc) ? active.doc : null
  const hint = missingDoc
    ? `Este chat trata de «${missingDoc}», que ya no está cargado. Escoge otro archivo y empieza un chat nuevo.`
    : !hasProblems && !noDocs && !selectedDoc ? 'Escoge un archivo arriba para empezar a preguntar.' : null

  return (
    <div className={`app ${drawer ? 'drawer-open' : ''}`}>
      <div className="scrim" onClick={() => setDrawer(false)} />
      <div className="side-wrap">
        <Sidebar
          status={status} kb={kb} jobRunning={jobRunning}
          chats={entries} chatId={activeKey}
          onOpenChat={openChat} onNewChat={newChat} onRenameChat={renameChat} onDeleteChat={deleteChat}
          onAdd={() => { setDrawer(false); setModal('add') }}
          onSyncNow={() => startJob(api.syncKb(opts.vision, opts.lang))}
          onSettings={() => setModal('settings')} onClose={() => setDrawer(false)}
        />
      </div>

      <div className="content">
        <DocBar
          docs={docs} selected={selectedDoc} viewing={viewer?.doc === selectedDoc} busy={busy} summarizing={summarizing}
          onSelect={selectDoc} onAdd={() => setModal('add')} onOpenViewer={() => selectedDoc && openDoc(selectedDoc)}
          onSummarize={summarize} onRemove={remove} onNewChat={newChat} hasChat={messages.length > 0} onOpenSidebar={() => setDrawer(true)} attention={attention}
        />
        {hasProblems && (
          <div className="banner error" role="alert">
            <strong>Hay un problema con los modelos</strong>
            <ul>{status.problems.map((p) => <li key={p}>{p}</li>)}</ul>
            <button className="btn small" onClick={() => setModal('settings')}>Abrir ajustes</button>
          </div>
        )}
        <JobPanel job={job} onCancel={() => api.cancel(job.id)} onDismiss={() => setJob(null)} />
        {loadError && <div className="banner error">{loadError}</div>}
        <div className={`workspace ${viewer ? 'split' : ''}`}>
          {viewer && <Viewer key={viewer.doc} target={viewer} zone={zone} onZone={(z) => { setZone(z); if (!wide()) setViewer(null) }} onClearZone={() => setZone(null)} onClose={() => setViewer(null)} />}
          <Chat
            key={activeKey}
            messages={messages} busy={busy || !!summarizing} noDocs={noDocs} doc={selectedDoc} docs={docs} zone={zone?.doc === selectedDoc ? zone : null} onClearZone={() => setZone(null)} disabled={noDocs || !selectedDoc || hasProblems || !!missingDoc} hint={hint}
            onSend={send} onAdd={() => setModal('add')} onPickDoc={selectDoc} onOpenSource={openDoc}
            onPick={pick} onMore={(req) => exam('/examen', req)}
          />
        </div>
      </div>

      {modal === 'add' && (
        <AddDocsModal
          status={status} kb={kb} opts={opts} setOpts={setOpts} jobRunning={jobRunning}
          onUpload={(files) => startJob(api.upload(files, opts.vision, opts.lang))}
          onSync={() => startJob(api.syncKb(opts.vision, opts.lang))}
          onOpenFolder={api.openFolder} onClose={() => setModal(null)}
        />
      )}
      {modal === 'settings' && (
        <SettingsModal status={status} opts={opts} setOpts={setOpts} onSave={async (body) => { setStatus(await api.saveSettings(body)) }} onClose={() => setModal(null)} />
      )}
    </div>
  )
}
