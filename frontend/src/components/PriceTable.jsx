import { useRef } from 'react'
import { api } from '../api.js'
import { fmtNum } from '../format.js'
import { usePolling } from '../hooks.js'

// 실시간 시세 표. 행을 누르면 차트 종목이 바뀐다.
export default function PriceTable({ selected, onSelect, anomalySymbols, beginner = false }) {
  const { data } = usePolling(api.prices, 1000)
  const prev = useRef({})
  const base = useRef({})
  const prices = data ?? []

  const rows = prices.map((p) => {
    const before = prev.current[p.symbol]
    base.current[p.symbol] ??= p.price
    const dir = before == null || before === p.price ? '' : p.price > before ? 'up' : 'down'
    const chg = ((p.price - base.current[p.symbol]) / base.current[p.symbol]) * 100
    return { ...p, dir, chg }
  })
  prev.current = Object.fromEntries(prices.map((p) => [p.symbol, p.price]))

  return (
    <section className="card" data-explain={beginner ? 'realtimePrice' : undefined}>
      <div className="card-head">
        <h2>실시간 시세</h2>
        <span className="muted">모의 시세 · 1초 갱신</span>
      </div>
      {rows.length === 0 ? (
        <p className="empty">시세 수신 대기 중...</p>
      ) : (
        <table className="table clickable">
          <thead>
            <tr>
              <th>종목</th>
              <th className="r" data-explain={beginner ? 'price' : undefined}>현재가</th>
              <th className="r" data-explain={beginner ? 'change' : undefined}>등락</th>
              <th className="r" data-explain={beginner ? 'volume' : undefined}>거래량</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((p) => (
              <tr key={p.symbol} className={p.symbol === selected ? 'active' : ''} onClick={() => onSelect(p.symbol)}>
                <td>
                  {anomalySymbols.has(p.symbol) && <span className="dot-alert" title="최근 이상거래" />}
                  {p.name} <small className="muted">{p.symbol}</small>
                </td>
                <td className={`r num ${p.dir} flash-${p.dir}`}>{fmtNum(p.price)}</td>
                <td className={`r num ${p.chg > 0 ? 'up' : p.chg < 0 ? 'down' : ''}`}>
                  {p.chg > 0 ? '+' : ''}
                  {p.chg.toFixed(2)}%
                </td>
                <td className="r num muted">{fmtNum(p.volume)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  )
}
