import { describe, expect, it } from 'vitest'
import { LESSONS } from './content/index.js'
import { answer, checkInput, gradedCount, missions, next, parseBold, start } from './engine.js'

describe('레슨 진행', () => {
  it('오답 3번이면 실패', () => {
    let s = start()
    s = answer(s, false)
    s = answer(s, false)
    expect(s.failed).toBe(false)
    s = answer(s, false)
    expect(s.failed).toBe(true)
  })
  it('채점 안 하는 카드는 점수에 영향 없음, 마지막 카드 후 완료', () => {
    let s = answer(start(), null)
    expect(s.correct + s.wrong).toBe(0)
    s = next(next(s, 2), 2)
    expect(s.done).toBe(true)
  })
})

describe('숫자 입력 채점', () => {
  it('쉼표·단위가 있어도 인정, 0.5% 오차 허용', () => {
    expect(checkInput({ answer: 11500 }, '11,500원')).toBe(true)
    expect(checkInput({ answer: 10 }, '10%')).toBe(true)
    expect(checkInput({ answer: 12 }, '13')).toBe(false)
    expect(checkInput({ answer: 5 }, '')).toBe(false)
  })
})

describe('굵게 표시', () => {
  it('**텍스트** 분리', () => {
    expect(parseBold('a **b** c')).toEqual([
      { text: 'a ', bold: false },
      { text: 'b', bold: true },
      { text: ' c', bold: false },
    ])
  })
})

describe('레슨 콘텐츠 검사', () => {
  for (const [id, lesson] of Object.entries(LESSONS)) {
    it(`${id} 카드 형식이 올바름`, () => {
      expect(lesson.cards.length).toBeGreaterThan(2)
      expect(gradedCount(lesson.cards)).toBeGreaterThan(0)
      for (const c of lesson.cards) {
        if (c.type === 'choice') expect(c.answer).toBeLessThan(c.options.length)
        if (c.type === 'ox') expect(typeof c.answer).toBe('boolean')
        if (c.type === 'match') expect(c.pairs.length).toBeGreaterThanOrEqual(3)
        if (c.type === 'input') expect(Number.isFinite(c.answer)).toBe(true)
        if (['choice', 'ox', 'input'].includes(c.type)) expect(c.explain).toBeTruthy()
      }
    })
  }
})

describe('연습 매매 미션', () => {
  it('거래 기록으로 미션 완료 판단', () => {
    const acc = {
      positions: [{ symbol: 'A' }, { symbol: 'B' }],
      trades: [
        { side: 'buy', symbol: 'A' },
        { side: 'buy', symbol: 'A' },
        { side: 'buy', symbol: 'B' },
        { side: 'sell', symbol: 'A', realized_pnl: 500 },
      ],
    }
    expect(missions(acc).every((m) => m.done)).toBe(true)
    expect(missions({ positions: [], trades: [] }).some((m) => m.done)).toBe(false)
  })
})
