import {
  Area, CartesianGrid, ComposedChart, Line, LineChart, ReferenceDot, ReferenceLine, ResponsiveContainer, Tooltip, XAxis,
  YAxis,
} from 'recharts'
import { fmtNum } from '../../format.js'

const C = { price: '#e8ecf1', sma5: '#f5b041', sma20: '#5dade2', band: '#8e7cc3', rsi: '#58d68d' }
const tip = { background: '#151a22', border: '1px solid #2a313d' }
const short = (d) => d?.slice(2) // 2024-06-03 → 24-06-03

// 일봉 차트: 종가 + SMA5·SMA20 + 볼린저밴드, 매매 표시, 이상거래 표시, RSI
export default function DailyChart({ rows, points = [], anomalies = [], height = 280 }) {
  const data = rows.map((r) => ({ ...r, band: r.bb_upper && r.bb_lower ? [r.bb_lower, r.bb_upper] : null }))
  const dates = new Set(data.map((r) => r.date))
  const byDate = Object.fromEntries(data.map((r) => [r.date, r]))
  const anomalyDates = [...new Set(anomalies.map((a) => a.timestamp))].filter((d) => dates.has(d))

  return (
    <>
      <div className="legend">
        <span style={{ color: C.price }}>━ 종가</span>
        <span style={{ color: C.sma5 }}>━ SMA5</span>
        <span style={{ color: C.sma20 }}>━ SMA20</span>
        <span style={{ color: C.band }}>▒ 볼린저밴드</span>
        <span className="up">▲ 매수</span>
        <span className="down">▼ 매도</span>
        <span style={{ color: '#f5a623' }}>● AI·룰 이상거래</span>
      </div>
      <ResponsiveContainer width="100%" height={height}>
        <ComposedChart data={data} margin={{ top: 10, right: 8, left: 0, bottom: 0 }}>
          <CartesianGrid stroke="#252b36" />
          <XAxis dataKey="date" tickFormatter={short} stroke="#6b7685" fontSize={11} minTickGap={40} />
          <YAxis domain={['auto', 'auto']} stroke="#6b7685" fontSize={11} tickFormatter={fmtNum} width={70} />
          <Tooltip contentStyle={tip} formatter={(v, k) => [Array.isArray(v) ? v.map(fmtNum).join(' ~ ') : fmtNum(v), k]} />
          <Area dataKey="band" name="볼린저밴드" stroke="none" fill={C.band} fillOpacity={0.15} isAnimationActive={false} />
          <Line dataKey="sma20" name="SMA20" stroke={C.sma20} dot={false} strokeWidth={1.5} isAnimationActive={false} />
          <Line dataKey="sma5" name="SMA5" stroke={C.sma5} dot={false} strokeWidth={1.5} isAnimationActive={false} />
          <Line dataKey="close" name="종가" stroke={C.price} dot={false} strokeWidth={2} isAnimationActive={false} />
          {anomalyDates.map((d) => (
            <ReferenceDot key={`a-${d}`} x={d} y={byDate[d].close} r={6} fill="none" stroke="#f5a623" strokeWidth={2} />
          ))}
          {points
            .filter((p) => dates.has(p.date))
            .map((p, i) => (
              <ReferenceDot
                key={`p-${i}`}
                x={p.date}
                y={p.price}
                r={5}
                fill={p.side === 'buy' ? '#f2555a' : '#4c8ff5'}
                stroke="#0d1117"
                label={{ value: p.side === 'buy' ? '▲' : '▼', position: p.side === 'buy' ? 'bottom' : 'top', fill: p.side === 'buy' ? '#f2555a' : '#4c8ff5', fontSize: 12 }}
              />
            ))}
        </ComposedChart>
      </ResponsiveContainer>
      <ResponsiveContainer width="100%" height={80}>
        <LineChart data={data} margin={{ top: 4, right: 8, left: 0, bottom: 0 }}>
          <XAxis dataKey="date" hide />
          <YAxis domain={[0, 100]} ticks={[30, 70]} stroke="#6b7685" fontSize={11} width={70} />
          <ReferenceLine y={70} stroke="#e74c3c" strokeDasharray="3 3" />
          <ReferenceLine y={30} stroke="#3498db" strokeDasharray="3 3" />
          <Tooltip contentStyle={tip} />
          <Line dataKey="rsi" name="RSI" stroke={C.rsi} dot={false} strokeWidth={1.5} isAnimationActive={false} />
        </LineChart>
      </ResponsiveContainer>
    </>
  )
}

// 자산 곡선: 내 전략 vs 단순 보유
export function EquityChart({ rows, label = '전략' }) {
  return (
    <ResponsiveContainer width="100%" height={200}>
      <LineChart data={rows} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
        <CartesianGrid stroke="#252b36" />
        <XAxis dataKey="date" tickFormatter={short} stroke="#6b7685" fontSize={11} minTickGap={40} />
        <YAxis domain={['auto', 'auto']} stroke="#6b7685" fontSize={11} width={80} tickFormatter={(v) => `${Math.round(v / 10000).toLocaleString()}만`} />
        <Tooltip contentStyle={tip} formatter={(v, k) => [`${fmtNum(v)}원`, k]} />
        <Line dataKey="equity" name={label} stroke="#7c6cf2" dot={false} strokeWidth={2} isAnimationActive={false} />
        <Line dataKey="buy_and_hold" name="단순 보유" stroke="#6b7685" dot={false} strokeDasharray="4 3" isAnimationActive={false} />
      </LineChart>
    </ResponsiveContainer>
  )
}
