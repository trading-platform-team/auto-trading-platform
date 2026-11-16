import { useEffect, useState } from 'react'

const IMPACT = {
  positive: { label: '긍정 요인', cls: 'up' },
  negative: { label: '부정 요인', cls: 'down' },
  mixed: { label: '복합 요인', cls: 'mixed' },
}

export default function MarketEvents({ events = [], currentDate }) {
  const visible = events.filter((event) => !currentDate || event.date <= currentDate)
  const [selectedId, setSelectedId] = useState(null)

  useEffect(() => {
    if (!visible.some((event) => event.id === selectedId)) {
      setSelectedId(visible.at(-1)?.id ?? null)
    }
  }, [selectedId, visible])

  const selected = visible.find((event) => event.id === selectedId)

  return (
    <section className="market-events" aria-label="해당 시점 주요 사건">
      <div className="card-head">
        <div>
          <h2>📰 해당 시점 뉴스·주요 사건</h2>
          <p className="muted small">차트의 ◆ 표시와 같은 날짜의 공식 발표를 확인해 보세요.</p>
        </div>
        <span className="tag">{visible.length}건</span>
      </div>

      {visible.length === 0 ? (
        <p className="empty">현재 공개된 날짜까지 등록된 주요 사건이 없습니다.</p>
      ) : (
        <div className="event-layout">
          <div className="event-list" role="list">
            {[...visible].reverse().map((event) => {
              const impact = IMPACT[event.impact] ?? IMPACT.mixed
              return (
                <button
                  key={event.id}
                  type="button"
                  role="listitem"
                  className={`event-item ${selectedId === event.id ? 'on' : ''}`}
                  onClick={() => setSelectedId(event.id)}
                >
                  <span className="event-date num">{event.date}</span>
                  <b>{event.title}</b>
                  <span className={`event-impact ${impact.cls}`}>{impact.label}</span>
                </button>
              )
            })}
          </div>
          {selected && (
            <article className="event-detail">
              <div className="event-meta">
                <span className="tag">{selected.category}</span>
                <span className="muted num">{selected.date}</span>
              </div>
              <h3>{selected.title}</h3>
              <p>{selected.summary}</p>
              <p className="event-caution">⚠ {selected.educational_note}</p>
              <a href={selected.source_url} target="_blank" rel="noreferrer" className="event-source">
                원문 확인 · {selected.source_name} ↗
              </a>
            </article>
          )}
        </div>
      )}
    </section>
  )
}
