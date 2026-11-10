import { useState } from 'react'
import { api } from '../api.js'
import { conditionLabel, PRESETS, toStrategyPayload } from '../format.js'
import { ConditionList, emptyCond } from './ConditionEditor.jsx'
import { usePolling } from '../hooks.js'

export default function StrategyPanel({ symbols, selected }) {
  const [tick, setTick] = useState(0)
  const { data: strategies } = usePolling(api.strategies, 5000, [tick])
  const refresh = () => setTick((t) => t + 1)
  const [msg, setMsg] = useState(null)
  const [form, setForm] = useState({ name: '', symbol: selected, side: 'buy', quantity: 10, cooldown_sec: 60, conditions: [emptyCond()] })
  const set = (patch) => setForm((f) => ({ ...f, ...patch }))

  const applyPreset = (p) => set({ name: p.name, side: p.side, conditions: p.conditions.map((c) => ({ ...emptyCond(), ...c })), symbol: selected })

  const submit = async (e) => {
    e.preventDefault()
    try {
      await api.createStrategy(toStrategyPayload({ ...form, name: form.name || '내 전략' }))
      setMsg({ ok: true, text: '전략이 등록됐어요. 조건을 만족하면 자동으로 모의 주문이 실행됩니다.' })
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
  const nameOf = (code) => symbols.find((s) => s.symbol === code)?.name ?? code

  return (
    <section className="card">
      <div className="card-head">
        <h2>자동매매 전략</h2>
      </div>

      <div className="presets">
        <span className="muted">빠른 선택</span>
        {PRESETS.map((p) => (
          <button key={p.name} className="btn btn-ghost" onClick={() => applyPreset(p)}>{p.name}</button>
        ))}
      </div>

      <form className="strategy-form" onSubmit={submit}>
        <div className="form-grid">
          <label className="wide">이름<input value={form.name} placeholder="내 전략" onChange={(e) => set({ name: e.target.value })} /></label>
          <label>종목
            <select value={form.symbol} onChange={(e) => set({ symbol: e.target.value })}>
              {symbols.map((s) => <option key={s.symbol} value={s.symbol}>{s.name}</option>)}
            </select>
          </label>
          <label>매매
            <select value={form.side} onChange={(e) => set({ side: e.target.value })}>
              <option value="buy">매수</option>
              <option value="sell">매도</option>
            </select>
          </label>
          <label>수량<input type="number" min={1} value={form.quantity} onChange={(e) => set({ quantity: e.target.value })} /></label>
          <label>쿨다운(초)<input type="number" min={0} value={form.cooldown_sec} onChange={(e) => set({ cooldown_sec: e.target.value })} /></label>
        </div>

        <p className="muted small">조건 (모두 만족하면 주문)</p>
        <ConditionList conditions={form.conditions} onChange={(conditions) => set({ conditions })} />
        <div className="form-actions">
          <span />
          <button type="submit" className="btn btn-primary">전략 등록</button>
        </div>
        {msg && <p className={msg.ok ? 'msg-ok' : 'msg-err'}>{msg.text}</p>}
      </form>

      <div className="strategy-list">
        {(strategies ?? []).length === 0 && <p className="empty">등록된 전략이 없어요</p>}
        {(strategies ?? []).map((s) => (
          <div key={s.id} className={`strategy-item ${s.enabled ? '' : 'off'}`}>
            <div>
              <b>{s.name}</b>{' '}
              <span className={`tag ${s.side === 'buy' ? 'up' : 'down'}`}>{s.side === 'buy' ? '매수' : '매도'}</span>{' '}
              <span className="muted">{nameOf(s.symbol)} · {s.quantity}주</span>
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
