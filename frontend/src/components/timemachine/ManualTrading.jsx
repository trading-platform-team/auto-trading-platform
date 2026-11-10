import { useEffect, useRef, useState } from 'react'
import { api } from '../../api.js'
import { fmtNum, fmtPct, fmtWon, pctClass } from '../../format.js'
import DailyChart, { EquityChart } from './DailyChart.jsx'

const SPEEDS = [
  { label: '1일/초', ms: 1000 },
  { label: '2일/초', ms: 500 },
  { label: '5일/초', ms: 200 },
]

function addDays(iso, n) {
  const d = new Date(iso)
  d.setDate(d.getDate() + n)
  return d.toISOString().slice(0, 10)
}

function Setup({ symbols, onStart }) {
  const [symbol, setSymbol] = useState(symbols[0]?.symbol ?? '')
  const info = symbols.find((s) => s.symbol === symbol)
  const min = info ? addDays(info.start, 100) : ''
  const max = info ? addDays(info.end, -40) : ''
  const [date, setDate] = useState('2024-06-03')
  const [cash, setCash] = useState(10000000)
  const [err, setErr] = useState(null)

  const start = async () => {
    try {
      onStart(await api.tmCreate({ symbol, start_date: date, initial_cash: Number(cash) }))
    } catch (e) {
      setErr(e.message)
    }
  }

  return (
    <div className="tm-setup">
      <h3>과거 어느 날로 돌아갈까요?</h3>
      <p className="muted">그날까지의 차트만 보고 직접 매매해 보세요. 미래 시세는 하루씩 지나야 공개됩니다.</p>
      <div className="form-grid">
        <label>
          종목
          <select value={symbol} onChange={(e) => setSymbol(e.target.value)}>
            {symbols.map((s) => <option key={s.symbol} value={s.symbol}>{s.name}</option>)}
          </select>
        </label>
        <label>
          시작일
          <input type="date" value={date} min={min} max={max} onChange={(e) => setDate(e.target.value)} />
        </label>
        <label>
          초기 자금(원)
          <input type="number" step={1000000} value={cash} onChange={(e) => setCash(e.target.value)} />
        </label>
        <label>
          &nbsp;
          <button className="btn btn-primary" onClick={start}>타임머신 출발</button>
        </label>
      </div>
      {err && <p className="msg-err">{err}</p>}
    </div>
  )
}

function Result({ result, onRestart }) {
  const max = Math.max(...result.ranking.map((r) => Math.abs(r.return_pct)), 1)
  return (
    <div className="tm-result">
      <div className="card-head">
        <h3>
          결과: {result.period.start} ~ {result.period.end} ({result.period.days}거래일)
        </h3>
        <button className="btn" onClick={onRestart}>다시 하기</button>
      </div>
      <div className="ranking">
        {result.ranking.map((r, i) => (
          <div key={r.name} className={`rank-row ${r.me ? 'me' : ''}`}>
            <span className="rank">{i + 1}</span>
            <span className="rank-name">{r.name}</span>
            <span className="rank-bar">
              <i className={pctClass(r.return_pct)} style={{ width: `${(Math.abs(r.return_pct) / max) * 100}%` }} />
            </span>
            <b className={`num ${pctClass(r.return_pct)}`}>{fmtPct(r.return_pct)}</b>
            <span className="muted num small">MDD {r.max_drawdown_pct == null ? '-' : fmtPct(r.max_drawdown_pct)} · {r.trades}회</span>
          </div>
        ))}
      </div>
      <EquityChart rows={result.equity} label="나의 자산" />
    </div>
  )
}

