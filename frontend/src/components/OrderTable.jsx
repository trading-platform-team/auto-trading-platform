import { api } from '../api.js'
import { fmtNum, fmtTime } from '../format.js'
import { usePolling } from '../hooks.js'

export default function OrderTable({ beginner = false }) {
  const { data } = usePolling(() => api.orders(30), 2000)
  const orders = data ?? []

  return (
    <section className="card" data-explain={beginner ? 'orders' : undefined}>
      <div className="card-head">
        <h2>모의 주문 내역</h2>
        <span className="muted">최근 {orders.length}건</span>
      </div>
      {orders.length === 0 ? (
        <p className="empty">아직 체결된 주문이 없어요</p>
      ) : (
        <div className="scroll">
          <table className="table">
            <thead>
              <tr>
                <th>시간</th>
                <th>전략</th>
                <th>종목</th>
                <th>구분</th>
                <th className="r">수량</th>
                <th className="r" data-explain={beginner ? 'filledPrice' : undefined}>체결가</th>
              </tr>
            </thead>
            <tbody>
              {orders.map((o) => (
                <tr key={o.id} title={(o.reason?.conditions ?? []).map((c) => `${c.left} ${c.op} ${c.right}: ${c.left_value} / ${c.right_value}`).join('\n')}>
                  <td className="muted num">{fmtTime(o.created_at)}</td>
                  <td>{o.strategy_name}</td>
                  <td>{o.symbol}</td>
                  <td className={o.side === 'buy' ? 'up' : 'down'}>{o.side === 'buy' ? '매수' : '매도'}</td>
                  <td className="r num">{o.quantity}</td>
                  <td className="r num">{fmtNum(o.price)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  )
}
