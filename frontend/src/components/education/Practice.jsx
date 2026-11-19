import { useCallback, useEffect, useRef, useState } from 'react'
import { api } from '../../api.js'
import { fmtNum, fmtPct, fmtTime, fmtWon, pctClass, tradeSource } from '../../format.js'
import AlertFeed from '../AlertFeed.jsx'
import AnomalyPanel from '../AnomalyPanel.jsx'
import ExplainPanel, { useExplain } from '../ExplainPanel.jsx'
import StrategyStats from '../StrategyStats.jsx'
import { missions } from './engine.js'
import StockBrowser from './practice/StockBrowser.jsx'
import StockDetail from './practice/StockDetail.jsx'
import TradeBox from './practice/TradeBox.jsx'

// 가상계좌 모의투자: 종목을 골라 호가창을 보며 지정가·시장가 주문, 같은 화면에서 자동매매 전략 등록
// symbols: 실시간 시세를 받는 종목 (자동매매 전략은 이 종목들에서만 돈다)
// alerts·anomalies: 실시간 알림(자동매매 체결 등)과 AI 이상거래 탐지 결과 (App에서 받아 옴)
export default function Practice({ onBadge, symbols = [], alerts = [], anomalies = [] }) {
  const [account, setAccount] = useState(null)
  const [status, setStatus] = useState(null)
  const [symbol, setSymbol] = useState('005930')
  const [watch, setWatch] = useState({ items: [] })
  const [msg, setMsg] = useState(null)
  const [info, setInfo] = useState(null)
  const explain = useExplain() // 차트·호가창·주문·자동매매의 점선 밑줄 용어 → 차트 아래 패널
  const openIds = useRef(null) // 직전에 본 미체결 주문 (사라지면 체결 알림)

  const applyAccount = useCallback((a) => {
    const prev = openIds.current
    const ids = new Set(a.open_orders.map((o) => o.id))
    if (prev) {
      const gone = [...prev.keys()].filter((id) => !ids.has(id))
      const filled = gone.map((id) => prev.get(id)).filter(Boolean)
      if (filled.length)
        setMsg({ ok: true, text: filled.map((o) => `${o.name} ${fmtNum(o.price)}원 ${fmtNum(o.quantity)}주 ${o.side === 'buy' ? '매수' : '매도'} 지정가 주문이 체결됐어요`).join(' · ') })
    }
    openIds.current = new Map(a.open_orders.map((o) => [o.id, o]))
    setAccount(a)
  }, [])

  // 선택한 종목 현재가·이름 (5초마다)
  useEffect(() => {
    let alive = true
    setInfo(null)
    const loadInfo = () => api.stock(symbol).then((d) => alive && setInfo(d)).catch(() => {})
    loadInfo()
    const id = setInterval(loadInfo, 5000)
    return () => {
      alive = false
      clearInterval(id)
    }
  }, [symbol])

  const [loadError, setLoadError] = useState(null)
  const load = useCallback(
    () =>
      api
        .eduAccount()
        .then((a) => (applyAccount(a), setLoadError(null)))
        .catch((e) => setLoadError(e.message)),
    [applyAccount],
  )
  const loadWatch = useCallback(() => api.eduWatchlist().then((items) => setWatch({ items })).catch(() => {}), [])
  useEffect(() => {
    load()
    loadWatch()
    const loadStatus = () => api.stocksStatus().then(setStatus).catch(() => {})
    loadStatus()
    const id = setInterval(() => {
      load() // 평가금액 갱신, 미체결 지정가 체결 확인
      loadWatch()
      loadStatus()
    }, 5000)
    return () => clearInterval(id)
  }, [load, loadWatch])

  const toggleWatch = async (code) => {
    const on = watch.items.some((x) => x.symbol === code)
    try {
      const items = await (on ? api.eduWatchRemove(code) : api.eduWatchAdd(code))
      setWatch({ items })
    } catch (e) {
      setMsg({ ok: false, text: e.message })
    }
  }

  const forget = (r) => {
    // 내가 방금 바꾼 미체결 목록은 '체결됐어요' 알림 대상이 아니다
    openIds.current = new Map(r.open_orders.map((o) => [o.id, o]))
    setAccount(r)
  }

  const order = async (code, name, side, n, opts = {}) => {
    try {
      const r = await api.eduOrder(code, side, n, opts)
      forget(r.account)
      const word = side === 'buy' ? '매수' : '매도'
      let text
      if (r.status === 'open') {
        text = `${name} ${fmtNum(r.price)}원에 ${fmtNum(n)}주 ${word} 주문을 걸었어요. 가격이 닿으면 체결돼요.`
      } else {
        const p = r.account.positions.find((x) => x.symbol === code)
        text = `${name} ${fmtNum(n)}주 ${word} 체결 @ ${fmtNum(r.price)}원.`
        if (side === 'buy' && p) text += ` 평균 단가는 ${fmtNum(p.avg_price)}원이에요.`
        if (side === 'sell') text += ` 실현손익 ${r.realized_pnl >= 0 ? '+' : ''}${fmtNum(r.realized_pnl)}원 (수수료 포함)`
      }
      setMsg({ ok: true, text })
      if (r.badges?.length) onBadge?.(r.badges)
    } catch (e) {
      setMsg({ ok: false, text: e.message.replace(/^"|"$/g, '') })
    }
  }

  const cancel = async (id) => {
    try {
      forget(await api.eduCancelOrder(id))
      setMsg({ ok: true, text: '미체결 주문을 취소했어요' })
    } catch (e) {
      setMsg({ ok: false, text: e.message.replace(/^"|"$/g, '') })
    }
  }

  const reset = async () => {
    if (!window.confirm('교육용 계좌를 처음 상태(1,000만 원)로 되돌릴까요? 거래 기록, 미체결 주문, 자동매매 모의 주문 내역도 지워져요. 등록한 전략은 그대로예요.')) return
    forget(await api.eduReset())
    setMsg(null)
  }

  const select = (code) => {
    setSymbol(code)
    setMsg(null)
  }

  if (!account)
    return loadError ? (
      <div className="empty">
        <p className="msg-err">교육용 계좌를 불러오지 못했어요: {loadError}</p>
        <button className="btn" onClick={load}>다시 시도</button>
      </div>
    ) : (
      <p className="empty">교육용 계좌 불러오는 중...</p>
    )
  const ms = missions(account)
  const real = status?.source === 'kis_replay' || status?.source === 'public_data' || status?.source === 'kiwoom'

  return (
    <div className="practice">
      <div className={`feed-status ${real ? 'real' : status?.loading ? 'loading' : 'mock'}`}>
        <span className="dot" />
        {status == null
          ? '시세 연결 확인 중...'
          : status?.source === 'kis_replay'
            ? `한국투자 실제 과거 분봉 재생 · 코스피·코스닥 ${fmtNum(status.stocks)}개 종목`
            : status?.source === 'public_data'
            ? `금융위원회 실제 최근 종가 · 코스피·코스닥 ${fmtNum(status.stocks)}개 종목`
            : real
              ? `키움증권 실제 시세 · 코스피·코스닥 ${fmtNum(status.stocks)}개 종목`
            : status.loading
              ? '키움에서 전체 종목 목록을 받는 중이에요 (처음 한 번만, 잠시만 기다려 주세요). 그동안은 가상 시세 5종목'
              : `가상 시세로 연습 중${status.error ? ` (${status.error})` : ''}`}
        {status && (
          <span className="muted small">
            {status.source === 'kis_replay'
              ? ` · ${fmtNum(status.replay_interval_sec)}초마다 다음 1분봉으로 움직여요 · 실제 주문은 나가지 않아요`
              : status.source === 'public_data'
              ? ' · 최근 실제 거래일 종가로 체결돼요'
              : status.market_open ? ' · 장 운영 중 (09:00~15:30)' : ' · 장 마감: 마지막 가격으로 체결돼요'}
          </span>
        )}
      </div>

      <section className="card account-bar">
        <div className="ind-cards five">
          <div className="ind-card"><span>총 자산</span><b>{fmtWon(account.equity)}</b></div>
          <div className="ind-card"><span>수익률</span><b className={pctClass(account.return_pct)}>{fmtPct(account.return_pct)}</b></div>
          <div className="ind-card">
            <span>현금</span><b>{fmtWon(account.cash)}</b>
            {account.available_cash < account.cash && <small className="muted">주문 가능 {fmtWon(account.available_cash)}</small>}
          </div>
          <div className="ind-card"><span>주식 평가금액</span><b>{fmtWon(account.stock_value)}</b></div>
          <div className="ind-card"><span>실현손익</span><b className={pctClass(account.realized_pnl)}>{fmtWon(account.realized_pnl)}</b></div>
        </div>
        <div className="account-foot">
          <p className="muted small">가상머니 {fmtWon(account.initial_cash)}로 시작 · 실제 돈은 쓰이지 않아요 · 수수료 0.015%</p>
          <button className="btn btn-ghost" onClick={reset}>초기화</button>
        </div>
      </section>

      <div className="practice-grid" {...explain.handlers}>
        <StockBrowser selected={symbol} onSelect={select} watch={watch} onToggleWatch={toggleWatch} source={status?.source} />
        <StockDetail
          symbol={symbol}
          info={info}
          watched={watch.items.some((x) => x.symbol === symbol)}
          onToggleWatch={toggleWatch}
          source={status?.source}
        />
        <ExplainPanel explain={explain} />
        <TradeBox
          symbol={symbol}
          name={info?.name ?? symbol}
          account={account}
          onOrder={order}
          onCancel={cancel}
          msg={msg}
          symbols={symbols}
          strategyAccount="paper"
          autoBlock={
            symbols.some((s) => s.symbol === symbol)
              ? null
              : `자동매매는 지금 실시간 시세를 받는 ${fmtNum(symbols.length)}개 종목에서만 돌아요: ${symbols.map((s) => s.name).join(', ')}`
          }
        />
      </div>

      <div className="practice-bottom">
        <section className="card">
          <div className="card-head"><h2>보유 종목</h2><span className="muted small">{account.positions.length}종목</span></div>
          {account.positions.length === 0 ? (
            <p className="empty">아직 보유 종목이 없어요. 종목을 골라 첫 매수를 해 보세요!</p>
          ) : (
            <div className="scroll">
              <table className="table clickable">
                <thead>
                  <tr><th>종목</th><th className="r">수량</th><th className="r">평단</th><th className="r">현재가</th><th className="r">평가손익</th></tr>
                </thead>
                <tbody>
                  {account.positions.map((p) => (
                    <tr key={p.symbol} onClick={() => select(p.symbol)} className={p.symbol === symbol ? 'active' : ''}>
                      <td>{p.name}</td>
                      <td className="r num">{fmtNum(p.quantity)}</td>
                      <td className="r num">{fmtNum(p.avg_price)}</td>
                      <td className="r num">{fmtNum(p.price)}</td>
                      <td className={`r num ${pctClass(p.pnl)}`}>{p.pnl > 0 ? '+' : ''}{fmtNum(p.pnl)} ({fmtPct(p.return_pct)})</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
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
                      <td className="r num">{fmtNum(t.quantity)}주</td>
                      <td className="r num">{fmtNum(t.price)}</td>
                      <td className={`r num ${pctClass(t.realized_pnl)}`}>{t.realized_pnl == null ? '' : `${t.realized_pnl > 0 ? '+' : ''}${fmtNum(t.realized_pnl)}`}</td>
                      <td title={tradeSource(t).title}>{tradeSource(t).auto ? <span className="tag source-tag">{tradeSource(t).label}</span> : <span className="muted small">{tradeSource(t).label}</span>}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>
      </div>

      <StrategyStats stats={account.strategy_stats} />

      <div className="practice-folds">
        <details className="beginner-fold card">
          <summary><span>🔔 실시간 알림</span><small>{alerts.length ? `${fmtNum(alerts.length)}건 · ` : ''}클릭해서 펼치기</small></summary>
          <div className="beginner-fold-body"><AlertFeed alerts={alerts} /></div>
        </details>
        <details className="beginner-fold card">
          <summary><span>⚠️ AI 이상거래 탐지</span><small>{anomalies.length ? `${fmtNum(anomalies.length)}건 · ` : ''}클릭해서 펼치기</small></summary>
          <div className="beginner-fold-body"><AnomalyPanel anomalies={anomalies} onSelect={select} /></div>
        </details>
      </div>
    </div>
  )
}
