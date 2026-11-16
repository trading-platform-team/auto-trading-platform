import { describe, expect, it } from 'vitest'
import { LESSONS } from './content/index.js'
import { answer, checkInput, checkSlider, gradedCount, matchStrategy, missions, next, parseBold, rewardRisk, start } from './engine.js'
import { targets } from './indicators.js'

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
        if (['choice', 'ox', 'input', 'spot'].includes(c.type)) expect(c.explain).toBeTruthy()
        if (c.type === 'spot') expect(targets(c.find, c.series).length).toBeGreaterThan(0)
        if (c.type === 'duel') expect(c.symbol && c.start && c.end && c.lesson).toBeTruthy()
        if (c.type === 'slider') for (const f of c.fields) expect(f.answer >= f.min && f.answer <= f.max).toBe(true)
        if (c.type === 'build') expect(c.target.conditions.length).toBeGreaterThan(0)
        if (c.type === 'build') expect(matchStrategy(c.target, { ...c.target, cooldown_sec: c.target.cooldown_sec ?? 60 }).ok).toBe(true)
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

describe('리스크 관리 계산', () => {
  it('손익비와 슬라이더 채점', () => {
    expect(rewardRisk(10, -5)).toBe(2)
    const card = { fields: [{ key: 'sl', answer: -5 }, { key: 'tp', answer: 10 }] }
    expect(checkSlider(card, { sl: -5, tp: 10 })).toBe(true)
    expect(checkSlider(card, { sl: -5, tp: 9 })).toBe(false)
  })
})

describe('전략 만들기 채점', () => {
  const target = {
    symbol: '035720', side: 'buy', quantity: 20,
    conditions: [
      { left: { name: 'RSI', period: 14 }, op: '<', right: 30 },
      { left: { name: 'PRICE' }, op: '<', right: { name: 'BB_LOWER', period: 20 } },
    ],
  }
  it('조건 순서가 달라도 같은 전략이면 정답, 폼 값(문자열)도 인정', () => {
    const built = { symbol: '035720', side: 'buy', quantity: '20', cooldown_sec: 60, conditions: [target.conditions[1], { ...target.conditions[0], right: '30' }] }
    built.conditions[1].right = 30
    expect(matchStrategy(target, built).ok).toBe(true)
  })
  it('틀린 부분을 알려줌', () => {
    const built = { symbol: '005930', side: 'buy', quantity: 10, cooldown_sec: 60, conditions: [target.conditions[0]] }
    expect(matchStrategy(target, built).problems).toEqual(['종목', '수량', '조건'])
  })
})
