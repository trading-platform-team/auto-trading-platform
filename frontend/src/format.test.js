import { describe, it, expect } from 'vitest'
import { conditionLabel, indicatorLabel, PRESETS, speechText, toStrategyPayload } from './format.js'

describe('indicatorLabel', () => {
  it('지표 이름과 기간을 표시한다', () => {
    expect(indicatorLabel({ name: 'RSI', period: 14 })).toBe('RSI(14)')
    expect(indicatorLabel({ name: 'PRICE' })).toBe('현재가')
    expect(indicatorLabel({ name: 'SMA' })).toBe('단순이동평균(20)')
    expect(indicatorLabel(30)).toBe('30')
  })
})

describe('conditionLabel', () => {
  it('조건을 읽기 쉬운 문장으로 만든다', () => {
    const c = { left: { name: 'SMA', period: 5 }, op: 'cross_up', right: { name: 'SMA', period: 20 } }
    expect(conditionLabel(c)).toBe('단순이동평균(5) 상향 돌파 단순이동평균(20)')
  })
})

describe('toStrategyPayload', () => {
  it('폼 상태를 API 형식으로 바꾼다', () => {
    const form = { name: ' 테스트 ', symbol: '005930', side: 'buy', quantity: '10', cooldown_sec: '60', ...PRESETS[1] }
    form.name = ' 테스트 '
    const body = toStrategyPayload(form)
    expect(body.name).toBe('테스트')
    expect(body.quantity).toBe(10)
    expect(body.conditions[0]).toEqual({
      left: { name: 'SMA', period: 5 },
      op: 'cross_up',
      right: { name: 'SMA', period: 20 },
    })
  })

  it('숫자 비교 조건과 현재가(기간 없음)를 처리한다', () => {
    const form = { name: 'x', symbol: '005930', side: 'sell', quantity: 1, cooldown_sec: 0, ...PRESETS[2] }
    form.name = 'x'
    const c = toStrategyPayload(form).conditions[0]
    expect(c.left).toEqual({ name: 'PRICE' })
    const rsi = toStrategyPayload({ ...form, ...PRESETS[0], name: 'y' }).conditions[0]
    expect(rsi.right).toBe(30)
  })
})

describe('speechText', () => {
  it('주문·이상거래 알림을 음성 문장으로 만든다', () => {
    expect(speechText({ type: 'order', message: '[RSI] 삼성전자 10주 매수 @ 70,000원' })).toBe('삼성전자 10주 매수 주문 체결')
    expect(speechText({ type: 'anomaly', name: '카카오' })).toBe('카카오 이상거래 감지')
  })
})
