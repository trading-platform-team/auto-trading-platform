import { useEffect, useState } from 'react'
import PriceTable from './PriceTable.jsx'
import { toStatusRows } from './status.js'

export default function App() {
  const [rows, setRows] = useState([])
  const [error, setError] = useState(null)

  useEffect(() => {
    fetch('/api/health/deps')
      .then((r) => r.json())
      .then((data) => setRows(toStatusRows(data.deps)))
      .catch(() => setError('백엔드에 연결할 수 없습니다'))
  }, [])

  return (
    <main style={{ fontFamily: 'sans-serif', maxWidth: 760, margin: '40px auto', padding: '0 16px' }}>
      <h1>보조지표 기반 지능형 자동매매 플랫폼</h1>
      <h2>실시간 시세 (모의)</h2>
      <PriceTable />
      <h2>서비스 상태</h2>
      {error && <p style={{ color: 'crimson' }}>{error}</p>}
      <ul>
        {rows.map((r) => (
          <li key={r.name}>
            {r.ok ? '🟢' : '🔴'} {r.name}: {r.label}
          </li>
        ))}
      </ul>
    </main>
  )
}
