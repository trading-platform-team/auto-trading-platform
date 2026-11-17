import { useCallback, useEffect, useState } from 'react'
import { api } from '../../api.js'
import { fmtNum, fmtPct, pctClass } from '../../format.js'
import { usePolling } from '../../hooks.js'
import { AccountCard, KiwoomOrders, SettingsCard } from './KiwoomPanels.jsx'
import { ENV_LABEL, ORDER_RESULT_TEXT, checkOrder, errText, orderAmount, toOrderBody } from './logic.js'
import './realtrading.css'

// 실거래: 사용자 본인 키움 계좌로 주문 (모의투자 서버 또는 실전 서버)
export default function RealTradingPage() {
  const [symbol, setSymbol] = useState({ code: '005930', name: '삼성전자' })
  const [settings, setSettings] = useState(null)
  const [ordersTick, setOrdersTick] = useState(0) // 주문 후 내역 새로고침

  const loadSettings = useCallback(() => api.kwSettings().then(setSettings).catch(() => {}), [])
  useEffect(() => {
    loadSettings()
  }, [loadSettings])

  return (
    <div className="tm-page rt-page">
      <div className="tm-top">
        <h2 className="rt-title">💼 키움 계좌·주문</h2>
        {settings && (
          <span className={`rt-pill ${settings.enabled ? (settings.env === 'real' ? 'real' : 'on') : ''}`}>
            {ENV_LABEL[settings.env]} · {settings.enabled ? '주문 가능' : '꺼짐'}
          </span>
        )}
        <span className="notice">
          본인 키움 계좌로 실제 주문이 나가요. 처음에는 <b>모의투자 서버</b>와 작은 한도로 시작하세요
        </span>
      </div>
      <div className="rt-grid">
        <div className="rt-col">
          <StockSearch onSelect={setSymbol} selected={symbol.code} />
          <QuoteAndOrder symbol={symbol} settings={settings} onOrdered={() => setOrdersTick((t) => t + 1)} />
          <KiwoomOrders refreshKey={ordersTick} />
        </div>
        <div className="rt-col">
          <SettingsCard settings={settings} onChange={setSettings} />
          <AccountCard settings={settings} />
        </div>
      </div>
    </div>
  )
}

function StockSearch({ onSelect, selected }) {
  const [q, setQ] = useState('')
  const [items, setItems] = useState([])
  const [err, setErr] = useState(null)

  useEffect(() => {
    if (!q.trim()) {
      setItems([])
      return
    }
    const id = setTimeout(() => {
      api.stocksSearch(q.trim()).then((r) => (setItems(r.slice(0, 15).map((s) => ({ ...s, code: s.symbol }))), setErr(null))).catch((e) => setErr(errText(e)))
    }, 250) // 입력이 멈추면 검색
    return () => clearTimeout(id)
  }, [q])

  return (
    <section className="card">
      <div className="card-head">
        <h2>종목 검색</h2>
        <span className="muted small">이름 또는 종목코드</span>
      </div>
      <input className="rt-search" value={q} onChange={(e) => setQ(e.target.value)} placeholder="예) 삼성전자, 005930" />
      {err && <p className="msg-err">{err}</p>}
      {items.length > 0 && (
        <ul className="rt-results">
          {items.map((s) => (
            <li key={s.code}>
              <button className={s.code === selected ? 'on' : ''} onClick={() => (onSelect(s), setQ(''))}>
                <span>{s.name}</span>
                <span className="muted num">{s.code}</span>
                <span className="tag">{s.market}</span>
                {s.warning && <span className="tag warn">{s.warning}</span>}
              </button>
            </li>
          ))}
        </ul>
      )}
      {q.trim() && items.length === 0 && !err && <p className="empty small">검색 결과가 없어요</p>}
    </section>
  )
}

const EMPTY_FORM = { side: 'buy', quantity: 1, orderType: 'market', price: '' }

