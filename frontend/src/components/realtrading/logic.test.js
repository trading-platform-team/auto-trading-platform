import { describe, expect, it } from 'vitest'
import { checkOrder, errText, isOpen, lossRatio, orderAmount, statusInfo, toOrderBody } from './logic.js'

const on = { enabled: true, max_order_amount: 1_000_000 }

describe('주문 금액·검사', () => {
  it('시장가는 현재가, 지정가는 입력 가격으로 계산', () => {
    expect(orderAmount({ quantity: 3, orderType: 'market' }, 70000)).toBe(210000)
    expect(orderAmount({ quantity: 3, orderType: 'limit', price: 69000 }, 70000)).toBe(207000)
  })

  it('입력이 잘못되면 이유를 돌려준다', () => {
    const base = { symbol: '005930', side: 'buy', quantity: 1, orderType: 'market' }
    expect(checkOrder({ ...base, symbol: '' }, 70000, on)).toMatch('종목')
    expect(checkOrder({ ...base, quantity: 0 }, 70000, on)).toMatch('수량')
    expect(checkOrder({ ...base, quantity: 1.5 }, 70000, on)).toMatch('수량')
    expect(checkOrder({ ...base, orderType: 'limit', price: '' }, 70000, on)).toMatch('지정가')
    expect(checkOrder(base, null, on)).toMatch('현재가')
    expect(checkOrder(base, 70000, { ...on, enabled: false })).toMatch('꺼져')
    expect(checkOrder({ ...base, quantity: 20 }, 70000, on)).toMatch('한도')
    expect(checkOrder(base, 70000, on)).toBeNull()
  })

  it('요청 본문: 시장가는 price 없음', () => {
    expect(toOrderBody({ symbol: '005930', side: 'buy', quantity: '2', orderType: 'market', price: 1 })).toEqual({
      symbol: '005930', side: 'buy', quantity: 2,
    })
    expect(toOrderBody({ symbol: '005930', side: 'sell', quantity: 1, orderType: 'limit', price: '71000' }).price).toBe(71000)
  })
})

describe('표시', () => {
  it('상태 라벨과 미체결 여부', () => {
    expect(statusInfo('BLOCKED').label).toBe('차단')
    expect(statusInfo('UNKNOWN').label).toBe('UNKNOWN')
    expect(isOpen({ status: 'PARTIAL' })).toBe(true)
    expect(isOpen({ status: 'FILLED' })).toBe(false)
  })

  it('손실 비율은 0~1', () => {
    expect(lossRatio({ loss: 50000 }, 100000)).toBe(0.5)
    expect(lossRatio({ loss: 500000 }, 100000)).toBe(1)
    expect(lossRatio(null, 100000)).toBe(0)
  })

  it('API 오류 메시지에서 따옴표 제거', () => {
    expect(errText(new Error('"등록된 키움 키가 없습니다"'))).toBe('등록된 키움 키가 없습니다')
    expect(errText(new Error('[{"msg":"too small"}]'))).toBe('too small')
    expect(errText(new Error('500 Internal'))).toBe('500 Internal')
  })
})
