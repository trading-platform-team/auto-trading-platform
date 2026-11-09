import {
  Area, CartesianGrid, ComposedChart, Line, LineChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from 'recharts'
import { api } from '../api.js'
import { fmtNum, fmtTime } from '../format.js'
import { usePolling } from '../hooks.js'

const C = { price: '#e8ecf1', sma5: '#f5b041', sma20: '#5dade2', band: '#8e7cc3', rsi: '#58d68d' }

function Legend() {
  return (
    <div className="legend">
      <span style={{ color: C.price }}>━ 현재가</span>
      <span style={{ color: C.sma5 }}>━ SMA5</span>
      <span style={{ color: C.sma20 }}>━ SMA20</span>
      <span style={{ color: C.band }}>▒ 볼린저밴드(20,2)</span>
    </div>
  )
}

export default function PriceChart({ symbol, name }) {
  const { data } = usePolling(() => api.chart(symbol, 150), 2000, [symbol])
  const { data: ind } = usePolling(() => api.indicators(symbol), 2000, [symbol])
  const rows = (data ?? []).map((r) => ({ ...r, band: r.bb_upper && r.bb_lower ? [r.bb_lower, r.bb_upper] : null }))

  const cards = [
    ['현재가', fmtNum(ind?.price)],
    ['SMA5', fmtNum(ind?.sma5)],
    ['SMA20', fmtNum(ind?.sma20)],
    ['RSI(14)', ind?.rsi14 ?? '-', ind?.rsi14 > 70 ? 'up' : ind?.rsi14 < 30 ? 'down' : ''],
    ['BB 상단', fmtNum(ind?.bb_upper)],
    ['BB 하단', fmtNum(ind?.bb_lower)],
  ]

  return (
    <section className="card">
      <div className="card-head">
        <h2>
          {name ?? symbol} <small className="muted">{symbol}</small>
        </h2>
        <Legend />
      </div>
      <div className="ind-cards">
        {cards.map(([k, v, cls]) => (
          <div key={k} className="ind-card">
            <span>{k}</span>
            <b className={cls}>{v}</b>
          </div>
        ))}
      </div>
      {rows.length < 2 ? (
        <p className="empty">차트 데이터 수집 중...</p>
      ) : (
        <>
          <ResponsiveContainer width="100%" height={260}>
            <ComposedChart data={rows} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
              <CartesianGrid stroke="#252b36" />
              <XAxis dataKey="timestamp" tickFormatter={fmtTime} stroke="#6b7685" fontSize={11} minTickGap={40} />
              <YAxis domain={['auto', 'auto']} stroke="#6b7685" fontSize={11} tickFormatter={fmtNum} width={70} />
              <Tooltip
                contentStyle={{ background: '#151a22', border: '1px solid #2a313d' }}
                labelFormatter={fmtTime}
                formatter={(v, k) => [Array.isArray(v) ? v.map(fmtNum).join(' ~ ') : fmtNum(v), k]}
              />
              <Area dataKey="band" name="볼린저밴드" stroke="none" fill={C.band} fillOpacity={0.15} isAnimationActive={false} />
              <Line dataKey="sma20" name="SMA20" stroke={C.sma20} dot={false} strokeWidth={1.5} isAnimationActive={false} />
              <Line dataKey="sma5" name="SMA5" stroke={C.sma5} dot={false} strokeWidth={1.5} isAnimationActive={false} />
              <Line dataKey="price" name="현재가" stroke={C.price} dot={false} strokeWidth={2} isAnimationActive={false} />
            </ComposedChart>
          </ResponsiveContainer>
          <ResponsiveContainer width="100%" height={90}>
            <LineChart data={rows} margin={{ top: 4, right: 8, left: 0, bottom: 0 }}>
              <XAxis dataKey="timestamp" hide />
              <YAxis domain={[0, 100]} ticks={[30, 70]} stroke="#6b7685" fontSize={11} width={70} />
              <ReferenceLine y={70} stroke="#e74c3c" strokeDasharray="3 3" />
              <ReferenceLine y={30} stroke="#3498db" strokeDasharray="3 3" />
              <Tooltip contentStyle={{ background: '#151a22', border: '1px solid #2a313d' }} labelFormatter={fmtTime} />
              <Line dataKey="rsi" name="RSI" stroke={C.rsi} dot={false} strokeWidth={1.5} isAnimationActive={false} />
            </LineChart>
          </ResponsiveContainer>
        </>
      )}
    </section>
  )
}
