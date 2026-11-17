import { useEffect, useState } from 'react'
import { Area, AreaChart, Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { api } from '../../../api.js'
import { fmtNum, fmtPct, fmtWon, pctClass } from '../../../format.js'
import { RANGES, estimate, maxBuy, periodChange, quickQty } from './trade.js'

const tip = { background: '#151a22', border: '1px solid #2a313d' }
const short = (d) => d?.slice(5) // 2026-11-17 → 11-17

// 선택한 종목: 현재가, 일봉 차트, 주문
export default function StockDetail({ symbol, account, watched, onToggleWatch, onOrder, msg, source }) {
  const [info, setInfo] = useState(null)
  const [bars, setBars] = useState(null)
  const [barsError, setBarsError] = useState(null)
  const [range, setRange] = useState('3M')
  const [side, setSide] = useState('buy')
  const [qty, setQty] = useState(1)

  useEffect(() => {
    let alive = true
    setInfo(null)
    const load = () => api.stock(symbol).then((d) => alive && setInfo(d)).catch(() => {})
    load()
    const id = setInterval(load, 5000)
    return () => {
      alive = false
      clearInterval(id)
    }
  }, [symbol])

  // 일봉: 실패하면 이유를 보여 주고 15초 뒤 다시 시도. 시세 출처가 바뀌면 다시 받기
  useEffect(() => {
    let alive = true
    let timer
    setBars(null)
    setBarsError(null)
    const load = () =>
      api
        .stockDaily(symbol, 130)
        .then((d) => alive && (setBars(d), setBarsError(null)))
        .catch((e) => {
          if (!alive) return
          setBars([])
          setBarsError(e.message.replace(/^"|"$/g, ''))
          timer = setTimeout(load, 15000)
        })
    load()
    return () => {
      alive = false
      clearTimeout(timer)
    }
  }, [symbol, source])

  const held = account?.positions.find((p) => p.symbol === symbol)
  const price = info?.price ?? 0
  const ctx = { cash: account?.cash ?? 0, price, held: held?.quantity ?? 0 }
  const est = estimate(side, price, qty)
  const shown = bars?.slice(-RANGES.find((r) => r.key === range).days) ?? []
  const pc = periodChange(shown)
  const up = (pc ?? 0) >= 0

  if (!info) return <section className="card stock-detail"><p className="empty">종목 정보 불러오는 중...</p></section>

  return (
    <section className="card stock-detail">
      <div className="detail-head">
        <div>
          <div className="detail-name">
            <h2>{info.name}</h2>
            <button className={`star big ${watched ? 'on' : ''}`} onClick={() => onToggleWatch(symbol)} aria-label="관심종목">
              {watched ? '★' : '☆'}
            </button>
            {info.warning && <span className="warn-tag">{info.warning}</span>}
          </div>
          <small className="muted">
            {symbol} · {info.market === 'KOSDAQ' ? '코스닥' : '코스피'} · {info.sector}
          </small>
        </div>
        <div className="detail-price">
          <b className={`num ${pctClass(info.change_pct)}`}>{price ? `${fmtNum(price)}원` : '-'}</b>
          {info.change_pct != null && (
            <span className={`num ${pctClass(info.change_pct)}`}>
              {info.change > 0 ? '▲' : info.change < 0 ? '▼' : ''} {fmtNum(Math.abs(info.change ?? 0))} ({fmtPct(info.change_pct)})
            </span>
          )}
        </div>
      </div>

      {info.open ? (
        <div className="ind-cards four">
          <div className="ind-card"><span>시가</span><b>{fmtNum(info.open)}</b></div>
          <div className="ind-card"><span>고가</span><b className="up">{fmtNum(info.high)}</b></div>
          <div className="ind-card"><span>저가</span><b className="down">{fmtNum(info.low)}</b></div>
          <div className="ind-card"><span>거래량</span><b>{fmtNum(info.volume)}</b></div>
        </div>
      ) : null}

      <div className="card-head chart-head">
        <span className="muted small">
          일봉 차트{pc != null && <> · 기간 수익률 <b className={pctClass(pc)}>{fmtPct(pc)}</b></>}
        </span>
        <div className="seg small-seg">
          {RANGES.map((r) => (
            <button key={r.key} className={range === r.key ? 'on' : ''} onClick={() => setRange(r.key)}>{r.label}</button>
          ))}
        </div>
      </div>
      {bars == null ? (
        <p className="empty">차트 불러오는 중...</p>
      ) : shown.length === 0 ? (
        <p className="empty">
          {barsError ? `${barsError} · 잠시 후 다시 시도해요` : '키움 키가 없어서 차트를 볼 수 없어요 (가상 시세 모드)'}
        </p>
      ) : (
        <>
          <ResponsiveContainer width="100%" height={200}>
            <AreaChart data={shown} margin={{ top: 6, right: 8, left: 0, bottom: 0 }}>
              <defs>
                <linearGradient id="pfill" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor={up ? '#f2555a' : '#4c8ff5'} stopOpacity={0.35} />
                  <stop offset="100%" stopColor={up ? '#f2555a' : '#4c8ff5'} stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid stroke="#252b36" vertical={false} />
              <XAxis dataKey="date" tickFormatter={short} stroke="#6b7685" fontSize={11} minTickGap={30} />
              <YAxis domain={['auto', 'auto']} stroke="#6b7685" fontSize={11} tickFormatter={fmtNum} width={64} />
              <Tooltip contentStyle={tip} formatter={(v) => [`${fmtNum(v)}원`, '종가']} labelFormatter={(d) => d} />
              <Area dataKey="close" stroke={up ? '#f2555a' : '#4c8ff5'} strokeWidth={2} fill="url(#pfill)" isAnimationActive={false} />
            </AreaChart>
          </ResponsiveContainer>
          <ResponsiveContainer width="100%" height={50}>
            <BarChart data={shown} margin={{ top: 0, right: 8, left: 0, bottom: 0 }}>
              <XAxis dataKey="date" hide />
              <YAxis hide />
              <Tooltip contentStyle={tip} formatter={(v) => [fmtNum(v), '거래량']} />
              <Bar dataKey="volume" fill="#3a4250" isAnimationActive={false} />
            </BarChart>
          </ResponsiveContainer>
        </>
      )}

      <div className="order-panel">
        <div className="seg order-side">
          <button className={side === 'buy' ? 'on buy' : ''} onClick={() => setSide('buy')}>매수</button>
          <button className={side === 'sell' ? 'on sell' : ''} onClick={() => setSide('sell')}>매도</button>
        </div>
        <p className="muted small">
          시장가 · 지금 가격으로 바로 체결 · 보유 {fmtNum(ctx.held)}주
          {held && <> (평단 {fmtNum(held.avg_price)}원)</>} · 최대 매수 {fmtNum(maxBuy(ctx.cash, price))}주
        </p>
        <div className="qty-row">
          <input type="number" min={1} value={qty} onChange={(e) => setQty(Math.max(0, Math.floor(Number(e.target.value))))} aria-label="수량" />
          <span>주</span>
          {[0.1, 0.25, 0.5, 1].map((r) => (
            <button key={r} className="chip-btn" onClick={() => setQty(quickQty(side, r, ctx))}>
              {r === 1 ? '최대' : `${r * 100}%`}
            </button>
          ))}
        </div>
        {est && (
          <p className="estimate">
            {side === 'buy' ? '예상 결제 금액' : '예상 받을 금액'} <b className="num">{fmtWon(est.total)}</b>
            <small className="muted"> (주문 {fmtWon(est.amount)} {side === 'buy' ? '+' : '−'} 수수료 {fmtWon(est.fee)})</small>
          </p>
        )}
        <button
          className={`btn ${side === 'buy' ? 'btn-buy' : 'btn-sell'} order-go`}
          disabled={!price || !qty}
          onClick={() => onOrder(symbol, info.name, side, qty)}
        >
          {info.name} {fmtNum(qty)}주 {side === 'buy' ? '매수' : '매도'}
        </button>
        {msg && <p className={msg.ok ? 'msg-ok' : 'msg-err'}>{msg.text}</p>}
      </div>
    </section>
  )
}
