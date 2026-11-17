import { describe, expect, it } from 'vitest'
import { estimate, fee, maxBuy, periodChange, quickQty } from './trade.js'

describe('가상계좌 주문 계산', () => {
  it('수수료 0.015%', () => {
    expect(fee(1_000_000)).toBe(150)
  })

  it('매수는 수수료를 더하고 매도는 뺀다', () => {
    expect(estimate('buy', 100_000, 10)).toEqual({ amount: 1_000_000, fee: 150, total: 1_000_150 })
    expect(estimate('sell', 100_000, 10).total).toBe(999_850)
    expect(estimate('buy', 0, 10)).toBeNull()
    expect(estimate('buy', 100, 0)).toBeNull()
  })

  it('최대 매수 수량은 수수료까지 고려', () => {
    expect(maxBuy(10_000_000, 100_000)).toBe(99) // 100주면 수수료 때문에 부족
    expect(maxBuy(10_000_000, 0)).toBe(0)
  })

  it('비율 버튼', () => {
    const ctx = { cash: 10_000_000, price: 100_000, held: 7 }
    expect(quickQty('buy', 0.5, ctx)).toBe(49)
    expect(quickQty('sell', 1, ctx)).toBe(7)
    expect(quickQty('sell', 0.1, ctx)).toBe(1) // 최소 1주
    expect(quickQty('sell', 0.5, { ...ctx, held: 0 })).toBe(0)
  })

  it('기간 수익률', () => {
    expect(periodChange([{ close: 100 }, { close: 110 }])).toBeCloseTo(10)
    expect(periodChange([])).toBeNull()
  })
})
