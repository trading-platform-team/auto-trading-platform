import { useState } from 'react'
import { api } from '../../api.js'
import { conditionLabel, fmtNum, toApiConditions } from '../../format.js'
import { ConditionList, emptyCond } from '../ConditionEditor.jsx'
import { checkSlider, matchStrategy, rewardRisk } from './engine.js'

const SYMBOLS = [
  ['005930', '삼성전자'],
  ['000660', 'SK하이닉스'],
  ['035420', 'NAVER'],
  ['005380', '현대차'],
  ['035720', '카카오'],
]

// ---------- 슬라이더: 손절·익절선 맞추기 ----------
export function SliderCard({ card, onCheck, locked }) {
  const [vals, setVals] = useState(Object.fromEntries(card.fields.map((f) => [f.key, f.start ?? 0])))
  const base = card.base
  const sl = vals.sl ?? 0
  const tp = vals.tp ?? 0
  const rr = rewardRisk(tp, sl)
  const price = (pct) => Math.round(base * (1 + pct / 100))
  // 현재 값에 맞춰 눈금을 조절해서 선이 겹치지 않게 (0% = 가운데)
  const span = Math.max(Math.abs(sl), Math.abs(tp), 4) * 1.25
  const y = (pct) => 50 - (pct / span) * 45

  return (
    <div className="card-body">
      <h3>{card.q}</h3>
      <div className="slider-wrap">
        <div className="ladder">
          <div className="ladder-line entry" style={{ top: `${y(0)}%` }}><span>매수가 {fmtNum(base)}</span></div>
          {'tp' in vals && <div className="ladder-line tp" style={{ top: `${y(tp)}%` }}><span>익절 {fmtNum(price(tp))} (+{tp}%)</span></div>}
          {'sl' in vals && <div className="ladder-line sl" style={{ top: `${y(sl)}%` }}><span>손절 {fmtNum(price(sl))} ({sl}%)</span></div>}
          {'tp' in vals && <div className="ladder-zone win" style={{ top: `${y(tp)}%`, height: `${y(0) - y(tp)}%` }} />}
          {'sl' in vals && <div className="ladder-zone loss" style={{ top: `${y(0)}%`, height: `${y(sl) - y(0)}%` }} />}
        </div>
        <div className="sliders">
          {card.fields.map((f) => (
            <label key={f.key}>
              <span>{f.label} <b className={f.key === 'sl' ? 'down' : 'up'}>{vals[f.key] > 0 ? '+' : ''}{vals[f.key]}%</b></span>
              <input type="range" min={f.min} max={f.max} step={f.step ?? 1} value={vals[f.key]} disabled={locked}
                onChange={(e) => setVals({ ...vals, [f.key]: Number(e.target.value) })} />
            </label>
          ))}
          {'sl' in vals && 'tp' in vals && (
            <div className="rr">손익비 <b>{rr == null ? '-' : `1 : ${rr.toFixed(1)}`}</b></div>
          )}
        </div>
      </div>
      {!locked && <button className="btn btn-primary big" onClick={() => onCheck(checkSlider(card, vals))}>확인</button>}
    </div>
  )
}

