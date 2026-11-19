import { useEffect, useState } from 'react'
import { api } from '../api.js'
import { canUseExit, conditionLabel, exitLabel, PRESETS, toStrategyPayload } from '../format.js'
import { ConditionList, emptyCond } from './ConditionEditor.jsx'
import { usePolling } from '../hooks.js'
import SymbolSearch from './SymbolSearch.jsx'

const PRESET_HELP = ['presetRsiBuy', 'presetGoldenCross', 'presetBollingerBuy', 'presetRsiSell']

export default function StrategyPanel({ symbols, selected, beginner = false }) {
  const [tick, setTick] = useState(0)
  const { data: strategies } = usePolling(api.strategies, 5000, [tick])
  const refresh = () => setTick((t) => t + 1)
  const [msg, setMsg] = useState(null)
  const [form, setForm] = useState({ name: '', symbol: selected, side: 'buy', quantity: 10, cooldown_sec: 60, account: 'paper', take_profit_pct: '', stop_loss_pct: '', conditions: [emptyCond()] })
  const set = (patch) => setForm((f) => ({ ...f, ...patch }))
  // 종목명: 시세가 들어오는 종목은 시세 목록에서, 그 밖의 종목은 검색에서 고를 때·/stocks/{code}로 채운다
  const [names, setNames] = useState({})
  const nameOf = (code) => names[code] ?? symbols.find((s) => s.symbol === code)?.name ?? code
  const streaming = (code) => symbols.some((s) => s.symbol === code)

  useEffect(() => {
    const unknown = [...new Set((strategies ?? []).map((s) => s.symbol))].filter(
      (code) => !(code in names) && !symbols.some((s) => s.symbol === code),
    )
    unknown.forEach((code) => {
      setNames((n) => ({ ...n, [code]: code })) // 같은 종목을 두 번 조회하지 않게
      api.stock(code).then((r) => setNames((n) => ({ ...n, [code]: r.name }))).catch(() => {})
    })
  }, [strategies, symbols, names])

  const applyPreset = (p) => set({ name: p.name, side: p.side, conditions: p.conditions.map((c) => ({ ...emptyCond(), ...c })), symbol: selected })

  const submit = async (e) => {
    e.preventDefault()
    try {
      await api.createStrategy(toStrategyPayload({ ...form, name: form.name || '내 전략' }))
      const base = form.account === 'kiwoom'
        ? '전략이 등록됐어요. 조건을 만족하면 실거래 설정(서버·한도)으로 키움에 주문합니다.'
        : '전략이 등록됐어요. 조건을 만족하면 자동으로 모의 주문이 실행됩니다.'
      const warmup = streaming(form.symbol) ? '' : ' 이 종목은 지금부터 시세를 받기 시작해서, 지표를 계산할 만큼 쌓일 때까지(시세 20개쯤) 주문하지 않아요.'
      setMsg({ ok: true, text: base + warmup })
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

  return (
    <section className="card" data-explain={beginner ? 'strategy' : undefined}>
      <div className="card-head">
        <h2>자동매매 전략</h2>
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
          <label data-explain={beginner ? 'symbol' : undefined}>종목
            {beginner ? (
              // 초보자: 시세가 들어오는 종목만 (kis_replay는 기본 종목 분봉만 재생하므로 다른 종목은 주문이 나가지 않음)
              <select value={form.symbol} onChange={(e) => set({ symbol: e.target.value })}>
                {symbols.map((s) => <option key={s.symbol} value={s.symbol}>{s.name}</option>)}
              </select>
            ) : (
              <SymbolSearch
                value={form.symbol}
                name={nameOf(form.symbol)}
                onChange={(symbol, name) => (setNames((n) => ({ ...n, [symbol]: name })), set({ symbol }))}
              />
            )}
          </label>
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
          {!beginner && (
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
