import { useEffect, useState } from 'react'
import { api } from '../../../api.js'
import { fmtNum, fmtPct, pctClass } from '../../../format.js'
import { RANGES, periodChange } from './trade.js'
import TvChart from './TvChart.jsx'

const CHART_KEY = 'chartKind' // 선/캔들 선택을 이 브라우저에 기억

function loadKind() {
  try {
    return localStorage.getItem(CHART_KEY) === 'candle' ? 'candle' : 'line'
  } catch {
    return 'line'
  }
}

// 선택한 종목: 현재가, 일봉 차트 (주문은 TradeBox)
export default function StockDetail({ symbol, info, watched, onToggleWatch, source }) {
  const [bars, setBars] = useState(null)
  const [barsError, setBarsError] = useState(null)
  const [range, setRange] = useState('3M')
  const [kind, setKind] = useState(loadKind)
  const pickKind = (k) => {
    setKind(k)
    try {
      localStorage.setItem(CHART_KEY, k)
    } catch {
      /* 저장 못 해도 이번 화면에서는 바뀐다 */
    }
  }

  // 일봉: 실패하면 이유를 보여 주고 15초 뒤 다시 시도. 시세 출처가 바뀌면 다시 받기
  useEffect(() => {
    let alive = true
    let timer
    setBars(null)
    setBarsError(null)
    const load = () =>
      api
        .stockDaily(symbol, 250)
        .then((d) => alive && (setBars(d), setBarsError(null)))
        .catch((e) => {
          if (!alive) return
          setBars([])
          setBarsError(e.message.replace(/^"|"$/g, ''))
          timer = setTimeout(load, 15000)
        })
    load()
    return () => {
      alive = false
      clearTimeout(timer)
    }
  }, [symbol, source])

  const price = info?.price ?? 0
  const shown = bars?.slice(-RANGES.find((r) => r.key === range).days) ?? []
  const pc = periodChange(shown)

  if (!info) return <section className="card stock-detail"><p className="empty">종목 정보 불러오는 중...</p></section>

  return (
    <section className="card stock-detail">
      <div className="detail-head">
        <div>
          <div className="detail-name">
            <h2>{info.name}</h2>
            <button className={`star big ${watched ? 'on' : ''}`} onClick={() => onToggleWatch(symbol)} aria-label="관심종목">
              {watched ? '★' : '☆'}
            </button>
            {info.warning && <span className="warn-tag">{info.warning}</span>}
          </div>
          <small className="muted">
            {symbol} · {info.market === 'KOSDAQ' ? '코스닥' : '코스피'} · {info.sector}
          </small>
        </div>
        <div className="detail-price">
          <b className={`num ${pctClass(info.change_pct)}`} data-explain="price">{price ? `${fmtNum(price)}원` : '-'}</b>
          {info.change_pct != null && (
            <span className={`num ${pctClass(info.change_pct)}`} data-explain="change">
              {info.change > 0 ? '▲' : info.change < 0 ? '▼' : ''} {fmtNum(Math.abs(info.change ?? 0))} ({fmtPct(info.change_pct)})
            </span>
          )}
        </div>
      </div>

      {info.open ? (
        <div className="ind-cards four">
          <div className="ind-card"><span>시가</span><b>{fmtNum(info.open)}</b></div>
          <div className="ind-card"><span>고가</span><b className="up">{fmtNum(info.high)}</b></div>
          <div className="ind-card"><span>저가</span><b className="down">{fmtNum(info.low)}</b></div>
          <div className="ind-card" data-explain="volume"><span className="term">거래량</span><b>{fmtNum(info.volume)}</b></div>
        </div>
      ) : null}

      <div className="card-head chart-head">
        <span className="muted small">
          일봉 차트{pc != null && <> · 기간 수익률 <b className={pctClass(pc)}>{fmtPct(pc)}</b></>}
        </span>
        <div className="chart-tools">
        <div className="seg small-seg" role="group" aria-label="차트 종류">
          <button className={kind === 'line' ? 'on' : ''} onClick={() => pickKind('line')}>선</button>
          <button className={kind === 'candle' ? 'on' : ''} onClick={() => pickKind('candle')}>캔들</button>
        </div>
        <div className="seg small-seg">
          {RANGES.map((r) => (
            <button key={r.key} className={range === r.key ? 'on' : ''} onClick={() => setRange(r.key)}>{r.label}</button>
          ))}
        </div>
        </div>
      </div>
      {bars == null ? (
        <p className="empty">차트 불러오는 중...</p>
      ) : shown.length === 0 ? (
        <p className="empty">
          {barsError ? `${barsError} · 잠시 후 다시 시도해요` : '과거 일봉 데이터가 없어요'}
        </p>
      ) : (
        <>
          <TvChart bars={bars} kind={kind} days={RANGES.find((r) => r.key === range).days} />
        </>
      )}

    </section>
  )
}
