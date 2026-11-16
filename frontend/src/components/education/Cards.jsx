import { useEffect, useMemo, useState } from 'react'
import { api } from '../../api.js'
import { checkInput, parseBold } from './engine.js'
import { BuildCard, DeployCard, SliderCard } from './BuildCards.jsx'
import DuelCard from './DuelCard.jsx'
import SpotCard from './SpotCard.jsx'
import Visual, { MiniCandles, MiniLine } from './Visuals.jsx'

export function Rich({ text }) {
  return text.split('\n').map((line, i) => (
    <p key={i}>
      {parseBold(line).map((p, j) => (p.bold ? <b key={j}>{p.text}</b> : <span key={j}>{p.text}</span>))}
    </p>
  ))
}

function shuffle(arr, seed) {
  const a = [...arr]
  let s = seed
  for (let i = a.length - 1; i > 0; i--) {
    s = (s * 9301 + 49297) % 233280
    const j = Math.floor((s / 233280) * (i + 1))
    ;[a[i], a[j]] = [a[j], a[i]]
  }
  return a
}

// 각 카드는 onCheck(result)로 결과를 알린다: true/false/null(채점 없음)
// locked: 이미 채점이 끝나 피드백이 떠 있는 상태

export function ConceptCard({ card }) {
  return (
    <div className="card-body">
      <h3>{card.title}</h3>
      <Visual name={card.visual} />
      <div className="rich">
        <Rich text={card.body} />
      </div>
    </div>
  )
}

export function ChoiceCard({ card, onCheck, locked }) {
  const [sel, setSel] = useState(null)
  return (
    <div className="card-body">
      <h3>{card.q}</h3>
      {card.visual && <Visual name={card.visual} />}
      {card.chart && <div className="edu-visual"><MiniCandles data={card.chart} /></div>}
      {card.chartSeries && <div className="edu-visual"><MiniLine data={card.chartSeries} /></div>}
      <div className="options">
        {card.options.map((o, i) => {
          const state = locked ? (i === card.answer ? 'is-right' : i === sel ? 'is-wrong' : '') : i === sel ? 'is-sel' : ''
          return (
            <button key={i} className={`option ${state}`} disabled={locked} onClick={() => setSel(i)}>
              <span className="opt-key">{i + 1}</span> {o}
            </button>
          )
        })}
      </div>
      {!locked && (
        <button className="btn btn-primary big" disabled={sel === null} onClick={() => onCheck(sel === card.answer)}>
          확인
        </button>
      )}
    </div>
  )
}

export function OXCard({ card, onCheck, locked }) {
  const [sel, setSel] = useState(null)
  const pick = (v) => {
    setSel(v)
    onCheck(v === card.answer)
  }
  return (
    <div className="card-body">
      <h3>{card.q}</h3>
      <div className="ox">
        {[true, false].map((v) => (
          <button
            key={String(v)}
            className={`ox-btn ${v ? 'o' : 'x'} ${locked && v === card.answer ? 'is-right' : ''} ${locked && v === sel && v !== card.answer ? 'is-wrong' : ''}`}
            disabled={locked}
            onClick={() => pick(v)}
          >
            {v ? 'O' : 'X'}
          </button>
        ))}
      </div>
    </div>
  )
}

export function MatchCard({ card, onCheck, locked }) {
  const seed = card.pairs.length * 7 + card.pairs[0][0].length
  const lefts = useMemo(() => shuffle(card.pairs.map((p) => p[0]), seed), [card, seed])
  const rights = useMemo(() => shuffle(card.pairs.map((p) => p[1]), seed + 3), [card, seed])
  const [left, setLeft] = useState(null)
  const [matched, setMatched] = useState([])
  const [miss, setMiss] = useState(false)
  const [flash, setFlash] = useState(null)

  const tryRight = (r) => {
    if (!left) return
    const ok = card.pairs.some(([l, rr]) => l === left && rr === r)
    if (ok) {
      const m = [...matched, left]
      setMatched(m)
      if (m.length === card.pairs.length) onCheck(!miss)
    } else {
      setMiss(true)
      setFlash(r)
      setTimeout(() => setFlash(null), 500)
    }
    setLeft(null)
  }
  const doneRight = (r) => card.pairs.some(([l, rr]) => rr === r && matched.includes(l))

  return (
    <div className="card-body">
      <h3>{card.q}</h3>
      <div className="match-grid">
        <div>
          {lefts.map((l) => (
            <button key={l} className={`option ${matched.includes(l) ? 'is-right' : left === l ? 'is-sel' : ''}`}
              disabled={locked || matched.includes(l)} onClick={() => setLeft(l)}>
              {l}
            </button>
          ))}
        </div>
        <div>
          {rights.map((r) => (
            <button key={r} className={`option ${doneRight(r) ? 'is-right' : flash === r ? 'is-wrong shake' : ''}`}
              disabled={locked || doneRight(r)} onClick={() => tryRight(r)}>
              {r}
            </button>
          ))}
        </div>
      </div>
      {!locked && <p className="muted small">왼쪽 용어를 누르고 맞는 뜻을 눌러요. 한 번이라도 틀리면 하트가 줄어요.</p>}
    </div>
  )
}

