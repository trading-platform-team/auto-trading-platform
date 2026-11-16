import { useCallback, useEffect, useState } from 'react'
import { api } from '../../api.js'
import { fmtNum, fmtPct, fmtTime, fmtWon, pctClass } from '../../format.js'
import { usePolling } from '../../hooks.js'
import { missions } from './engine.js'

// 교육용 가상계좌 연습 매매 (실시간 모의 시세로 시장가 체결)
export default function Practice({ onBadge }) {
  const { data: prices } = usePolling(api.prices, 2000)
  const [account, setAccount] = useState(null)
  const [symbol, setSymbol] = useState('005930')
  const [qty, setQty] = useState(10)
  const [msg, setMsg] = useState(null)

  const load = useCallback(() => api.eduAccount().then(setAccount).catch((e) => setMsg({ ok: false, text: e.message })), [])
  useEffect(() => {
    load()
    const id = setInterval(load, 3000) // 평가금액 갱신
    return () => clearInterval(id)
  }, [load])

  const list = prices ?? []
  const cur = list.find((p) => p.symbol === symbol)
  const held = account?.positions.find((p) => p.symbol === symbol)
  const maxBuy = cur && account ? Math.floor(account.cash / (cur.price * 1.00015)) : 0

  const order = async (side, n = qty) => {
    try {
      const r = await api.eduOrder(symbol, side, n)
      setAccount(r.account)
      const p = r.account.positions.find((x) => x.symbol === symbol)
      let text = `${cur?.name} ${n}주 ${side === 'buy' ? '매수' : '매도'} 체결 @ ${fmtNum(r.price)}원.`
      if (side === 'buy' && p) text += ` 평균 단가는 ${fmtNum(p.avg_price)}원이에요.`
      if (side === 'sell') text += ` 실현손익 ${r.realized_pnl >= 0 ? '+' : ''}${fmtNum(r.realized_pnl)}원 (수수료 포함)`
      setMsg({ ok: true, text })
      if (r.badges?.length) onBadge?.(r.badges)
    } catch (e) {
      setMsg({ ok: false, text: e.message })
    }
  }

  const reset = async () => {
    if (!window.confirm('교육용 계좌를 처음 상태(1,000만 원)로 되돌릴까요? 거래 기록도 지워져요.')) return
    setAccount(await api.eduReset())
    setMsg(null)
  }

  if (!account) return <p className="empty">교육용 계좌 불러오는 중...</p>
  const ms = missions(account)

  return (
    <div className="practice">
      <section className="card">
        <div className="card-head">
          <h2>교육용 계좌</h2>
          <button className="btn btn-ghost" onClick={reset}>초기화</button>
        </div>
        <div className="ind-cards three">
          <div className="ind-card"><span>총 자산</span><b>{fmtWon(account.equity)}</b></div>
          <div className="ind-card"><span>수익률</span><b className={pctClass(account.return_pct)}>{fmtPct(account.return_pct)}</b></div>
          <div className="ind-card"><span>현금</span><b>{fmtWon(account.cash)}</b></div>
        </div>
        <p className="muted small">가상머니 {fmtWon(account.initial_cash)}로 시작 · 모의투자 페이지 계좌와는 별개 · 실시간 모의 시세로 체결 · 수수료 0.015%</p>

        <h4>보유 종목</h4>
        {account.positions.length === 0 ? (
          <p className="empty">아직 보유 종목이 없어요. 아래에서 첫 매수를 해 보세요!</p>
        ) : (
          <table className="table">
            <thead>
              <tr><th>종목</th><th className="r">수량</th><th className="r">평단</th><th className="r">현재가</th><th className="r">평가손익</th></tr>
            </thead>
            <tbody>
              {account.positions.map((p) => (
                <tr key={p.symbol} onClick={() => setSymbol(p.symbol)} className="clickable-row">
                  <td>{p.name}</td>
                  <td className="r num">{p.quantity}</td>
                  <td className="r num">{fmtNum(p.avg_price)}</td>
                  <td className="r num">{fmtNum(p.price)}</td>
                  <td className={`r num ${pctClass(p.pnl)}`}>{p.pnl > 0 ? '+' : ''}{fmtNum(p.pnl)} ({fmtPct(p.return_pct)})</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>

      <div className="practice-side">
        <section className="card">
          <div className="card-head"><h2>주문</h2><span className="muted small">시장가 · 지금 가격으로 바로 체결</span></div>
          <div className="symbol-pick">
            {list.map((p) => (
              <button key={p.symbol} className={`chip-btn ${p.symbol === symbol ? 'on' : ''}`} onClick={() => setSymbol(p.symbol)}>
                {p.name}
              </button>
            ))}
          </div>
          {cur && (
            <div className="quote">
              <b>{cur.name}</b> <span className="num big-price">{fmtNum(cur.price)}원</span>
              <span className="muted small">보유 {held?.quantity ?? 0}주 · 최대 매수 {fmtNum(maxBuy)}주</span>
            </div>
          )}
          <div className="order-box">
            <input type="number" min={1} value={qty} onChange={(e) => setQty(Number(e.target.value))} />
            <button className="btn btn-buy" onClick={() => order('buy')}>매수</button>
            <button className="btn btn-sell" onClick={() => order('sell')}>매도</button>
          </div>
          {msg && <p className={msg.ok ? 'msg-ok' : 'msg-err'}>{msg.text}</p>}
        </section>

        <section className="card">
          <div className="card-head"><h2>연습 미션</h2><span className="muted small">{ms.filter((m) => m.done).length}/{ms.length}</span></div>
          <ul className="missions">
            {ms.map((m) => (
              <li key={m.id} className={m.done ? 'done' : ''}>
                <span className="check">{m.done ? '✓' : ''}</span>
                <div><b>{m.title}</b><p className="muted small">{m.hint}</p></div>
              </li>
            ))}
          </ul>
        </section>

        <section className="card">
          <div className="card-head"><h2>거래 기록</h2></div>
          {account.trades.length === 0 ? <p className="empty">거래 기록이 없어요</p> : (
            <div className="scroll">
              <table className="table">
                <tbody>
                  {account.trades.map((t) => (
                    <tr key={t.id}>
                      <td className="muted num">{fmtTime(t.created_at)}</td>
                      <td>{t.name}</td>
                      <td className={t.side === 'buy' ? 'up' : 'down'}>{t.side === 'buy' ? '매수' : '매도'}</td>
                      <td className="r num">{t.quantity}주</td>
                      <td className="r num">{fmtNum(t.price)}</td>
                      <td className={`r num ${pctClass(t.realized_pnl)}`}>{t.realized_pnl == null ? '' : `${t.realized_pnl > 0 ? '+' : ''}${fmtNum(t.realized_pnl)}`}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>
      </div>
    </div>
  )
}
