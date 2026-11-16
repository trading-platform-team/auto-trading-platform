// 레슨 설명용 그림 (SVG). 국내 관례: 상승 빨강, 하락 파랑
const UP = '#f2555a'
const DOWN = '#4c8ff5'
const MUTED = '#7d8794'
const TEXT = '#e6ebf1'

export function MiniCandles({ data, width = 300, height = 140 }) {
  const highs = data.map((d) => d[1])
  const lows = data.map((d) => d[2])
  const max = Math.max(...highs)
  const min = Math.min(...lows)
  const y = (v) => 8 + ((max - v) / (max - min || 1)) * (height - 16)
  const step = width / data.length
  return (
    <svg viewBox={`0 0 ${width} ${height}`} className="edu-svg" role="img" aria-label="캔들 차트">
      {data.map(([o, h, l, c], i) => {
        const x = step * i + step / 2
        const color = c >= o ? UP : DOWN
        const top = y(Math.max(o, c))
        const bh = Math.max(2, Math.abs(y(o) - y(c)))
        return (
          <g key={i}>
            <line x1={x} x2={x} y1={y(h)} y2={y(l)} stroke={color} strokeWidth="1.5" />
            <rect x={x - step * 0.3} y={top} width={step * 0.6} height={bh} fill={color} rx="1" />
          </g>
        )
      })}
    </svg>
  )
}

function Candle() {
  const one = (x, up) => {
    const color = up ? UP : DOWN
    const [bodyTop, bodyBottom] = [55, 125]
    const labels = up
      ? [['고가', 25], ['종가', bodyTop], ['시가', bodyBottom], ['저가', 155]]
      : [['고가', 25], ['시가', bodyTop], ['종가', bodyBottom], ['저가', 155]]
    return (
      <g>
        <line x1={x} x2={x} y1="25" y2="155" stroke={color} strokeWidth="3" />
        <rect x={x - 22} y={bodyTop} width="44" height={bodyBottom - bodyTop} fill={color} rx="3" />
        {labels.map(([t, yy]) => (
          <g key={t}>
            <line x1={x + 26} x2={x + 44} y1={yy} y2={yy} stroke={MUTED} strokeDasharray="2 2" />
            <text x={x + 48} y={yy + 4} fill={TEXT} fontSize="12">{t}</text>
          </g>
        ))}
        <text x={x} y="178" fill={color} fontSize="13" textAnchor="middle" fontWeight="700">
          {up ? '양봉 (상승)' : '음봉 (하락)'}
        </text>
        <text x={x - 30} y="40" fill={MUTED} fontSize="10" textAnchor="end">윗꼬리</text>
        <text x={x - 30} y="94" fill={MUTED} fontSize="10" textAnchor="end">몸통</text>
        <text x={x - 30} y="145" fill={MUTED} fontSize="10" textAnchor="end">아래꼬리</text>
      </g>
    )
  }
  return (
    <svg viewBox="0 0 360 190" className="edu-svg" role="img" aria-label="양봉과 음봉">
      {one(90, true)}
      {one(250, false)}
    </svg>
  )
}

function OrderBook() {
  const asks = [[72300, 820], [72200, 1540], [72100, 990], [72000, 2310]]
  const bids = [[71900, 1870], [71800, 2650], [71700, 1120], [71600, 760]]
  return (
    <div className="orderbook">
      <div className="ob-title">삼성전자 호가창</div>
      {asks.map(([p, q]) => (
        <div key={p} className="ob-row ask">
          <span className="ob-qty">{q.toLocaleString()}</span>
          <span className="ob-price">{p.toLocaleString()}</span>
          <span />
        </div>
      ))}
      {bids.map(([p, q]) => (
        <div key={p} className="ob-row bid">
          <span />
          <span className="ob-price">{p.toLocaleString()}</span>
          <span className="ob-qty">{q.toLocaleString()}</span>
        </div>
      ))}
      <div className="ob-legend">
        <span className="down">▲ 매도호가 (팔려는 사람)</span>
        <span className="up">▼ 매수호가 (사려는 사람)</span>
      </div>
    </div>
  )
}