export function InputCard({ card, onCheck, locked }) {
  const [v, setV] = useState('')
  return (
    <div className="card-body">
      <h3>{card.q}</h3>
      <div className="input-answer">
        <input inputMode="decimal" value={v} disabled={locked} autoFocus placeholder="숫자 입력"
          onChange={(e) => setV(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && v && !locked && onCheck(checkInput(card, v))} />
        <span>{card.unit}</span>
      </div>
      {locked && <p className="muted">정답: <b>{card.answer.toLocaleString()}{card.unit}</b></p>}
      {!locked && (
        <button className="btn btn-primary big" disabled={!v} onClick={() => onCheck(checkInput(card, v))}>
          확인
        </button>
      )}
    </div>
  )
}

function addDays(iso, n) {
  const d = new Date(iso)
  d.setDate(d.getDate() + n)
  return d.toISOString().slice(0, 10)
}

// 과거 차트로 다음 며칠을 예측하는 게임 (채점하지 않음)
export function PredictCard({ card, onCheck, onPredict, locked }) {
  const [bars, setBars] = useState(null)
  const [guess, setGuess] = useState(null)
  useEffect(() => {
    api.history(card.symbol, addDays(card.date, -70), addDays(card.date, card.days * 2 + 4))
      .then(setBars).catch(() => setBars([]))
  }, [card])

  if (!bars) return <div className="card-body"><h3>{card.q}</h3><p className="muted">차트 불러오는 중...</p></div>
  const cut = bars.findIndex((b) => b.date > card.date)
  if (bars.length === 0 || cut <= 0) {
    return (
      <div className="card-body">
        <h3>{card.q}</h3>
        <p className="muted">과거 시세를 불러오지 못했어요. 건너뛰어도 괜찮아요.</p>
        {!locked && <button className="btn btn-primary big" onClick={() => onCheck(null)}>건너뛰기</button>}
      </div>
    )
  }
  const past = bars.slice(Math.max(0, cut - 30), cut)
  const future = bars.slice(cut, cut + card.days)
  const shown = guess ? [...past, ...future] : past
  const change = ((future.at(-1).close / past.at(-1).close - 1) * 100).toFixed(2)
  const actual = change > 0 ? 'up' : 'down'

  const pick = (g) => {
    setGuess(g)
    onPredict?.({ hit: g === actual, change })
    onCheck(null)
  }
  return (
    <div className="card-body">
      <h3>{card.q}</h3>
      <div className="edu-visual">
        <MiniCandles data={shown.map((b) => [b.open, b.high, b.low, b.close])} width={420} height={160} />
        <p className="muted small">{past[0].date} ~ {guess ? future.at(-1).date : past.at(-1).date} · 가상 과거 시세</p>
      </div>
      {!guess ? (
        <div className="ox">
          <button className="ox-btn o" onClick={() => pick('up')}>📈 오른다</button>
          <button className="ox-btn x" onClick={() => pick('down')}>📉 내린다</button>
        </div>
      ) : null}
    </div>
  )
}

export const CARD_COMPONENTS = {
  concept: ConceptCard,
  choice: ChoiceCard,
  ox: OXCard,
  match: MatchCard,
  input: InputCard,
  predict: PredictCard,
  spot: SpotCard,
  duel: DuelCard,
  slider: SliderCard,
  build: BuildCard,
  deploy: DeployCard,
}
