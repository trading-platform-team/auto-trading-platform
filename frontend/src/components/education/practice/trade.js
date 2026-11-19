// 가상계좌 연습 주문 계산 (단위 테스트 대상)

export const FEE_PCT = 0.015 // 백엔드 account.FEE_PCT와 같게

export const fee = (amount) => Math.round((amount * FEE_PCT) / 100)

// 주문 예상 금액: 매수는 (가격×수량 + 수수료)만큼 빠지고, 매도는 (가격×수량 − 수수료)만큼 들어온다
export function estimate(side, price, qty) {
  if (!price || !qty || qty < 1) return null
  const amount = price * qty
  const f = fee(amount)
  return { amount, fee: f, total: side === 'buy' ? amount + f : amount - f }
}

// 현금으로 살 수 있는 최대 수량 (수수료 포함)
export const maxBuy = (cash, price) => (price > 0 ? Math.max(0, Math.floor(cash / (price * (1 + FEE_PCT / 100)))) : 0)

// 비율 버튼(10%·25%·50%·최대): 매수는 현금 기준, 매도는 보유 수량 기준. 최소 1주
export function quickQty(side, ratio, { cash, price, held }) {
  const base = side === 'buy' ? maxBuy(cash, price) : held
  if (!base) return 0
  return Math.max(1, Math.floor(base * ratio))
}

// 차트 기간
export const RANGES = [
  { key: '1M', label: '1개월', days: 22 },
  { key: '3M', label: '3개월', days: 66 },
  { key: '6M', label: '6개월', days: 125 },
]

// 기간 수익률
export function periodChange(bars) {
  if (!bars?.length) return null
  const first = bars[0].close
  const last = bars[bars.length - 1].close
  return first ? ((last - first) / first) * 100 : null
}

// 한국거래소 호가 단위 표 (백엔드 app/edu/orderbook.py와 같게). 호가창 응답에 tick이 오면 그 값을 쓴다
// (실제 분봉 가격으로 정한 단위라 표보다 촘촘할 수 있다)
const TICKS = [[2000, 1], [5000, 5], [20000, 10], [50000, 50], [200000, 100], [500000, 500]]
export function tickSize(price) {
  for (const [limit, tick] of TICKS) if (price < limit) return tick
  return 1000
}

// 호가 n칸 위(+)·아래(−) 가격. tick이 없으면 표를 따라 구간마다 단위를 바꾼다
export function stepPrice(price, n, tick) {
  let p = Math.floor(price)
  if (tick) return Math.max(p + tick * n, tick)
  for (let i = 0; i < Math.abs(n); i += 1) p = n > 0 ? p + tickSize(p) : p > 1 ? p - tickSize(p - 1) : p
  return Math.max(p, 1)
}

export const validPrice = (price, tick) => Number.isInteger(price) && price > 0 && price % (tick || tickSize(price)) === 0