function QuoteAndOrder({ symbol, settings, onOrdered }) {
  // 5초마다 현재가 조회 (조회하면 서버가 이 종목을 실시간 구독 대상으로 유지)
  const { data: quote, error } = usePolling(() => api.quote(symbol.code), 5000, [symbol.code])
  const [form, setForm] = useState(EMPTY_FORM)
  const [msg, setMsg] = useState(null)
  const [busy, setBusy] = useState(false)
  const set = (k, v) => setForm((f) => ({ ...f, [k]: v }))
  const price = quote?.symbol === symbol.code ? quote.price : null

  useEffect(() => {
    setForm(EMPTY_FORM)
    setMsg(null)
  }, [symbol.code])
  useEffect(() => setMsg(null), [settings?.enabled]) // 켜고 끄면 지난 안내 지우기

  const submit = async (e) => {
    e.preventDefault()
    const full = { ...form, symbol: symbol.code }
    const problem = checkOrder(full, price, settings)
    if (problem) return setMsg({ ok: false, text: problem })
    const sideKr = form.side === 'buy' ? '매수' : '매도'
    const how = form.orderType === 'limit' ? `${fmtNum(form.price)}원 지정가` : '시장가'
    const env = ENV_LABEL[settings.env]
    if (!window.confirm(`[${env}] ${symbol.name} ${form.quantity}주 ${how} ${sideKr} 주문을 보낼까요?`)) return
    setBusy(true)
    try {
      const o = await api.kwOrder(toOrderBody(full))
      setMsg({ ok: o.status === 'SUBMITTED', text: `${ORDER_RESULT_TEXT[o.status] ?? o.status}: ${o.message}` })
      onOrdered()
    } catch (err) {
      setMsg({ ok: false, text: errText(err) })
    } finally {
      setBusy(false)
    }
  }

  const amount = orderAmount(form, price)
  return (
    <section className="card">
      <div className="card-head">
        <h2>
          {symbol.name} <span className="muted num small">{symbol.code}</span>
        </h2>
        {quote?.source && <span className="muted small">{quote.source === 'kiwoom' ? '키움 현재가' : '최근 시세'}</span>}
      </div>
      {error && !quote ? (
        <p className="empty">현재가를 불러오지 못했어요 ({errText({ message: error })})</p>
      ) : (
        <div className="rt-quote">
          <b className={`rt-price num ${pctClass(quote?.change_pct)}`}>{fmtNum(price)}원</b>
          {quote?.change_pct != null && <span className={pctClass(quote.change_pct)}>{fmtPct(quote.change_pct)}</span>}
          <dl className="rt-ohlc">
            {[['시가', 'open'], ['고가', 'high'], ['저가', 'low'], ['거래량', 'volume']].map(([label, k]) =>
              quote?.[k] != null ? (
                <div key={k}>
                  <dt>{label}</dt>
                  <dd className="num">{fmtNum(quote[k])}</dd>
                </div>
              ) : null,
            )}
          </dl>
        </div>
      )}

      <form className="rt-order" onSubmit={submit}>
        <div className="seg rt-side">
          <button type="button" className={form.side === 'buy' ? 'on buy' : ''} onClick={() => set('side', 'buy')}>
            매수
          </button>
          <button type="button" className={form.side === 'sell' ? 'on sell' : ''} onClick={() => set('side', 'sell')}>
            매도
          </button>
        </div>
        <div className="form-grid">
          <label>
            주문 방식
            <select value={form.orderType} onChange={(e) => set('orderType', e.target.value)}>
              <option value="market">시장가</option>
              <option value="limit">지정가</option>
            </select>
          </label>
          <label>
            수량(주)
            <input type="number" min="1" step="1" value={form.quantity} onChange={(e) => set('quantity', e.target.value)} />
          </label>
          {form.orderType === 'limit' && (
            <label>
              가격(원)
              <input type="number" min="1" value={form.price} onChange={(e) => set('price', e.target.value)} />
            </label>
          )}
          <label>
            예상 금액
            <output className="num">{amount ? `${fmtNum(amount)}원` : '-'}</output>
          </label>
        </div>
        <button className={`btn btn-primary rt-submit ${form.side}`} disabled={busy}>
          {busy ? '주문 중...' : `${form.side === 'buy' ? '매수' : '매도'} 주문`}
        </button>
        {msg && <p className={msg.ok ? 'msg-ok' : 'msg-err'}>{msg.text}</p>}
      </form>
    </section>
  )
}
