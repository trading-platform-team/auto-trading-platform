import { useEffect, useState } from 'react'
import { api } from '../api.js'

// 전략 종목 고르기: 이름·코드로 전 종목 검색 (/stocks/search, 가상계좌 연습과 같은 목록)
export default function SymbolSearch({ value, name, onChange }) {
  const [q, setQ] = useState('')
  const [items, setItems] = useState([])
  const [err, setErr] = useState(null)
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    if (!q.trim()) {
      setItems([])
      return
    }
    setLoading(true)
    let stale = false // 늦게 온 이전 검색 결과는 버린다
    const id = setTimeout(() => {
      api
        .stocksSearch(q.trim())
        .then((r) => !stale && (setItems(r.slice(0, 10)), setErr(null)))
        .catch((e) => !stale && setErr(e.message))
        .finally(() => !stale && setLoading(false))
    }, 250) // 입력이 멈추면 검색
    return () => {
      stale = true
      clearTimeout(id)
    }
  }, [q])

  const pick = (s) => {
    onChange(s.symbol, s.name)
    setQ('')
  }

  return (
    <div className="symbol-search">
      <input
        value={q}
        placeholder={name ? `${name} (${value})` : value || '종목명 또는 코드'}
        onChange={(e) => setQ(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === 'Enter') {
            e.preventDefault() // 폼 제출 대신 첫 결과 선택
            if (items[0]) pick(items[0])
          } else if (e.key === 'Escape') setQ('')
        }}
        aria-label="종목 검색"
      />
      {q.trim() && (
        <ul className="symbol-results">
          {err && <li className="msg-err small">{err}</li>}
          {!err && items.length === 0 && <li className="empty small">{loading ? '검색 중…' : '검색 결과가 없어요'}</li>}
          {items.map((s) => (
            <li key={s.symbol}>
              <button type="button" className={s.symbol === value ? 'on' : ''} onClick={() => pick(s)}>
                <span>{s.name}</span>
                <span className="muted num">{s.symbol}</span>
                {s.warning && <span className="tag warn">{s.warning}</span>}
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
