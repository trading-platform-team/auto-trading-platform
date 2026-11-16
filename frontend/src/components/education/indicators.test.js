import { describe, expect, it } from 'vitest'
import { BB_BREAK, CHOPPY, DEAD, GOLDEN, RSI_DROP } from './content/series.js'
import { bollinger, crosses, isHit, rsi, sma, targets } from './indicators.js'

describe('지표 계산', () => {
  it('SMA', () => {
    expect(sma([1, 2, 3, 4, 5], 5)[4]).toBe(3)
    expect(sma([1, 2, 3], 5)[2]).toBe(null)
  })
  it('RSI: 계속 오르면 100, 계속 내리면 0', () => {
    const up = Array.from({ length: 30 }, (_, i) => 100 + i)
    expect(rsi(up).at(-1)).toBe(100)
    expect(rsi([...up].reverse()).at(-1)).toBeCloseTo(0)
  })
  it('볼린저: 상단 > 중간 > 하단', () => {
    const b = bollinger(CHOPPY).at(-1)
    expect(b.upper).toBeGreaterThan(b.mid)
    expect(b.mid).toBeGreaterThan(b.lower)
  })
  it('교차 찾기', () => {
    expect(crosses([1, 2, 3], [2, 2, 2], 'up')).toEqual([2])
    expect(isHit(10, [9])).toBe(true)
    expect(isHit(12, [9])).toBe(false)
  })
})

describe('레슨 차트 데이터에 정답이 정확히 있음', () => {
  it('골든크로스·데드크로스는 각각 한 번', () => {
    expect(targets('golden_cross', GOLDEN)).toHaveLength(1)
    expect(targets('dead_cross', DEAD)).toHaveLength(1)
  })
  it('RSI 급락 구간과 볼린저 하단 이탈이 있음', () => {
    expect(targets('rsi_oversold', RSI_DROP).length).toBeGreaterThan(0)
    expect(targets('bb_lower_break', BB_BREAK)).toContain(36)
  })
  it('횡보 차트는 교차가 여러 번 (속임수 신호 설명용)', () => {
    expect(targets('golden_cross', CHOPPY).length + targets('dead_cross', CHOPPY).length).toBeGreaterThanOrEqual(3)
  })
})
