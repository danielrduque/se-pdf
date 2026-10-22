// Mapa mental en SVG (sin librerías): raíz a la izquierda, ramas en el centro y sub-ideas a la derecha.
const CHAR = 6.7 // ancho aproximado de un carácter a 12 px
const LINE = 15
const GAP_Y = 8
const GAP_X = 44
const LEVELS = [{ chars: 18, lines: 3 }, { chars: 24, lines: 3 }, { chars: 32, lines: 3 }]

function wrap(text, chars, maxLines) {
  const lines = []
  let cur = ''
  for (const word of text.split(' ')) {
    if (cur && `${cur} ${word}`.length > chars) { lines.push(cur); cur = word } else cur = cur ? `${cur} ${word}` : word
  }
  if (cur) lines.push(cur)
  if (lines.length > maxLines) { lines.length = maxLines; lines[maxLines - 1] = `${lines[maxLines - 1].slice(0, chars - 1)}…` }
  return lines
}

function box(node, level) {
  const { chars, lines: max } = LEVELS[level]
  const lines = wrap(node.title, chars, max)
  const w = Math.max(...lines.map((l) => l.length)) * CHAR + 26
  return { node, level, lines, w, h: lines.length * LINE + 14 }
}

/** Calcula la posición de cada caja; devuelve las cajas, las líneas de unión y el tamaño total. */
function layout(root) {
  const colW = [0, 1, 2].map(() => 0)
  const branches = root.children.map((b) => ({ ...box(b, 1), kids: b.children.map((c) => box(c, 2)) }))
  const rootBox = box(root, 0)
  colW[0] = rootBox.w
  for (const b of branches) { colW[1] = Math.max(colW[1], b.w); for (const k of b.kids) colW[2] = Math.max(colW[2], k.w) }
  const x = [0, colW[0] + GAP_X, colW[0] + colW[1] + GAP_X * 2]

  let y = 0
  for (const b of branches) {
    const stack = b.kids.reduce((s, k) => s + k.h, 0) + GAP_Y * Math.max(0, b.kids.length - 1)
    const slot = Math.max(stack, b.h)
    let ky = y + (slot - stack) / 2
    for (const k of b.kids) { k.x = x[2]; k.y = ky; ky += k.h + GAP_Y }
    b.x = x[1]
    b.y = y + (slot - b.h) / 2
    y += slot + GAP_Y * 2
  }
  const total = y - GAP_Y * 2
  const first = branches[0]
  const last = branches[branches.length - 1]
  rootBox.x = 0
  rootBox.y = (first.y + last.y + last.h) / 2 - rootBox.h / 2
  const widths = branches.some((b) => b.kids.length) ? colW[0] + colW[1] + colW[2] + GAP_X * 2 : colW[0] + colW[1] + GAP_X
  return { rootBox, branches, width: widths, height: Math.max(total, rootBox.h) }
}

const link = (a, b) => {
  const x1 = a.x + a.w
  const y1 = a.y + a.h / 2
  const x2 = b.x
  const y2 = b.y + b.h / 2
  const mid = (x1 + x2) / 2
  return `M${x1},${y1} C${mid},${y1} ${mid},${y2} ${x2},${y2}`
}

function Node({ b, color, onOpen }) {
  const src = b.node.source
  const open = src ? () => onOpen(src.doc, src.loc, src.id, [{ id: src.id, loc: src.loc, kind: src.kind }]) : undefined
  return (
    <g
      className={`mm-node l${b.level} ${src ? 'link' : ''}`}
      style={{ '--c': color }}
      transform={`translate(${b.x},${b.y})`}
      onClick={open}
      onKeyDown={(e) => { if (open && (e.key === 'Enter' || e.key === ' ')) { e.preventDefault(); open() } }}
      role={src ? 'button' : undefined}
      tabIndex={src ? 0 : undefined}
    >
      {src && <title>{`Abrir ${src.doc}, ${src.loc}`}</title>}
      <rect width={b.w} height={b.h} rx={6} />
      {b.lines.map((l, i) => <text key={i} x={b.w / 2} y={7 + LINE * (i + 0.78)} textAnchor="middle">{l}</text>)}
      {src && <text className="mm-pin" x={b.w - 7} y={11} textAnchor="end">↗</text>}
    </g>
  )
}

export default function MindMap({ map, onOpen }) {
  const { rootBox, branches, width, height } = layout(map)
  const PALETTE = ['var(--accent)', 'var(--blue)', 'var(--green)', 'var(--amber)', 'var(--muted)']
  const color = (i) => PALETTE[i % PALETTE.length]
  return (
    <div className="mindmap">
      <div className="mm-scroll">
        <svg viewBox={`-4 -4 ${width + 8} ${height + 8}`} style={{ minWidth: Math.min(width, 640) }} role="img" aria-label={`Mapa mental: ${map.title}`}>
          <g fill="none" strokeWidth="1.8">
            {branches.map((b, i) => (
              <g key={i} style={{ stroke: color(i) }}>
                <path d={link(rootBox, b)} />
                {b.kids.map((k, j) => <path key={j} d={link(b, k)} strokeWidth="1.4" opacity="0.8" />)}
              </g>
            ))}
          </g>
          <Node b={rootBox} color="var(--text)" onOpen={onOpen} />
          {branches.map((b, i) => (
            <g key={i}>
              <Node b={b} color={color(i)} onOpen={onOpen} />
              {b.kids.map((k, j) => <Node key={j} b={k} color={color(i)} onOpen={onOpen} />)}
            </g>
          ))}
        </svg>
      </div>
      <div className="mm-foot">
        <small className="muted">Las ideas con ↗ abren el documento en el punto de donde salen.</small>
      </div>
    </div>
  )
}
