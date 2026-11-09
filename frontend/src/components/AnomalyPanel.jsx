import { fmtNum, fmtTime } from '../format.js'

export default function AnomalyPanel({ anomalies, onSelect }) {
  return (
    <section className="card">
      <div className="card-head">
        <h2>AI 이상거래 탐지</h2>
        <span className="muted">룰 + LOF 모델</span>
      </div>
      {anomalies.length === 0 ? (
        <p className="empty">감지된 이상 징후가 없어요 (모델은 종목별 100건 학습 후 동작)</p>
      ) : (
        <div className="scroll anomaly-list">
          {anomalies.map((a, i) => (
            <div key={`${a.tick_time}-${a.symbol}-${i}`} className={`anomaly ${a.level}`} onClick={() => onSelect(a.symbol)}>
              <div className="anomaly-head">
                <span className={`level ${a.level}`}>{a.level === 'high' ? '높음' : '주의'}</span>
                <b>{a.name}</b>
                <span className="num">{fmtNum(a.price)}</span>
                <span className="muted num right">{fmtTime(a.timestamp)}</span>
              </div>
              <ul>
                {a.reasons.map((r, j) => (
                  <li key={j}>
                    <span className={`method ${r.method}`}>{r.method === 'model' ? 'AI' : '룰'}</span> {r.message}
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
      )}
    </section>
  )
}
