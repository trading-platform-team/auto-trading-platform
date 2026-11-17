import { useEffect, useState } from 'react'
import { api } from '../../api.js'
import { fmtNum, fmtPct, fmtTime, fmtWon, pctClass } from '../../format.js'
import { usePolling } from '../../hooks.js'
import { ENV_LABEL, errText, isOpen, lossRatio, statusInfo } from './logic.js'

// 서버·한도 설정, 확인 문구로 활성화, 긴급 정지
export function SettingsCard({ settings, onChange }) {
  const [form, setForm] = useState(null)
  const [confirm, setConfirm] = useState('')
  const [msg, setMsg] = useState(null)

  useEffect(() => {
    if (settings) setForm({ env: settings.env, max_order_amount: settings.max_order_amount, daily_loss_limit: settings.daily_loss_limit })
  }, [settings])

  if (!settings || !form) return <section className="card"><p className="empty">설정 불러오는 중...</p></section>

  const dirty = form.env !== settings.env || Number(form.max_order_amount) !== settings.max_order_amount ||
    Number(form.daily_loss_limit) !== settings.daily_loss_limit
  const run = async (fn, okText) => {
    try {
      onChange(await fn())
      setMsg({ ok: true, text: okText })
      setConfirm('')
    } catch (e) {
      setMsg({ ok: false, text: errText(e) })
    }
  }
  const save = () =>
    run(() => api.kwSaveSettings({ ...form, max_order_amount: Number(form.max_order_amount), daily_loss_limit: Number(form.daily_loss_limit) }),
      settings.enabled ? '저장했어요. 설정이 바뀌어 실거래가 꺼졌으니 다시 활성화하세요' : '저장했어요')

  return (
    <section className={`card rt-settings ${settings.enabled ? 'on' : ''}`}>
      <div className="card-head">
        <h2>실거래 설정</h2>
        <span className={`rt-pill ${settings.enabled ? (settings.env === 'real' ? 'real' : 'on') : ''}`}>
          {settings.enabled ? '주문 가능' : '꺼짐'}
        </span>
      </div>

      <div className="seg rt-env">
        {['mock', 'real'].map((env) => (
          <button key={env} type="button" className={form.env === env ? 'on' : ''} onClick={() => setForm({ ...form, env })}>
            {ENV_LABEL[env]}
          </button>
        ))}
      </div>
      {form.env === 'real' && <p className="notice rt-warn">실전 서버는 실제 돈으로 거래돼요. 손실이 날 수 있어요</p>}

      <div className="form-grid rt-limits">
        <label>
          1회 주문 한도(원)
          <input type="number" min="10000" step="10000" value={form.max_order_amount}
            onChange={(e) => setForm({ ...form, max_order_amount: e.target.value })} />
        </label>
        <label>
          하루 손실 한도(원)
          <input type="number" min="10000" step="10000" value={form.daily_loss_limit}
            onChange={(e) => setForm({ ...form, daily_loss_limit: e.target.value })} />
        </label>
      </div>
      <p className="muted small">하루 손실이 한도에 닿으면 주문을 막고 실거래를 자동으로 꺼요</p>
      <button className="btn" disabled={!dirty} onClick={save}>설정 저장</button>

      <div className="rt-activate">
        {settings.enabled ? (
          <>
            <p className="small">
              {ENV_LABEL[settings.env]}로 주문할 수 있어요 {settings.activated_at && <span className="muted">({fmtTime(settings.activated_at)} 활성화)</span>}
            </p>
            <button className="btn rt-stop" onClick={() => run(api.kwDeactivate, '실거래를 껐어요')}>
              ⏻ 긴급 정지
            </button>
          </>
        ) : (
          <>
            {settings.disabled_reason && <p className="msg-err">꺼진 이유: {settings.disabled_reason}</p>}
            <p className="small">
              켜려면 아래 문구를 그대로 입력하세요: <b>{settings.confirm_text}</b>
            </p>
            <div className="rt-confirm">
              <input value={confirm} onChange={(e) => setConfirm(e.target.value)} placeholder={settings.confirm_text} />
              <button className="btn btn-primary" disabled={dirty || confirm.trim() !== settings.confirm_text}
                onClick={() => run(() => api.kwActivate(confirm), '실거래를 켰어요')}>
                활성화
              </button>
            </div>
            {dirty && <p className="muted small">설정을 먼저 저장하세요</p>}
          </>
        )}
      </div>
      {msg && <p className={msg.ok ? 'msg-ok' : 'msg-err'}>{msg.text}</p>}
    </section>
  )
}

