import { describe, it, expect } from 'vitest'
import { toStatusRows } from './status.js'

describe('toStatusRows', () => {
  it('서비스 상태를 행으로 변환한다', () => {
    const rows = toStatusRows({ kafka: true, redis: false })
    expect(rows).toEqual([
      { name: 'kafka', label: '정상', ok: true },
      { name: 'redis', label: '연결 안 됨', ok: false },
    ])
  })
})