// ---------- 전략 만들기: 실제 자동매매 화면과 같은 조건 빌더 ----------
export function BuildCard({ card, onCheck, locked }) {
  const [form, setForm] = useState({ symbol: '005930', side: 'buy', quantity: 1, cooldown_sec: 60, conditions: [emptyCond()] })
  const [problems, setProblems] = useState(null)
  const set = (patch) => setForm((f) => ({ ...f, ...patch }))
  const check = () => {
    const r = matchStrategy(card.target, { ...form, conditions: toApiConditions(form.conditions) })
    setProblems(r.problems)
    onCheck(r.ok)
  }
  const t = card.target

  return (
    <div className="card-body">
      <h3>{card.q}</h3>
      <div className="mission">
        <span className="mission-tag">미션</span> {card.mission}
      </div>
      <div className="strategy-form">
        <div className="form-grid">
          <label>종목
            <select value={form.symbol} disabled={locked} onChange={(e) => set({ symbol: e.target.value })}>
              {SYMBOLS.map(([c, n]) => <option key={c} value={c}>{n}</option>)}
            </select>
          </label>
          <label>매매
            <select value={form.side} disabled={locked} onChange={(e) => set({ side: e.target.value })}>
              <option value="buy">매수</option>
              <option value="sell">매도</option>
            </select>
          </label>
          <label>수량<input type="number" min={1} value={form.quantity} disabled={locked} onChange={(e) => set({ quantity: e.target.value })} /></label>
          <label>쿨다운(초)<input type="number" min={0} value={form.cooldown_sec} disabled={locked} onChange={(e) => set({ cooldown_sec: e.target.value })} /></label>
        </div>
        <p className="muted small">조건 (모두 만족하면 주문)</p>
        <fieldset disabled={locked} className="plain">
          <ConditionList conditions={form.conditions} onChange={(conditions) => set({ conditions })} />
        </fieldset>
      </div>
      {locked && problems?.length > 0 && (
        <div className="answer-box">
          <b>다시 확인할 부분: {problems.join(', ')}</b>
          <p className="muted small">
            정답: {SYMBOLS.find(([c]) => c === t.symbol)?.[1] ?? '아무 종목'} · {t.side === 'buy' ? '매수' : '매도'}
            {t.quantity ? ` · ${t.quantity}주` : ''}{t.cooldown_sec != null ? ` · 쿨다운 ${t.cooldown_sec}초` : ''} · 조건{' '}
            {t.conditions.map(conditionLabel).join(' 그리고 ')}
          </p>
        </div>
      )}
      {!locked && <button className="btn btn-primary big" onClick={check}>확인</button>}
    </div>
  )
}

// ---------- 졸업 미션: 실제 자동매매에 등록 (채점 안 함) ----------
export function DeployCard({ card, onCheck, onPredict, locked }) {
  const [state, setState] = useState(null)
  const s = card.strategy
  const deploy = async () => {
    try {
      await api.createStrategy({ ...s, enabled: true })
      setState('ok')
      onPredict?.({ hit: true, text: '등록 완료! 상단 **실시간 자동매매** 탭의 전략 목록에서 확인할 수 있어요. 조건이 맞으면 모의 주문이 실행되고 실시간 알림이 와요. 언제든 끄거나 삭제할 수 있어요.' })
    } catch (e) {
      setState('err')
      onPredict?.({ hit: false, text: `등록하지 못했어요 (${e.message}). 나중에 실시간 자동매매 화면에서 직접 만들어도 돼요.` })
    }
    onCheck(null)
  }
  const skip = () => {
    setState('skip')
    onPredict?.({ hit: true, text: '나중에 **실시간 자동매매** 화면에서 배운 대로 직접 만들어 보세요!' })
    onCheck(null)
  }
  return (
    <div className="card-body">
      <h3>{card.q}</h3>
      <div className="deploy-box">
        <div className="deploy-title">🎓 {s.name}</div>
        <div className="pb-grid">
          <span>종목</span><b>{SYMBOLS.find(([c]) => c === s.symbol)?.[1]}</b>
          <span>매매</span><b className={s.side === 'buy' ? 'up' : 'down'}>{s.side === 'buy' ? '매수' : '매도'} {s.quantity}주</b>
          <span>조건</span><b>{s.conditions.map(conditionLabel).join(' 그리고 ')}</b>
          <span>쿨다운</span><b>{s.cooldown_sec}초</b>
        </div>
        <p className="muted small">모의투자로만 동작해요. 실제 돈은 쓰이지 않아요.</p>
      </div>
      {!locked && !state && (
        <div className="ox">
          <button className="btn btn-primary big" onClick={deploy}>실시간 자동매매에 등록</button>
          <button className="btn big" onClick={skip}>나중에 할게요</button>
        </div>
      )}
    </div>
  )
}
