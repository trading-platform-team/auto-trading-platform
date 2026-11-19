import { useEffect, useState } from 'react'
import { api } from '../../api.js'

// 타임머신 종목 고르기: 전 종목 검색 (자동매매·실거래와 같은 /stocks/search)
// 검색어가 없으면 코스피 시가총액 상위 종목을 보여준다 (전 종목에서 고를 수 있다는 걸 알 수 있게)
export default function SymbolSearch({ symbols, value, onChange }) {
  const [q, setQ] = useState('')
  const [open, setOpen] = useState(false)
  const [rows, setRows] = useState([])
  const [names, setNames] = useState({})
  const query = q.trim()

  useEffect(() => {
    let alive = true
    const load = () =>
      (query ? api.stocksSearch(query) : api.stocksBrowse({ market: 'KOSPI', sort: 'cap', limit: 30 }))
        .then((d) => alive && setRows(d))
        .catch(() => alive && setRows([]))
    const t = setTimeout(load, query ? 300 : 0)
    return () => {
      alive = false
      clearTimeout(t)
    }
  }, [query])

  const nameOf = (code) => names[code] ?? symbols.find((s) => s.symbol === code)?.name ?? code
  const pick = (r) => {
    setNames((n) => ({ ...n, [r.symbol]: r.name }))
    onChange(r.symbol, r.name)
    setQ('')
    setOpen(false)
  }

  return (
    <div className="symbol-search">
      <input
        type="search"
        placeholder={`${nameOf(value)} (${value}) · 종목명 또는 코드 검색`}
        value={q}
        onChange={(e) => (setQ(e.target.value), setOpen(true))}
        onFocus={() => setOpen(true)}
        onBlur={() => setTimeout(() => setOpen(false), 150)}
        aria-label="종목 검색"
      />
      {open && (
        <ul className="symbol-search-list">
          <li className="symbol-search-caption">
            {query ? `‘${query}’ 검색 결과` : '전 종목 검색 가능 · 코스피 시가총액 상위 30개'}
          </li>
          {rows.length === 0 ? (
            <li className="muted">{query ? '검색 결과가 없어요' : '불러오는 중...'}</li>
          ) : (
            rows.map((r) => (
              <li key={r.symbol} className={r.symbol === value ? 'active' : ''} onMouseDown={() => pick(r)}>
                <b>{r.name}</b> <small className="muted">{r.symbol}{r.sector ? ` · ${r.sector}` : ''}</small>
              </li>
            ))
          )}
        </ul>
      )}
    </div>
  )
}
