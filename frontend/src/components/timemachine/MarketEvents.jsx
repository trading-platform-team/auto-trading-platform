import { useEffect, useState } from 'react'
import { api } from '../../api'

function eventType(event) {
  if (event.source_name === 'OpenDART') return '공시'
  if (event.source_name === 'NAVER 뉴스') return '뉴스'
  return '주요 사건'
}

function disclosureImage(event, content) {
  const canvas = document.createElement('canvas')
  canvas.width = 900
  canvas.height = 1200
  const ctx = canvas.getContext('2d')
  ctx.fillStyle = '#fff'
  ctx.fillRect(0, 0, canvas.width, canvas.height)
  ctx.fillStyle = '#20242c'
  ctx.font = 'bold 28px sans-serif'
  ctx.fillText('전자공시 미리보기', 54, 65)
  ctx.font = 'bold 24px sans-serif'
  ctx.fillText(event.title.slice(0, 48), 54, 116)
  ctx.fillStyle = '#68707d'
  ctx.font = '18px sans-serif'
  ctx.fillText(`${event.date} · OpenDART`, 54, 151)
  ctx.strokeStyle = '#d9dde5'
  ctx.beginPath()
  ctx.moveTo(54, 177)
  ctx.lineTo(846, 177)
  ctx.stroke()

  ctx.fillStyle = '#303640'
  ctx.font = '18px sans-serif'
  let y = 220
  for (const paragraph of content.split('\n')) {
    let line = ''
    for (const char of paragraph) {
      const next = line + char
      if (ctx.measureText(next).width > 790) {
        ctx.fillText(line, 54, y)
        y += 31
        line = char
      } else line = next
      if (y > 1110) break
    }
    if (y > 1110) break
    if (line) {
      ctx.fillText(line, 54, y)
      y += 31
    }
    y += 9
  }
  ctx.fillStyle = '#68707d'
  ctx.font = '16px sans-serif'
  ctx.fillText('미리보기입니다. 정확한 전체 내용은 OpenDART 원문에서 확인하세요.', 54, 1160)
  return canvas.toDataURL('image/png')
}

export default function MarketEvents({ events = [], currentDate }) {
  const visible = events.filter((event) => !currentDate || event.date <= currentDate)
  const [selectedId, setSelectedId] = useState(null)
  const [previewImage, setPreviewImage] = useState(null)
  const [previewState, setPreviewState] = useState('idle')
  const [previewOpen, setPreviewOpen] = useState(false)

  useEffect(() => {
    if (!visible.some((event) => event.id === selectedId)) {
      setSelectedId(visible.at(-1)?.id ?? null)
    }
  }, [selectedId, visible])

  const selected = visible.find((event) => event.id === selectedId)

  useEffect(() => {
    let cancelled = false
    setPreviewImage(null)
    setPreviewOpen(false)
    if (!selected?.rcept_no) {
      setPreviewState('idle')
      return () => { cancelled = true }
    }
    setPreviewState('loading')
    api.disclosurePreview(selected.rcept_no)
      .then((result) => {
        if (!cancelled) {
          setPreviewImage(disclosureImage(selected, result.content))
          setPreviewState('done')
        }
      })
      .catch(() => {
        if (!cancelled) setPreviewState('error')
      })
    return () => { cancelled = true }
  }, [selected?.id, selected?.rcept_no])

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
                  <span className="event-category">{eventType(event)}</span>
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
              {selected.rcept_no && (
                <div className="disclosure-preview-wrap">
                  <b>공시 미리보기</b>
                  {previewState === 'loading' && <p className="muted small">미리보기를 만드는 중입니다…</p>}
                  {previewState === 'error' && <p className="muted small">미리보기를 만들지 못했습니다. 원문 링크를 이용해 주세요.</p>}
                  {previewImage && (
                    <button type="button" className="disclosure-preview-button" onClick={() => setPreviewOpen(true)}>
                      <img src={previewImage} alt={`${selected.title} 공시 미리보기`} />
                      <span>눌러서 크게 보기</span>
                    </button>
                  )}
                </div>
              )}
              <p className="event-caution">⚠ {selected.educational_note}</p>
              <a href={selected.source_url} target="_blank" rel="noreferrer" className="event-source">
                원문 확인 · {selected.source_name} ↗
              </a>
            </article>
          )}
        </div>
      )}
      {previewOpen && previewImage && (
        <div className="disclosure-modal" role="dialog" aria-modal="true" aria-label="공시 미리보기 확대">
          <button type="button" className="disclosure-modal-backdrop" aria-label="닫기" onClick={() => setPreviewOpen(false)} />
          <div className="disclosure-modal-content">
            <button type="button" className="disclosure-modal-close" onClick={() => setPreviewOpen(false)}>✕ 닫기</button>
            <img src={previewImage} alt={`${selected?.title ?? ''} 공시 확대 미리보기`} />
            <a href={selected?.source_url} target="_blank" rel="noreferrer" className="event-source">
              OpenDART 전체 원문 보기 ↗
            </a>
          </div>
        </div>
      )}
    </section>
  )
}
