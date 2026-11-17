import { useEffect, useState } from 'react'
import { api } from '../../../api.js'
import { fmtNum, fmtPct, pctClass } from '../../../format.js'

const SORTS = [
  { key: 'cap', label: '시가총액' },
  { key: 'change', label: '상승률' },
  { key: 'fall', label: '하락률' },
  { key: 'volume', label: '거래량' },
]

// 종목 찾기: 검색 / 관심종목 / 코스피·코스닥 + 업종 + 정렬
export default function StockBrowser({ selected, onSelect, watch, onToggleWatch, source }) {
  const [tab, setTab] = useState('all')
  const [q, setQ] = useState('')
  const [market, setMarket] = useState('KOSPI')
  const [sector, setSector] = useState('')
  const [sort, setSort] = useState('cap')
  const [markets, setMarkets] = useState([])
  const [sectors, setSectors] = useState([])
  const [rows, setRows] = useState(null)
  const [error, setError] = useState(null)

  // 시세 출처가 바뀌면(가상 → 키움 목록 받기 완료) 시장·업종 목록을 다시 받는다
  useEffect(() => {
    api.stocksMarkets().then(setMarkets).catch(() => {})
  }, [source])

  useEffect(() => {
    setSector('')
    api.stocksSectors(market).then(setSectors).catch(() => setSectors([]))
  }, [market, source])

  // 목록: 검색어가 있으면 검색, 아니면 탭에 따라. 10초마다 가격 갱신
  const query = q.trim()
  useEffect(() => {
    let alive = true
    const load = () => {
      const p = query
        ? api.stocksSearch(query)
        : tab === 'watch'
          ? Promise.resolve(watch.items)
          : api.stocksBrowse({ market, sector, sort })
      p.then((d) => alive && (setRows(d), setError(null))).catch((e) => alive && setError(e.message))
    }
    const t = setTimeout(load, query ? 300 : 0) // 검색어 입력 중에는 잠깐 기다렸다가
    const id = setInterval(load, 10000)
    return () => {
      alive = false
      clearTimeout(t)
      clearInterval(id)
    }
  }, [query, tab, market, sector, sort, watch.items, source])

  const watched = new Set(watch.items.map((x) => x.symbol))

  return (
    <section className="card stock-browser">
      <div className="card-head">
        <h2>종목 찾기</h2>
        <div className="seg small-seg">
          <button className={tab === 'all' ? 'on' : ''} onClick={() => setTab('all')}>전체</button>
          <button className={tab === 'watch' ? 'on' : ''} onClick={() => setTab('watch')}>★ 관심 {watch.items.length}</button>
        </div>
      </div>

      <input
        className="stock-search"
        type="search"
        placeholder="종목명 또는 코드 검색 (예: 삼성, 005930)"
        value={q}
        onChange={(e) => setQ(e.target.value)}
        aria-label="종목 검색"
      />

      {!query && tab === 'all' && (
        <div className="browse-filters">
          <div className="seg small-seg">
            {(markets.length ? markets : [{ market: 'KOSPI', label: '코스피' }, { market: 'KOSDAQ', label: '코스닥' }]).map((m) => (
              <button key={m.market} className={market === m.market ? 'on' : ''} onClick={() => setMarket(m.market)}>
                {m.label}
                {m.count ? <small className="muted"> {fmtNum(m.count)}</small> : null}
              </button>
            ))}
          </div>
          <select value={sector} onChange={(e) => setSector(e.target.value)} aria-label="업종">
            <option value="">전체 업종</option>
            {sectors.map((s) => (
              <option key={s.sector} value={s.sector}>{s.sector} ({s.count})</option>
            ))}
          </select>
          <select value={sort} onChange={(e) => setSort(e.target.value)} aria-label="정렬">
            {SORTS.map((s) => <option key={s.key} value={s.key}>{s.label}순</option>)}
          </select>
        </div>
      )}

      <p className="muted small list-caption">
        {query
          ? `‘${query}’ 검색 결과`
          : tab === 'watch'
            ? '★를 눌러 담은 종목'
            : `${sector || '전체 업종'} · 시가총액 상위 30개 · ${SORTS.find((s) => s.key === sort).label}순`}
      </p>

      {error && <p className="msg-err">{error}</p>}
      {rows == null ? (
        <p className="empty">불러오는 중...</p>
      ) : rows.length === 0 ? (
        <p className="empty">{query ? '검색 결과가 없어요' : tab === 'watch' ? '아직 관심종목이 없어요. 종목 옆 ☆를 눌러 담아 보세요' : '종목이 없어요'}</p>
      ) : (
        <div className="stock-list">
          <table className="table clickable">
            <tbody>
              {rows.map((r) => (
                <tr key={r.symbol} className={r.symbol === selected ? 'active' : ''} onClick={() => onSelect(r.symbol)}>
                  <td className="star-cell">
                    <button
                      className={`star ${watched.has(r.symbol) ? 'on' : ''}`}
                      aria-label={watched.has(r.symbol) ? '관심종목에서 빼기' : '관심종목에 담기'}
                      onClick={(e) => {
                        e.stopPropagation()
                        onToggleWatch(r.symbol)
                      }}
                    >
                      {watched.has(r.symbol) ? '★' : '☆'}
                    </button>
                  </td>
                  <td className="stock-name">
                    <b>{r.name}</b>
                    {r.warning && <span className="warn-tag">{r.warning}</span>}
                    <small className="muted">{r.symbol} · {r.sector}</small>
                  </td>
                  <td className="r num">{r.price ? fmtNum(r.price) : '-'}</td>
                  <td className={`r num ${pctClass(r.change_pct)}`}>{r.change_pct == null ? '-' : fmtPct(r.change_pct)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  )
}