function PriceBoard() {
  return (
    <div className="priceboard">
      <div>
        <b>삼성전자</b> <small className="muted">005930</small>
      </div>
      <div className="pb-price up">
        72,000 <small>▲ 1,000 (+1.41%)</small>
      </div>
      <div className="pb-grid">
        <span>시가</span><b>71,200</b>
        <span>고가</span><b className="up">72,500</b>
        <span>저가</span><b className="down">70,900</b>
        <span>종가</span><b>72,000</b>
      </div>
    </div>
  )
}

function Trend() {
  const lines = [
    ['상승', UP, '10,90 40,70 60,80 90,50 110,60 140,25'],
    ['하락', DOWN, '10,20 40,45 60,35 90,65 110,55 140,85'],
    ['횡보', MUTED, '10,55 35,40 60,62 85,42 110,60 140,48'],
  ]
  return (
    <svg viewBox="0 0 480 120" className="edu-svg" role="img" aria-label="추세 종류">
      {lines.map(([t, c, pts], i) => (
        <g key={t} transform={`translate(${i * 160},0)`}>
          <polyline points={pts} fill="none" stroke={c} strokeWidth="3" strokeLinejoin="round" />
          <text x="75" y="112" fill={c} fontSize="13" textAnchor="middle" fontWeight="700">{t}</text>
        </g>
      ))}
    </svg>
  )
}

function Volume() {
  const vols = [30, 34, 28, 32, 30, 35, 29, 33, 110, 60, 38]
  return (
    <svg viewBox="0 0 330 120" className="edu-svg" role="img" aria-label="거래량 막대">
      {vols.map((v, i) => (
        <rect key={i} x={10 + i * 29} y={110 - v * 0.9} width="20" height={v * 0.9} fill={i === 8 ? '#f5a623' : '#3b4454'} rx="2" />
      ))}
      <text x={10 + 8 * 29 + 10} y={110 - 110 * 0.9 - 4} fill="#f5a623" fontSize="11" textAnchor="middle">급증!</text>
    </svg>
  )
}

function MovingAverage() {
  const price = [50, 46, 52, 48, 55, 51, 58, 54, 61, 57, 64, 60, 67, 63, 70]
  const ma = price.map((_, i) => {
    const w = price.slice(Math.max(0, i - 4), i + 1)
    return w.reduce((a, b) => a + b, 0) / w.length
  })
  const pts = (arr) => arr.map((v, i) => `${10 + i * 22},${120 - (v - 40) * 3}`).join(' ')
  return (
    <svg viewBox="0 0 330 130" className="edu-svg" role="img" aria-label="가격과 이동평균선">
      <polyline points={pts(price)} fill="none" stroke={TEXT} strokeWidth="2" />
      <polyline points={pts(ma)} fill="none" stroke="#f5b041" strokeWidth="3" />
      <text x="320" y="20" fill={TEXT} fontSize="11" textAnchor="end">━ 가격</text>
      <text x="320" y="36" fill="#f5b041" fontSize="11" textAnchor="end">━ 5일 이동평균</text>
    </svg>
  )
}

function Emoji({ icons, caption }) {
  return (
    <div className="edu-emoji">
      <div>{icons}</div>
      {caption && <p className="muted small">{caption}</p>}
    </div>
  )
}

function Account() {
  return (
    <div className="priceboard">
      <div><b>내 보유 종목</b></div>
      <div className="pb-grid">
        <span>종목</span><b>삼성전자 20주</b>
        <span>평균 단가</span><b>71,000</b>
        <span>현재가</span><b className="up">75,000</b>
        <span>평가손익</span><b className="up">+80,000 (+5.63%)</b>
      </div>
    </div>
  )
}

const VISUALS = {
  candle: Candle,
  orderbook: OrderBook,
  priceboard: PriceBoard,
  trend: Trend,
  volume: Volume,
  ma: MovingAverage,
  account: Account,
  pizza: () => <Emoji icons="🏢 → 🍕🍕🍕🍕" caption="회사(피자)를 조각(주식)으로 나눠 판다" />,
  ticker: () => <Emoji icons="005930 · 000660 · 035420" caption="삼성전자 · SK하이닉스 · NAVER" />,
  practice: () => <Emoji icons="💰 10,000,000원" caption="교육용 가상머니" />,
}

export default function Visual({ name }) {
  const V = VISUALS[name]
  return V ? <div className="edu-visual"><V /></div> : null
}
