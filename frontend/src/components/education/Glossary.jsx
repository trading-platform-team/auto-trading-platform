import { useState } from 'react'
import { GLOSSARY } from './content/index.js'

export default function Glossary({ completed }) {
  const [q, setQ] = useState('')
  const items = GLOSSARY.filter((g) => !q || g.term.includes(q) || g.def.includes(q))
  return (
    <section className="card glossary">
      <div className="card-head">
        <h2>용어 사전</h2>
        <input placeholder="용어 검색" value={q} onChange={(e) => setQ(e.target.value)} />
      </div>
      <p className="muted small">레슨을 완료하면 그 레슨에서 배운 용어에 ✓ 표시가 붙어요.</p>
      <dl>
        {items.map((g) => (
          <div key={g.term} className={completed.has(g.lesson) ? 'learned' : ''}>
            <dt>{completed.has(g.lesson) && <span className="up">✓ </span>}{g.term}</dt>
            <dd>{g.def}</dd>
          </div>
        ))}
      </dl>
    </section>
  )
}
