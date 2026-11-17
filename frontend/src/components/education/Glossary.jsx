import { useState } from 'react'
import { GLOSSARY } from './content/index.js'

// 용어 사전: 학습 단계(유닛) 순서로 묶어서 보여준다
export default function Glossary({ completed, units = [] }) {
  const [q, setQ] = useState('')
  const [unit, setUnit] = useState('all')
  const unitOf = Object.fromEntries(units.flatMap((u, i) => u.lessons.map((l) => [l.id, { id: u.id, no: i + 1, title: u.title }])))
  const match = (g) => !q || g.term.toLowerCase().includes(q.toLowerCase()) || g.def.includes(q)
  const groups = units
    .map((u, i) => ({ ...u, no: i + 1, items: GLOSSARY.filter((g) => unitOf[g.lesson]?.id === u.id && match(g)) }))
    .filter((u) => u.items.length && (unit === 'all' || unit === u.id))
  const learned = GLOSSARY.filter((g) => completed.has(g.lesson)).length

  return (
    <section className="card glossary">
      <div className="card-head">
        <h2>용어 사전</h2>
        <span className="muted small">배운 용어 {learned} / {GLOSSARY.length}</span>
        <input placeholder="용어 검색 (예: PER, 코스피)" value={q} onChange={(e) => setQ(e.target.value)} />
      </div>
      <div className="symbol-pick">
        <button className={`chip-btn ${unit === 'all' ? 'on' : ''}`} onClick={() => setUnit('all')}>전체</button>
        {units.map((u, i) => (
          <button key={u.id} className={`chip-btn ${unit === u.id ? 'on' : ''}`} onClick={() => setUnit(u.id)}>
            {i + 1}. {u.title}
          </button>
        ))}
      </div>
      <p className="muted small">레슨을 완료하면 그 레슨에서 배운 용어에 ✓ 표시가 붙어요.</p>
      {groups.length === 0 && <p className="empty">검색 결과가 없어요</p>}
      {groups.map((u) => (
        <div key={u.id} className="glossary-group">
          <h4>
            <span className="unit-no">{u.no}단계</span> {u.title}
          </h4>
          <dl>
            {u.items.map((g) => (
              <div key={g.term} className={completed.has(g.lesson) ? 'learned' : ''}>
                <dt>{completed.has(g.lesson) && <span className="up">✓ </span>}{g.term}</dt>
                <dd>{g.def}</dd>
              </div>
            ))}
          </dl>
        </div>
      ))}
    </section>
  )
}
