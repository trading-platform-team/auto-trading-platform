import { useEffect, useRef, useState } from 'react'

// 1초마다 백엔드에서 최신 시세를 받아 표로 보여준다
export default function PriceTable() {
  const [prices, setPrices] = useState([])
  const prev = useRef({})

  useEffect(() => {
    const load = () =>
      fetch('/api/market/prices')
        .then((r) => r.json())
        .then((data) => {
          setPrices((old) => {
            prev.current = Object.fromEntries(old.map((p) => [p.symbol, p.price]))
            return data
          })
        })
        .catch(() => {})
    load()
    const id = setInterval(load, 1000)
    return () => clearInterval(id)
  }, [])

  if (prices.length === 0) return <p>시세 수신 대기 중...</p>

  return (
    <table style={{ width: '100%', borderCollapse: 'collapse' }}>
      <thead>
        <tr style={{ textAlign: 'right', borderBottom: '1px solid #ccc' }}>
          <th style={{ textAlign: 'left' }}>종목</th>
          <th>현재가</th>
          <th>거래량</th>
          <th>매수잔량</th>
          <th>매도잔량</th>
        </tr>
      </thead>
      <tbody>
        {prices.map((p) => {
          const before = prev.current[p.symbol]
          const color = before == null || before === p.price ? 'inherit' : p.price > before ? '#d32f2f' : '#1565c0'
          return (
            <tr key={p.symbol} style={{ textAlign: 'right' }}>
              <td style={{ textAlign: 'left' }}>
                {p.name} <small>{p.symbol}</small>
              </td>
              <td style={{ color, fontWeight: 600 }}>{p.price.toLocaleString()}</td>
              <td>{p.volume.toLocaleString()}</td>
              <td>{p.bid_size.toLocaleString()}</td>
              <td>{p.ask_size.toLocaleString()}</td>
            </tr>
          )
        })}
      </tbody>
    </table>
  )
}