// 키움 계좌 요약·예수금·오늘 손실·보유 종목
export function AccountCard({ settings }) {
  const { data, error } = usePolling(api.kwAccount, 10000, [settings?.env])
  const ratio = lossRatio(data?.today, settings?.daily_loss_limit)

  return (
    <section className="card">
      <div className="card-head">
        <h2>내 키움 계좌</h2>
        {data && <span className="muted small">{ENV_LABEL[data.env]}</span>}
      </div>
      {error && !data ? (
        <p className="empty">{errText({ message: error })}</p>
      ) : !data ? (
        <p className="empty">계좌 불러오는 중...</p>
      ) : (
        <>
          <div className="rt-stats">
            <Stat label="추정 자산" value={fmtWon(data.summary.estimated_assets)} />
            <Stat label="주문 가능 금액" value={fmtWon(data.cash.orderable)} />
            <Stat label="평가 손익" value={fmtWon(data.summary.total_profit)} cls={pctClass(data.summary.total_profit)} />
            <Stat label="수익률" value={fmtPct(data.summary.total_profit_rate)} cls={pctClass(data.summary.total_profit_rate)} />
          </div>
          <div className="rt-loss">
            <div className="rt-loss-head">
              <span>오늘 손실</span>
              <span className="num">
                {fmtWon(data.today.loss)} / {fmtWon(settings?.daily_loss_limit)}
              </span>
            </div>
            <div className="rt-bar">
              <i style={{ width: `${ratio * 100}%` }} className={ratio >= 0.8 ? 'danger' : ''} />
            </div>
          </div>
          {data.holdings.length === 0 ? (
            <p className="empty small">보유 종목이 없어요</p>
          ) : (
            <div className="scroll">
              <table className="table">
                <thead>
                  <tr>
                    <th>종목</th>
                    <th className="r">수량</th>
                    <th className="r">평균가</th>
                    <th className="r">현재가</th>
                    <th className="r">손익</th>
                  </tr>
                </thead>
                <tbody>
                  {data.holdings.map((h) => (
                    <tr key={h.symbol}>
                      <td>{h.name} <span className="muted small">{h.symbol}</span></td>
                      <td className="r num">{fmtNum(h.quantity)}</td>
                      <td className="r num">{fmtNum(h.avg_price)}</td>
                      <td className="r num">{fmtNum(h.price)}</td>
                      <td className={`r num ${pctClass(h.profit)}`}>
                        {fmtNum(h.profit)} <small>({fmtPct(h.profit_rate)})</small>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </>
      )}
    </section>
  )
}

const Stat = ({ label, value, cls = '' }) => (
  <div className="ind-card">
    <span>{label}</span>
    <b className={cls}>{value}</b>
  </div>
)

// 키움 주문 내역 (자동매매·직접 주문, 체결 동기화 포함)
export function KiwoomOrders({ refreshKey }) {
  const [tick, setTick] = useState(0) // 취소 후 바로 새로고침
  const { data, error } = usePolling(() => api.kwOrders(30), 10000, [refreshKey, tick])
  const [msg, setMsg] = useState(null)
  const orders = data ?? []

  const cancel = async (o) => {
    if (!window.confirm(`${o.symbol} ${o.quantity}주 주문을 취소할까요?`)) return
    try {
      await api.kwCancel(o.id)
      setMsg({ ok: true, text: '취소를 요청했어요' })
      setTick((t) => t + 1)
    } catch (e) {
      setMsg({ ok: false, text: errText(e) })
    }
  }

  return (
    <section className="card">
      <div className="card-head">
        <h2>키움 주문 내역</h2>
        <span className="muted small">10초마다 체결 확인</span>
      </div>
      {msg && <p className={msg.ok ? 'msg-ok' : 'msg-err'}>{msg.text}</p>}
      {error && !data ? (
        <p className="empty">{errText({ message: error })}</p>
      ) : orders.length === 0 ? (
        <p className="empty">아직 주문이 없어요</p>
      ) : (
        <div className="scroll">
          <table className="table">
            <thead>
              <tr>
                <th>시간</th>
                <th>종목</th>
                <th>구분</th>
                <th className="r">수량</th>
                <th className="r">가격</th>
                <th>상태</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {orders.map((o) => {
                const st = statusInfo(o.status)
                return (
                  <tr key={o.id} title={o.message}>
                    <td className="muted num">{fmtTime(o.created_at)}</td>
                    <td>
                      {o.symbol} {o.strategy_name && <span className="tag">{o.strategy_name}</span>}
                    </td>
                    <td className={o.side === 'buy' ? 'up' : 'down'}>{o.side === 'buy' ? '매수' : '매도'}</td>
                    <td className="r num">
                      {o.filled_qty > 0 && o.filled_qty < o.quantity ? `${o.filled_qty}/` : ''}
                      {o.quantity}
                    </td>
                    <td className="r num">
                      {fmtNum(o.filled_price ?? o.price)}
                      {o.order_type === 'market' && !o.filled_price && <small className="muted"> 시장가</small>}
                    </td>
                    <td>
                      <span className={`rt-status ${st.cls}`}>{st.label}</span>
                    </td>
                    <td>{isOpen(o) && <button className="btn btn-ghost" onClick={() => cancel(o)}>취소</button>}</td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}
    </section>
  )
}
