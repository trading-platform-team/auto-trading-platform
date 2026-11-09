import { fmtTime } from '../format.js'

export default function AlertFeed({ alerts }) {
  return (
    <section className="card">
      <div className="card-head">
        <h2>실시간 알림</h2>
        <span className="muted">주문 · 이상거래</span>
      </div>
      {alerts.length === 0 ? (
        <p className="empty">새 알림을 기다리는 중...</p>
      ) : (
        <div className="scroll feed">
          {alerts.map((a, i) => (
            <div key={i} className={`feed-item ${a.type} ${a.level ?? ''}`}>
              <span className="feed-icon">{a.type === 'order' ? '💰' : '⚠️'}</span>
              <span className="feed-msg">{a.message}</span>
              <span className="muted num">{fmtTime(a.timestamp)}</span>
            </div>
          ))}
        </div>
      )}
    </section>
  )
}
