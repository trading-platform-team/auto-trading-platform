import { useCallback, useEffect, useMemo, useState } from 'react'
import { api } from '../../api.js'
import { fmtNum, fmtPct, fmtWon, pctClass } from '../../format.js'
import AlertFeed from '../AlertFeed.jsx'
import AnomalyPanel from '../AnomalyPanel.jsx'
import ExplainPanel, { useExplain } from '../ExplainPanel.jsx'
import StockBrowser from '../education/practice/StockBrowser.jsx'
import StockDetail from '../education/practice/StockDetail.jsx'
import TradeBox from '../education/practice/TradeBox.jsx'
import '../education/edu.css'
import { KiwoomOrders, SettingsCard } from './KiwoomPanels.jsx'
import { ENV_LABEL, ORDER_RESULT_TEXT, errText, isOpen, keyStatus, lossRatio } from './logic.js'
import './realtrading.css'

// 실거래: 모의투자와 같은 화면 (종목 찾기 | 차트·용어 설명 | 호가창·주문·자동매매)
// 다른 점: 키움 실시간 호가, 키움 계좌로 실제 주문(확인 창), 자동매매 전략은 키움 계좌, 아래에 키움 연결 설정
export default function RealTradingPage({ symbols = [], alerts = [], anomalies = [] }) {
  const [symbol, setSymbol] = useState('005930')
  const [settings, setSettings] = useState(null)
  const [account, setAccount] = useState(null)
  const [accountError, setAccountError] = useState(null)
  const [orders, setOrders] = useState([])
  const [info, setInfo] = useState(null)
  const [watch, setWatch] = useState({ items: [] })
  const [msg, setMsg] = useState(null)
  const [ordersTick, setOrdersTick] = useState(0)
  const explain = useExplain()

  const loadSettings = useCallback(() => api.kwSettings().then(setSettings).catch(() => {}), [])
  const loadAccount = useCallback(
    () =>
      api
        .kwAccount()
        .then((a) => (setAccount(a), setAccountError(null)))
        .catch((e) => (setAccount(null), setAccountError(errText(e)))),
    [],
  )
  const loadOrders = useCallback(() => api.kwOrders(50).then(setOrders).catch(() => {}), [])
  const loadWatch = useCallback(() => api.eduWatchlist().then((items) => setWatch({ items })).catch(() => {}), [])

  useEffect(() => {
    loadSettings()
    loadWatch()
  }, [loadSettings, loadWatch])
  useEffect(() => {
    loadAccount()
    loadOrders()
    const id = setInterval(() => (loadAccount(), loadOrders()), 10000)
    return () => clearInterval(id)
  }, [loadAccount, loadOrders, settings?.env, ordersTick])

  // 종목 정보(이름·시장)는 종목 목록에서, 가격은 실거래 현재가(키움, 없으면 최근 시세)로
  useEffect(() => {
    let alive = true
    setInfo(null)
    const load = async () => {
      const [base, quote] = await Promise.all([
        api.stock(symbol).catch(() => null),
        api.quote(symbol).catch(() => null),
      ])
      if (alive && base) setInfo({ ...base, ...(quote ?? {}), name: base.name, market: base.market, sector: base.sector })
    }
    load()
    const id = setInterval(load, 5000)
    return () => {
      alive = false
      clearInterval(id)
    }
  }, [symbol])

  const toggleWatch = async (code) => {
    const on = watch.items.some((x) => x.symbol === code)
    try {
      setWatch({ items: await (on ? api.eduWatchRemove(code) : api.eduWatchAdd(code)) })
    } catch (e) {
      setMsg({ ok: false, text: errText(e) })
    }
  }

  // TradeBox가 쓰는 계좌 모양으로 맞춘다
  const names = useMemo(() => {
    const m = Object.fromEntries((account?.holdings ?? []).map((h) => [h.symbol, h.name]))
    if (info) m[symbol] = info.name
    return m
  }, [account, info, symbol])
  const tradeAccount = useMemo(
    () => ({
      available_cash: account?.cash.orderable ?? 0,
      positions: (account?.holdings ?? []).map((h) => ({
        symbol: h.symbol, quantity: h.quantity, sellable: h.sellable, avg_price: h.avg_price,
      })),
      open_orders: orders.filter(isOpen).map((o) => ({
        id: o.id, symbol: o.symbol, name: names[o.symbol] ?? o.symbol, side: o.side,
        price: o.price, quantity: o.quantity - (o.filled_qty ?? 0), created_at: o.created_at,
      })),
    }),
    [account, orders, names],
  )

  const guard = (side, qty, price) => {
    if (!settings) return '실거래 설정을 불러오는 중이에요'
    if (keyStatus(settings)?.missing) return keyStatus(settings).missing
    if (!settings.enabled) return '실거래가 꺼져 있어요. 아래 키움 연결 설정에서 먼저 켜세요'
    if (settings.max_order_amount && qty * price > settings.max_order_amount)
      return `1회 주문 한도(${fmtWon(settings.max_order_amount)})를 넘어요`
    return null
  }

  const order = async (code, name, side, n, opts) => {
    const limit = opts.order_type === 'limit'
    const how = limit ? `${fmtNum(opts.price)}원 지정가` : '시장가'
    const word = side === 'buy' ? '매수' : '매도'
    if (!window.confirm(`[${ENV_LABEL[settings.env]}] ${name} ${fmtNum(n)}주 ${how} ${word} 주문을 키움에 보낼까요?`)) return
    try {
      const o = await api.kwOrder({ symbol: code, side, quantity: n, ...(limit ? { price: opts.price } : {}) })
      setMsg({ ok: o.status === 'SUBMITTED', text: `${ORDER_RESULT_TEXT[o.status] ?? o.status}: ${o.message}` })
      setOrdersTick((t) => t + 1)
    } catch (e) {
      setMsg({ ok: false, text: errText(e) })
    }
  }

  const cancel = async (id) => {
    try {
      await api.kwCancel(id)
      setMsg({ ok: true, text: '취소를 요청했어요' })
      setOrdersTick((t) => t + 1)
    } catch (e) {
      setMsg({ ok: false, text: errText(e) })
    }
  }

  const select = (code) => {
    setSymbol(code)
    setMsg(null)
  }

  const liveKiwoom = symbols.some((s) => s.source === 'kiwoom')
  const key = keyStatus(settings)
  const ratio = lossRatio(account?.today, settings?.daily_loss_limit)

  return (
    <main className="paper-main">
      <section className="mode-intro">
        <div>
          <span className="mode-kicker">키움 계좌 연결</span>
          <h2>실거래</h2>
          <p>본인 키움 계좌로 실제 주문이 나가요. 처음에는 모의투자 서버와 작은 한도로 시작하세요.</p>
        </div>
      </section>
      <div className="paper-content practice">
        <div className={`feed-status ${settings?.enabled ? 'real' : 'mock'}`}>
          <span className="dot" />
          {settings ? `${ENV_LABEL[settings.env]} · ${settings.enabled ? '주문 가능' : '실거래 꺼짐'}` : '설정 확인 중...'}
          <span className="muted small">
            {settings?.enabled
              ? ` · 1회 한도 ${fmtWon(settings.max_order_amount)} · 하루 손실 한도 ${fmtWon(settings.daily_loss_limit)}`
              : ' · 아래 키움 연결 설정에서 켜야 주문이 나가요'}
          </span>
          {key && (
            <span className={`key-badge ${key.real ? 'real' : key.text.startsWith('등록된 키:') ? 'mock' : 'none'}`}>
              🔑 {key.text}
            </span>
          )}
        </div>
        {key?.missing && <p className="msg-err key-warn">{key.missing}. 아래 실거래 설정에서 서버를 바꾸거나 키를 등록하세요</p>}

        <section className="card account-bar">
          {account ? (
            <div className="ind-cards five">
              <div className="ind-card"><span>추정 자산</span><b>{fmtWon(account.summary.estimated_assets)}</b></div>
              <div className="ind-card"><span>수익률</span><b className={pctClass(account.summary.total_profit_rate)}>{fmtPct(account.summary.total_profit_rate)}</b></div>
              <div className="ind-card"><span>주문 가능 금액</span><b>{fmtWon(account.cash.orderable)}</b></div>
              <div className="ind-card"><span>주식 평가금액</span><b>{fmtWon(account.summary.total_eval)}</b></div>
              <div className="ind-card">
                <span>오늘 손실</span><b className={account.today?.loss > 0 ? 'down' : ''}>{fmtWon(account.today?.loss ?? 0)}</b>
                {settings?.daily_loss_limit ? <small className="muted">한도의 {Math.round(ratio * 100)}%</small> : null}
              </div>
            </div>
          ) : (
            <p className="empty">{accountError ? `키움 계좌를 불러오지 못했어요: ${accountError}` : '키움 계좌 불러오는 중...'}</p>
          )}
        </section>

        <div className="practice-grid" {...explain.handlers}>
          <StockBrowser selected={symbol} onSelect={select} watch={watch} onToggleWatch={toggleWatch} />
          <StockDetail symbol={symbol} info={info} watched={watch.items.some((x) => x.symbol === symbol)} onToggleWatch={toggleWatch} />
          <ExplainPanel explain={explain} />
          <TradeBox
            symbol={symbol}
            name={info?.name ?? symbol}
            account={tradeAccount}
            onOrder={order}
            onCancel={cancel}
            msg={msg}
            symbols={symbols}
            loadBook={api.kwOrderbook}
            fallbackPrice={info?.price ?? 0}
            guard={guard}
            strategyAccount="kiwoom"
            autoBlock={liveKiwoom ? null : '키움 실시간 시세가 연결돼 있지 않아 실거래 자동매매를 등록할 수 없어요. 실제 돈 주문은 키움 실시간 시세로만 내요'}
          />
        </div>

        <div className="practice-bottom">
          <section className="card">
            <div className="card-head"><h2>보유 종목</h2><span className="muted small">{fmtNum(account?.holdings.length ?? 0)}종목</span></div>
            {!account || account.holdings.length === 0 ? (
              <p className="empty">보유 종목이 없어요</p>
            ) : (
              <div className="scroll">
                <table className="table clickable">
                  <thead>
                    <tr><th>종목</th><th className="r">수량</th><th className="r">평단</th><th className="r">현재가</th><th className="r">평가손익</th></tr>
                  </thead>
                  <tbody>
                    {account.holdings.map((h) => (
                      <tr key={h.symbol} onClick={() => select(h.symbol)} className={h.symbol === symbol ? 'active' : ''}>
                        <td>{h.name}</td>
                        <td className="r num">{fmtNum(h.quantity)}</td>
                        <td className="r num">{fmtNum(h.avg_price)}</td>
                        <td className="r num">{fmtNum(h.price)}</td>
                        <td className={`r num ${pctClass(h.profit)}`}>{h.profit > 0 ? '+' : ''}{fmtNum(h.profit)} ({fmtPct(h.profit_rate)})</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </section>
          <KiwoomOrders refreshKey={ordersTick} />
          <SettingsCard settings={settings} onChange={(s) => (setSettings(s), setOrdersTick((t) => t + 1))} />
        </div>

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
    </main>
  )
}
