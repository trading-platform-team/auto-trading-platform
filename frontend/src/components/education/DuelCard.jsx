import { useEffect, useState } from 'react'
import { api } from '../../api.js'
import { fmtPct, pctClass } from '../../format.js'

// 전략 대결: 어떤 전략이 이길지 고르고, 실제 백테스트 결과 공개 (채점 안 함)
export default function DuelCard({ card, onCheck, onPredict, locked }) {
  const [results, setResults] = useState(null)
  const [pick, setPick] = useState(null)
  const [error, setError] = useState(false)

  useEffect(() => {
    let alive = true
    api
      .backtestPresets()
      .then((presets) =>
        Promise.all(
          presets.map((p) =>
            api
              .backtest({ symbol: card.symbol, start: card.start, end: card.end, buy_conditions: p.buy_conditions, sell_conditions: p.sell_conditions })
              .then((r) => ({ id: p.id, name: p.name, description: p.description, ret: r.metrics.total_return_pct, bh: r.metrics.buy_and_hold_pct, trades: r.metrics.trades, mdd: r.metrics.max_drawdown_pct })),
          ),
        ),
      )
      .then((rs) => alive && setResults(rs))
      .catch(() => alive && setError(true))
    return () => {
      alive = false
    }
  }, [card])

  if (error) {
    return (
      <div className="card-body">
        <h3>{card.q}</h3>
        <p className="muted">백테스트를 불러오지 못했어요. 건너뛰어도 괜찮아요.</p>
        {!locked && <button className="btn btn-primary big" onClick={() => onCheck(null)}>건너뛰기</button>}
      </div>
    )
  }
  if (!results) return <div className="card-body"><h3>{card.q}</h3><p className="muted">전략 대결 준비 중... (백테스트 계산)</p></div>

  const best = [...results].sort((a, b) => b.ret - a.ret)[0]
  const bh = results[0].bh
  const choose = (r) => {
    setPick(r.id)
    onPredict?.({
      hit: r.id === best.id,
      text: `1위는 **${best.name}**(${fmtPct(best.ret)})였어요. 같은 기간 그냥 들고만 있었다면 ${fmtPct(bh)}. ${card.lesson}`,
    })
    onCheck(null)
  }
  const max = Math.max(...results.map((r) => Math.abs(r.ret)), Math.abs(bh), 1)

  return (
    <div className="card-body">
      <h3>{card.q}</h3>
      <p className="muted small">{card.name} · {card.start} ~ {card.end} · 가상 과거 시세 · 1,000만 원으로 시작</p>
      <div className="options">
        {results.map((r) => (
          <button key={r.id} className={`option duel ${pick ? (r.id === best.id ? 'is-right' : r.id === pick ? 'is-wrong' : '') : ''}`} disabled={!!pick} onClick={() => choose(r)}>
            <b>{r.name}</b>
            <span className="muted small"> {r.description}</span>
            {pick && (
              <span className="duel-result">
                <span className="rank-bar"><i className={pctClass(r.ret)} style={{ width: `${(Math.abs(r.ret) / max) * 100}%` }} /></span>
                <b className={`num ${pctClass(r.ret)}`}>{fmtPct(r.ret)}</b>
                <span className="muted small num">{r.trades}회 · MDD {fmtPct(r.mdd)}</span>
              </span>
            )}
          </button>
        ))}
        {pick && (
          <div className="option duel bh">
            <b>그냥 들고 있기 (단순 보유)</b>
            <span className="duel-result">
              <span className="rank-bar"><i className={pctClass(bh)} style={{ width: `${(Math.abs(bh) / max) * 100}%` }} /></span>
              <b className={`num ${pctClass(bh)}`}>{fmtPct(bh)}</b>
            </span>
          </div>
        )}
      </div>
    </div>
  )
}
