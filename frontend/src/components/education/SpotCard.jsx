import { useMemo, useState } from 'react'
import {
  Area, CartesianGrid, ComposedChart, Line, LineChart, ReferenceArea, ReferenceLine, ResponsiveContainer, XAxis, YAxis,
} from 'recharts'
import { bollinger, isHit, rsi, sma, targets } from './indicators.js'

const SHOW_FROM = 19 // 20일선이 생기는 날부터 보여줌

// 차트에서 정답 위치를 직접 누르는 카드
export default function SpotCard({ card, onCheck, locked }) {
  const [pick, setPick] = useState(null)
  const answers = useMemo(() => targets(card.find, card.series), [card])
  const data = useMemo(() => {
    const s5 = sma(card.series, 5)
    const s20 = sma(card.series, 20)
    const r = rsi(card.series)
    const bb = bollinger(card.series)
    return card.series
      .map((c, i) => ({
        i,
        day: `${i + 1}일`,
        close: c,
        sma5: s5[i],
        sma20: s20[i],
        rsi: r[i],
        band: bb[i].lower == null ? null : [bb[i].lower, bb[i].upper],
      }))
      .slice(SHOW_FROM)
  }, [card])

  const showMA = card.find.includes('cross')
  const showBB = card.find.startsWith('bb')
  const showRSI = card.find.startsWith('rsi')
  const choose = (e) => {
    if (locked || e?.activeTooltipIndex == null) return
    setPick(data[e.activeTooltipIndex].i)
  }
  const day = (i) => `${i + 1}일`
  const first = answers[0]
  const last = answers.at(-1)

  return (
    <div className="card-body">
      <h3>{card.q}</h3>
      <div className="spot-chart">
        <div className="legend">
          <span>━ 가격</span>
          {showMA && <><span style={{ color: '#f5b041' }}>━ 5일선</span><span style={{ color: '#5dade2' }}>━ 20일선</span></>}
          {showBB && <span style={{ color: '#8e7cc3' }}>▒ 볼린저밴드</span>}
        </div>
        <ResponsiveContainer width="100%" height={220}>
          <ComposedChart data={data} onClick={choose} margin={{ top: 8, right: 8, left: -20, bottom: 0 }} style={{ cursor: locked ? 'default' : 'crosshair' }}>
            <CartesianGrid stroke="#252b36" />
            <XAxis dataKey="day" stroke="#6b7685" fontSize={11} minTickGap={20} />
            <YAxis domain={['auto', 'auto']} stroke="#6b7685" fontSize={11} />
            {showBB && <Area dataKey="band" stroke="none" fill="#8e7cc3" fillOpacity={0.18} isAnimationActive={false} />}
            {showMA && <Line dataKey="sma20" stroke="#5dade2" dot={false} strokeWidth={2} isAnimationActive={false} />}
            {showMA && <Line dataKey="sma5" stroke="#f5b041" dot={false} strokeWidth={2} isAnimationActive={false} />}
            <Line dataKey="close" stroke="#e6ebf1" dot={{ r: 2 }} strokeWidth={1.5} isAnimationActive={false} />
            {locked && (first === last ? (
              <ReferenceLine x={day(first)} stroke="#2ecc71" strokeWidth={3} label={{ value: '정답', fill: '#2ecc71', fontSize: 12, position: 'top' }} />
            ) : (
              <ReferenceArea x1={day(first)} x2={day(last)} fill="#2ecc71" fillOpacity={0.18} label={{ value: '정답 구간', fill: '#2ecc71', fontSize: 12 }} />
            ))}
            {pick != null && <ReferenceLine x={day(pick)} stroke="#7c6cf2" strokeWidth={2} strokeDasharray="4 3" />}
          </ComposedChart>
        </ResponsiveContainer>
        {showRSI && (
          <ResponsiveContainer width="100%" height={90}>
            <LineChart data={data} onClick={choose} margin={{ top: 4, right: 8, left: -20, bottom: 0 }}>
              <XAxis dataKey="day" hide />
              <YAxis domain={[0, 100]} ticks={[30, 70]} stroke="#6b7685" fontSize={11} />
              <ReferenceLine y={70} stroke="#e74c3c" strokeDasharray="3 3" />
              <ReferenceLine y={30} stroke="#3498db" strokeDasharray="3 3" />
              <Line dataKey="rsi" stroke="#58d68d" dot={false} strokeWidth={2} isAnimationActive={false} />
              {pick != null && <ReferenceLine x={day(pick)} stroke="#7c6cf2" strokeWidth={2} strokeDasharray="4 3" />}
            </LineChart>
          </ResponsiveContainer>
        )}
        <p className="muted small">
          {pick == null ? '차트에서 해당하는 날을 눌러 보세요 👆' : `선택: ${day(pick)}`}
        </p>
      </div>
      {!locked && (
        <button className="btn btn-primary big" disabled={pick == null} onClick={() => onCheck(isHit(pick, answers, card.tolerance ?? 1))}>
          확인
        </button>
      )}
    </div>
  )
}
