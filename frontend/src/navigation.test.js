import { describe, expect, it } from 'vitest'
import { PAGE_INFO, PAGES } from './navigation.js'

describe('거래 모드 메뉴', () => {
  it('교육, 모의투자, 실거래, 타임머신 네 메뉴만 제공한다', () => {
    expect(PAGES.map((page) => page.id)).toEqual(['education', 'paper', 'live', 'timemachine'])
  })

  it('각 메뉴에 사용자 안내 문구가 있다', () => {
    PAGES.forEach((page) => {
      expect(PAGE_INFO[page.id].title).toBeTruthy()
      expect(PAGE_INFO[page.id].description).toBeTruthy()
    })
  })
})
