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
