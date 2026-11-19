import { useEffect, useState } from 'react'
import { api } from '../api.js'
import { canUseExit, conditionLabel, exitLabel, PRESETS, toStrategyPayload } from '../format.js'
import { ConditionList, emptyCond, signalCond } from './ConditionEditor.jsx'
import { usePolling } from '../hooks.js'

const PRESET_HELP = ['presetRsiBuy', 'presetGoldenCross', 'presetBollingerBuy', 'presetRsiSell', 'presetDeadCross']

// fixedSymbol: 선택한 종목에만 등록 (주문 영역의 자동매매 탭)
// fixedAccount: 주문 계좌를 고정 ('paper' 가상계좌 | 'kiwoom' 키움 실거래) → 계좌 선택 칸을 숨김
export default function StrategyPanel({ symbols, selected, beginner = false, fixedSymbol = false, fixedAccount = null, disabled = false, selectedName = null }) {
  const [tick, setTick] = useState(0)
  const { data: strategies } = usePolling(api.strategies, 5000, [tick])
  const refresh = () => setTick((t) => t + 1)
  const [msg, setMsg] = useState(null)
  const [form, setForm] = useState({ name: '', symbol: selected, side: 'buy', quantity: 10, cooldown_sec: 60, account: 'paper', take_profit_pct: '', stop_loss_pct: '', conditions: [signalCond()] })
  const set = (patch) => setForm((f) => ({ ...f, ...patch }))
  useEffect(() => {
    if (fixedSymbol) setForm((f) => ({ ...f, symbol: selected }))
  }, [fixedSymbol, selected])
  useEffect(() => {
    if (fixedAccount) setForm((f) => ({ ...f, account: fixedAccount }))
  }, [fixedAccount])

  const applyPreset = (p) => set({ name: p.name, side: p.side, conditions: p.conditions.map((c) => ({ ...emptyCond(), ...c })), symbol: selected })

  const submit = async (e) => {
    e.preventDefault()
    try {
      await api.createStrategy(toStrategyPayload({ ...form, name: form.name || '내 전략' }))
      setMsg({ ok: true, text: form.account === 'kiwoom'
        ? '전략이 등록됐어요. 조건을 만족하면 실거래 설정(서버·한도)으로 키움에 주문합니다.'
        : '전략이 등록됐어요. 조건을 만족하면 자동으로 모의 주문이 실행됩니다.' })
      refresh()
    } catch (err) {
      setMsg({ ok: false, text: `등록 실패: ${err.message}` })
    }
  }

  const toggle = async (s) => {
    const { id, created_at, ...body } = s // eslint-disable-line no-unused-vars
    await api.updateStrategy(id, { ...body, enabled: !s.enabled })
    refresh()
  }
  const remove = async (id) => {
    await api.deleteStrategy(id)
    refresh()
  }
  const list = (strategies ?? []).filter(
    (s) => (!fixedSymbol || s.symbol === selected) && (!fixedAccount || (s.account ?? 'paper') === fixedAccount),
  )
  const nameOf = (code) => symbols.find((s) => s.symbol === code)?.name ?? ((code === selected && selectedName) || code)

  return (
    <section className="card" data-explain={beginner ? 'strategy' : undefined}>
      <div className="card-head">
        <h2>자동매매 전략</h2>
        {fixedSymbol && (
          <span className="muted small">
            {selectedName ?? nameOf(selected)}에 등록{fixedAccount === 'kiwoom' ? ' · 키움 계좌로 실제 주문' : fixedAccount === 'paper' ? ' · 가상계좌 주문' : ''}
          </span>
        )}
      </div>

      <div className="presets">
        <span className="muted">{beginner ? '쉬운 전략 선택' : '빠른 선택'}</span>
        {PRESETS.map((p, i) => (
          <button key={p.name} className="btn btn-ghost" data-explain={beginner ? PRESET_HELP[i] : undefined} onClick={() => applyPreset(p)}>{p.name}</button>
        ))}
      </div>

      <form className="strategy-form" onSubmit={submit}>
        <div className="form-grid">
          <label className="wide" data-explain={beginner ? 'strategyName' : undefined}>이름<input value={form.name} placeholder="내 전략" onChange={(e) => set({ name: e.target.value })} /></label>
          {!fixedSymbol && (
            <label data-explain={beginner ? 'symbol' : undefined}>종목
              <select value={form.symbol} onChange={(e) => set({ symbol: e.target.value })}>
                {symbols.map((s) => <option key={s.symbol} value={s.symbol}>{s.name}</option>)}
              </select>
            </label>
          )}
          <label data-explain={beginner ? 'tradeSide' : undefined}>매매
            <select value={form.side} onChange={(e) => set({ side: e.target.value })}>
              <option value="buy">매수</option>
              <option value="sell">매도</option>
            </select>
          </label>
          <label data-explain={beginner ? 'quantity' : undefined}>수량<input type="number" min={1} value={form.quantity} onChange={(e) => set({ quantity: e.target.value })} /></label>
          <label data-explain={beginner ? 'cooldown' : undefined}>쿨다운(초)<input type="number" min={0} value={form.cooldown_sec} onChange={(e) => set({ cooldown_sec: e.target.value })} /></label>
          {canUseExit(form) && (
            <>
              <label title="평균 단가보다 이만큼 오르면 이 전략이 산 수량을 팔아요">익절(%)
                <input type="number" min={0} step="0.1" placeholder="없음" value={form.take_profit_pct} onChange={(e) => set({ take_profit_pct: e.target.value })} />
              </label>
              <label title="평균 단가보다 이만큼 내리면 이 전략이 산 수량을 팔아요">손절(%)
                <input type="number" min={0} step="0.1" placeholder="없음" value={form.stop_loss_pct} onChange={(e) => set({ stop_loss_pct: e.target.value })} />
              </label>
            </>
          )}
          {!fixedAccount && !beginner && (
            <label>주문 계좌
              <select value={form.account} onChange={(e) => set({ account: e.target.value })}>
                <option value="paper">모의 주문</option>
                <option value="kiwoom">키움 실거래</option>
              </select>
            </label>
          )}
        </div>

        <p className="muted small" data-explain={beginner ? 'condition' : undefined}>조건 (모두 만족하면 주문)</p>
        <div data-explain={beginner ? 'condition' : undefined}><ConditionList conditions={form.conditions} onChange={(conditions) => set({ conditions })} beginner={beginner} /></div>
        <div className="form-actions">
          <span />
          <button type="submit" className="btn btn-primary" disabled={disabled}>전략 등록</button>
        </div>
        {msg && <p className={msg.ok ? 'msg-ok' : 'msg-err'}>{msg.text}</p>}
      </form>

      <div className="strategy-list">
        {list.length === 0 && <p className="empty">{fixedSymbol ? '이 종목에 ' : ''}등록된 전략이 없어요</p>}
        {list.map((s) => (
          <div key={s.id} className={`strategy-item ${s.enabled ? '' : 'off'}`}>
            <div>
              <b>{s.name}</b>{' '}
              <span className={`tag ${s.side === 'buy' ? 'up' : 'down'}`}>{s.side === 'buy' ? '매수' : '매도'}</span>{' '}
              {s.account === 'kiwoom' && <span className="tag warn" title="키움 계좌로 주문">키움</span>}{' '}
              <span className="muted">{nameOf(s.symbol)} · {s.quantity}주{exitLabel(s) && ` · ${exitLabel(s)}`}</span>
              <div className="muted small">{s.conditions.map(conditionLabel).join('  그리고  ')}</div>
            </div>
            <div className="row-actions">
              <button className={`switch ${s.enabled ? 'on' : ''}`} onClick={() => toggle(s)} title={s.enabled ? '끄기' : '켜기'}><i /></button>
              <button className="icon-btn" onClick={() => remove(s.id)} title="삭제">🗑</button>
            </div>
          </div>
        ))}
      </div>
    </section>
  )
}