export default function ManualTrading({ symbols }) {
  const [view, setView] = useState(null)
  const [result, setResult] = useState(null)
  const [qty, setQty] = useState(10)
  const [playing, setPlaying] = useState(false)
  const [speed, setSpeed] = useState(SPEEDS[0].ms)
  const [msg, setMsg] = useState(null)
  const busy = useRef(false)

  const call = async (fn) => {
    if (busy.current) return
    busy.current = true
    try {
      const v = await fn()
      setView(v)
      setMsg(null)
      if (v.days_left === 0) setPlaying(false)
    } catch (e) {
      setMsg(e.message)
      setPlaying(false)
    } finally {
      busy.current = false
    }
  }
  const step = (days = 1) => call(() => api.tmStep(view.id, days))
  const order = (side, n) => call(() => api.tmOrder(view.id, side, n))

  // 자동 재생
  useEffect(() => {
    if (!playing || !view) return
    const id = setInterval(() => step(1), speed)
    return () => clearInterval(id)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [playing, speed, view?.id])

  const finish = async () => {
    setPlaying(false)
    setResult(await api.tmFinish(view.id))
  }
  const restart = () => {
    setView(null)
    setResult(null)
  }

  if (!view) return <Setup symbols={symbols} onStart={setView} />
  if (result) return <Result result={result} onRestart={restart} />

  const a = view.account
  const maxBuy = Math.floor(a.cash / (view.price * 1.00015))
  const points = view.trades.map((t) => ({ date: t.date, side: t.side, price: t.price }))

  return (
    <div className="tm-play">
      <div className="tm-bar">
        <div>
          <span className="tm-date num">{view.date}</span>
          <span className="muted">
            {' '}
            {view.name} · D+{view.days_passed} · 남은 거래일 {view.days_left}
          </span>
        </div>
        <div className="tm-controls">
          <button className="btn" onClick={() => setPlaying((p) => !p)} disabled={view.days_left === 0}>
            {playing ? '⏸ 일시정지' : '▶ 재생'}
          </button>
          <select value={speed} onChange={(e) => setSpeed(Number(e.target.value))}>
            {SPEEDS.map((s) => <option key={s.ms} value={s.ms}>{s.label}</option>)}
          </select>
          <button className="btn" onClick={() => step(1)} disabled={playing || view.days_left === 0}>다음 날 ›</button>
          <button className="btn" onClick={() => step(5)} disabled={playing || view.days_left === 0}>+5일 »</button>
          <button className="btn btn-primary" onClick={finish}>종료하고 결과 보기</button>
        </div>
      </div>

      <div className="tm-grid">
        <section className="card">
          <DailyChart rows={view.chart} points={points} anomalies={view.anomalies} />
        </section>

        <div className="tm-side">
          <section className="card">
            <div className="card-head">
              <h2>내 계좌</h2>
              <b className={`num ${pctClass(a.return_pct)}`}>{fmtPct(a.return_pct)}</b>
            </div>
            <div className="kv">
              <span>평가 자산</span><b className="num">{fmtWon(a.equity)}</b>
              <span>현금</span><b className="num">{fmtWon(a.cash)}</b>
              <span>보유</span>
              <b className="num">
                {a.qty}주 {a.qty > 0 && <small className={pctClass(a.unrealized_pct)}>({fmtPct(a.unrealized_pct)})</small>}
              </b>
              <span>평균 단가</span><b className="num">{a.qty ? fmtWon(a.avg_price) : '-'}</b>
              <span>오늘 종가</span><b className="num">{fmtWon(view.price)}</b>
            </div>
          </section>

          <section className="card">
            <div className="card-head">
              <h2>주문</h2>
              <span className="muted small">오늘 종가로 체결</span>
            </div>
            <div className="order-box">
              <input type="number" min={1} value={qty} onChange={(e) => setQty(Number(e.target.value))} />
              <button className="btn btn-buy" onClick={() => order('buy', qty)}>매수</button>
              <button className="btn btn-sell" onClick={() => order('sell', qty)}>매도</button>
            </div>
            <div className="order-box">
              <button className="btn btn-ghost" onClick={() => maxBuy > 0 && order('buy', maxBuy)}>최대 매수 ({fmtNum(maxBuy)}주)</button>
              <button className="btn btn-ghost" onClick={() => a.qty > 0 && order('sell', a.qty)}>전량 매도</button>
            </div>
            {msg && <p className="msg-err">{msg}</p>}
          </section>

          <section className="card">
            <div className="card-head">
              <h2>매매 기록</h2>
            </div>
            {view.trades.length === 0 ? (
              <p className="empty">아직 매매 기록이 없어요</p>
            ) : (
              <div className="scroll">
                <table className="table">
                  <tbody>
                    {[...view.trades].reverse().map((t, i) => (
                      <tr key={i}>
                        <td className="muted num">{t.date}</td>
                        <td className={t.side === 'buy' ? 'up' : 'down'}>{t.side === 'buy' ? '매수' : '매도'}</td>
                        <td className="r num">{t.quantity}주</td>
                        <td className="r num">{fmtNum(t.price)}</td>
                        <td className={`r num ${pctClass(t.return_pct)}`}>{t.return_pct == null ? '' : fmtPct(t.return_pct)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </section>
        </div>
      </div>
    </div>
  )
}
