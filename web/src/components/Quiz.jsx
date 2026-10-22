import { useState } from 'react'

const LETTERS = ['A', 'B', 'C', 'D']

function verdict(pct) {
  if (pct >= 80) return '¡Excelente! Dominas este tema.'
  if (pct >= 50) return 'Vas bien. Repasa lo que fallaste y vuelve a intentarlo.'
  return 'Conviene repasar: abre el documento y practica de nuevo.'
}

/** Examen de selección múltiple dentro de un mensaje del chat (se crea con el comando /examen). */
export default function Quiz({ quiz, onPick, onOpen, onMore }) {
  const { questions, picked, req } = quiz
  const firstOpen = picked.findIndex((p) => p == null)
  const [i, setI] = useState(firstOpen === -1 ? questions.length : firstOpen)
  const done = i >= questions.length
  const score = picked.filter((p, k) => p === questions[k].answer).length
  const openSource = (s) => s && onOpen(s.doc, s.loc, s.id, [{ id: s.id, loc: s.loc, kind: s.kind }])

  if (done) {
    const pct = Math.round((score / questions.length) * 100)
    const wrong = questions.map((q, k) => ({ q, k })).filter(({ q, k }) => picked[k] !== q.answer)
    return (
      <div className="quiz-box result">
        <div className="score-ring" style={{ '--pct': pct }}><span>{score}/{questions.length}</span></div>
        <p className="verdict"><b>{pct} % correcto.</b> {verdict(pct)}</p>
        {wrong.length > 0 && (
          <div className="review">
            <h4>Para repasar</h4>
            {wrong.map(({ q, k }) => (
              <article key={k} className="review-item">
                <p><b>{q.question}</b></p>
                <p className="bad">Tu respuesta: {q.options[picked[k]]}</p>
                <p className="ok">Correcta: {q.options[q.answer]}</p>
                {q.explanation && <p className="muted small">{q.explanation}</p>}
                {q.source && <button className="link" onClick={() => openSource(q.source)}>Ver en el documento →</button>}
              </article>
            ))}
          </div>
        )}
        <div className="btn-row">
          <button className="btn small" onClick={() => setI(0)}>↻ Ver de nuevo</button>
          <button className="btn small primary" onClick={() => onMore(req)}>+ Más preguntas</button>
        </div>
      </div>
    )
  }

  const q = questions[i]
  const chosen = picked[i]
  const revealed = chosen != null
  return (
    <div className="quiz-box">
      <div className="quiz-progress">
        <span>Examen · pregunta {i + 1} de {questions.length}</span>
        <span>Aciertos: {score}</span>
      </div>
      <h3 className="quiz-q">{q.question}</h3>
      <ul className="options">
        {q.options.map((o, k) => {
          const state = !revealed ? '' : k === q.answer ? 'right' : k === chosen ? 'wrong' : 'dim'
          return (
            <li key={k}>
              <button className={`option ${state}`} onClick={() => onPick(i, k)} disabled={revealed}>
                <b>{LETTERS[k]}</b>
                <span>{o}</span>
                {state === 'right' && <i aria-hidden>Correcta</i>}
                {state === 'wrong' && <i aria-hidden>Tu elección</i>}
              </button>
            </li>
          )
        })}
      </ul>
      {revealed && (
        <div className={`feedback ${chosen === q.answer ? 'ok' : 'bad'}`}>
          <strong>{chosen === q.answer ? '¡Correcto!' : `Era la ${LETTERS[q.answer]}: ${q.options[q.answer]}`}</strong>
          {q.explanation && <p>{q.explanation}</p>}
          {q.source && <button className="link" onClick={() => openSource(q.source)}>Ver en el documento: {q.source.doc}, {q.source.loc} →</button>}
        </div>
      )}
      <div className="quiz-actions">
        <span />
        <button className="btn small primary" onClick={() => setI(i + 1)} disabled={!revealed}>{i + 1 < questions.length ? 'Siguiente →' : 'Ver resultado'}</button>
      </div>
    </div>
  )
}
