import { useEffect, useState } from 'react'
import { api } from '../../api.js'
import { fmtNum, fmtPct, fmtWon, pctClass, toApiConditions, toFormCondition } from '../../format.js'
import { ConditionList, emptyCond } from '../ConditionEditor.jsx'
import DailyChart, { EquityChart } from './DailyChart.jsx'

function Metric({ label, value, cls = '' }) {
  return (
    <div className="ind-card">
      <span>{label}</span>
      <b className={cls}>{value}</b>
    </div>
  )
}

export default function Backtest({ symbols }) {
  const [presets, setPresets] = useState([])
  const [form, setForm] = useState({
    symbol: symbols[0]?.symbol ?? '005930',
    start: '2024-01-02',
    end: '2025-12-31',
    initial_cash: 10000000,
    take_profit_pct: '',
    stop_loss_pct: '',
    buy: [emptyCond()],
    sell: [{ ...emptyCond(), op: '>', rightValue: 70 }],
  })
  const [result, setResult] = useState(null)
  const [err, setErr] = useState(null)
  const [loading, setLoading] = useState(false)
  const set = (patch) => setForm((f) => ({ ...f, ...patch }))

  useEffect(() => {
    api.backtestPresets().then(setPresets).catch(() => {})
  }, [])

  const applyPreset = (p) =>
    set({ buy: p.buy_conditions.map(toFormCondition), sell: p.sell_conditions.map(toFormCondition) })

  const run = async () => {
    setLoading(true)
    setErr(null)
    try {
      const num = (v) => (v === '' ? null : Number(v))
      setResult(
        await api.backtest({
          symbol: form.symbol,
          start: form.start,
          end: form.end || null,
          initial_cash: Number(form.initial_cash),
          take_profit_pct: num(form.take_profit_pct),
          stop_loss_pct: num(form.stop_loss_pct),
          buy_conditions: toApiConditions(form.buy),
          sell_conditions: toApiConditions(form.sell),
        }),
      )
    } catch (e) {
      setErr(e.message)
    } finally {
      setLoading(false)
    }
  }

  const m = result?.metrics
  const beat = m && m.total_return_pct - m.buy_and_hold_pct

  return (
    <div className="bt-grid">
      <section className="card">
        <div className="card-head">
          <h2>백테스트 설정</h2>
        </div>
        <div className="presets">
          <span className="muted">대표 전략</span>
          {presets.map((p) => (
            <button key={p.id} className="btn btn-ghost" title={p.description} onClick={() => applyPreset(p)}>
              {p.name}
            </button>
          ))}
        </div>
        <div className="strategy-form">
          <div className="form-grid">
            <label>
              종목
              <select value={form.symbol} onChange={(e) => set({ symbol: e.target.value })}>
                {symbols.map((s) => <option key={s.symbol} value={s.symbol}>{s.name}</option>)}
              </select>
            </label>
            <label>
              시작일
              <input type="date" value={form.start} onChange={(e) => set({ start: e.target.value })} />
            </label>
            <label>
              종료일
              <input type="date" value={form.end} onChange={(e) => set({ end: e.target.value })} />
            </label>
            <label>
              초기 자금
              <input type="number" step={1000000} value={form.initial_cash} onChange={(e) => set({ initial_cash: e.target.value })} />
            </label>
            <label>
              익절 %
              <input type="number" placeholder="없음" value={form.take_profit_pct} onChange={(e) => set({ take_profit_pct: e.target.value })} />
            </label>
            <label>
              손절 %
              <input type="number" placeholder="없음" value={form.stop_loss_pct} onChange={(e) => set({ stop_loss_pct: e.target.value })} />
            </label>
          </div>
          <p className="muted small">매수 조건 (모두 만족하면 매수)</p>
          <ConditionList conditions={form.buy} onChange={(buy) => set({ buy })} />
          <p className="muted small">매도 조건 (모두 만족하면 매도)</p>
          <ConditionList conditions={form.sell} onChange={(sell) => set({ sell })} />
          <div className="form-actions">
            <span className="muted small">종가 체결 · 거래비용 0.015%</span>
            <button className="btn btn-primary" onClick={run} disabled={loading}>
              {loading ? '계산 중...' : '백테스트 실행'}
            </button>
          </div>
          {err && <p className="msg-err">{err}</p>}
        </div>
      </section>

      <section className="card">
        <div className="card-head">
          <h2>{result ? `${result.name} 백테스트 결과` : '결과'}</h2>
          {m && (
            <span className={`tag ${beat >= 0 ? 'up' : 'down'}`}>
              단순 보유 대비 {fmtPct(beat)}p
            </span>
          )}
        </div>
        {!result ? (
          <p className="empty">조건을 정하고 백테스트를 실행해 보세요</p>
        ) : (
          <>
            <div className="ind-cards">
              <Metric label="전략 수익률" value={fmtPct(m.total_return_pct)} cls={pctClass(m.total_return_pct)} />
              <Metric label="단순 보유" value={fmtPct(m.buy_and_hold_pct)} cls={pctClass(m.buy_and_hold_pct)} />
              <Metric label="최대 낙폭(MDD)" value={fmtPct(m.max_drawdown_pct)} cls="down" />
              <Metric label="매매 횟수" value={`${m.trades}회`} />
              <Metric label="승률" value={m.win_rate_pct == null ? '-' : `${m.win_rate_pct}%`} />
              <Metric label="최종 자산" value={fmtWon(m.final_equity)} />
            </div>
            <EquityChart rows={result.equity} label="전략 자산" />
            <DailyChart rows={result.chart} points={result.points} height={220} />
            <div className="scroll">
              <table className="table">
                <thead>
                  <tr>
                    <th>매수일</th>
                    <th className="r">매수가</th>
                    <th>매도일</th>
                    <th className="r">매도가</th>
                    <th className="r">수익률</th>
                    <th>사유</th>
                  </tr>
                </thead>
                <tbody>
                  {result.trades.map((t, i) => (
                    <tr key={i}>
                      <td className="num">{t.entry_date}</td>
                      <td className="r num">{fmtNum(t.entry_price)}</td>
                      <td className="num">{t.exit_date ?? '-'}</td>
                      <td className="r num">{fmtNum(t.exit_price)}</td>
                      <td className={`r num ${pctClass(t.return_pct)}`}>{fmtPct(t.return_pct)}</td>
                      <td className="muted">{t.exit_reason}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        )}
      </section>
    </div>
  )
}
