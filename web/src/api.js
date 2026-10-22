const JSON_HEADERS = { 'Content-Type': 'application/json' }

async function j(url, opts = {}) {
  const r = await fetch(url, opts)
  if (!r.ok) {
    let detail = r.statusText
    try {
      detail = (await r.json()).detail || detail
    } catch {
      /* respuesta sin JSON */
    }
    throw new Error(detail)
  }
  return r.json()
}

export const api = {
  status: () => j('/api/status'),
  saveSettings: (body) => j('/api/settings', { method: 'POST', headers: JSON_HEADERS, body: JSON.stringify(body) }),
  deleteDoc: (name) => j(`/api/docs/${encodeURIComponent(name)}`, { method: 'DELETE' }),
  upload: (files, useVision, lang) => {
    const form = new FormData()
    files.forEach((f) => form.append('files', f))
    form.append('use_vision', useVision)
    form.append('lang', lang)
    return j('/api/upload', { method: 'POST', body: form })
  },
  job: (id) => j(`/api/jobs/${id}`),
  cancel: (id) => j(`/api/jobs/${id}/cancel`, { method: 'POST' }),
  chats: () => j('/api/chats'),
  getChat: (id) => j(`/api/chats/${id}`),
  createChat: (body) => j('/api/chats', { method: 'POST', headers: JSON_HEADERS, body: JSON.stringify(body) }),
  saveChat: (id, body) => j(`/api/chats/${id}`, { method: 'PUT', headers: JSON_HEADERS, body: JSON.stringify(body) }),
  renameChat: (id, title) => j(`/api/chats/${id}`, { method: 'PATCH', headers: JSON_HEADERS, body: JSON.stringify({ title }) }),
  deleteChat: (id) => j(`/api/chats/${id}`, { method: 'DELETE' }),
  playback: (name, force = false) => j(`/api/docs/${encodeURIComponent(name)}/playback${force ? '?force=true' : ''}`),
  quiz: (body) => j('/api/quiz', { method: 'POST', headers: JSON_HEADERS, body: JSON.stringify(body) }),
  mindmap: (body) => j('/api/mindmap', { method: 'POST', headers: JSON_HEADERS, body: JSON.stringify(body) }),
  content: (name) => j(`/api/docs/${encodeURIComponent(name)}/content`),
  kb: () => j('/api/kb'),
  openFolder: () => j('/api/kb/open', { method: 'POST' }),
  syncKb: (useVision, lang) => j('/api/kb/sync', { method: 'POST', headers: JSON_HEADERS, body: JSON.stringify({ use_vision: useVision, lang }) }),
  suggestions: (name) => j(`/api/docs/${encodeURIComponent(name)}/suggestions`),
  summarize: (doc) => j('/api/summarize', { method: 'POST', headers: JSON_HEADERS, body: JSON.stringify({ doc }) }),
}

/** Chat con streaming (SSE sobre POST): llama a handlers.sources / token / done / error según llegan los eventos. */
export async function streamChat(body, handlers, signal) {
  const r = await fetch('/api/chat', { method: 'POST', headers: JSON_HEADERS, body: JSON.stringify(body), signal })
  if (!r.ok || !r.body) throw new Error('No se pudo conectar con el servidor')
  const reader = r.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  for (;;) {
    const { done, value } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })
    let end
    while ((end = buffer.indexOf('\n\n')) >= 0) {
      const block = buffer.slice(0, end)
      buffer = buffer.slice(end + 2)
      let event = 'message'
      let data = ''
      for (const line of block.split('\n')) {
        if (line.startsWith('event: ')) event = line.slice(7)
        else if (line.startsWith('data: ')) data += line.slice(6)
      }
      if (data) handlers[event]?.(JSON.parse(data))
    }
  }
}

/** 'pág. 7' -> {kind:'page', value:7}; '02:14–02:40' -> {kind:'time', value:134}; otro -> null */
export function parseLoc(loc) {
  let m = loc.match(/pág\.\s*(\d+)/)
  if (m) return { kind: 'page', value: Number(m[1]) }
  m = loc.match(/^(\d+):(\d{2})/)
  if (m) return { kind: 'time', value: Number(m[1]) * 60 + Number(m[2]) }
  return null
}

/** Recorte de la zona marcada (miniatura en el chat y vista previa). */
export const zoneUrl = (z, dpi = 110) => `/api/zone/${encodeURIComponent(z.doc)}/${z.page}?x0=${z.rect[0]}&y0=${z.rect[1]}&x1=${z.rect[2]}&y1=${z.rect[3]}&dpi=${dpi}`

export const AUDIO = ['mp3', 'wav', 'm4a', 'flac', 'ogg', 'aac']
export const VIDEO = ['mp4', 'mkv', 'mov', 'avi', 'webm']
export const IMAGE = ['png', 'jpg', 'jpeg', 'webp', 'bmp']
export const extOf = (name) => name.split('.').pop().toLowerCase()

// «[contrato.pdf, pág. 2]» en una respuesta se convierte en un enlace que abre el visor en ese punto
const CITE = /\[([^[\]]+?\.(?:pdf|mp4|mkv|mov|avi|webm|wav|mp3|m4a|flac|ogg|aac|png|jpe?g|webp|bmp|txt|md)),\s*([^[\]]+?)\]/gi
const safe = (t) => encodeURIComponent(t).replace(/\(/g, '%28').replace(/\)/g, '%29')

export function linkifyCitations(text) {
  return text.replace(CITE, (_, file, loc) => `[${file}, ${loc}](#open/${safe(file)}/${safe(loc)})`)
}

export function parseOpenHref(href) {
  if (!href?.startsWith('#open/')) return null  // se usa «/» porque el procesador de Markdown reescribe otros separadores (p. ej. «|»)
  const [, file, loc] = href.split('/')
  return { doc: decodeURIComponent(file), loc: decodeURIComponent(loc) }
}
