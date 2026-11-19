import { useEffect, useState } from 'react'
import { api } from '../../api.js'
import Backtest from './Backtest.jsx'
import ManualTrading from './ManualTrading.jsx'

export default function TimeMachinePage() {
  const [mode, setMode] = useState('manual')
  const [symbols, setSymbols] = useState(null)

  useEffect(() => {
    api.historySymbols().then(setSymbols).catch(() => setSymbols([]))
  }, [])

  if (!symbols) return <p className="empty">과거 시세 불러오는 중...</p>
  const synthetic = symbols.some((s) => s.source === 'synthetic')
  const real = symbols.some((s) => s.source === 'public_data')

  return (
    <div className="tm-page">
      <div className="tm-top">
        <div className="seg">
          <button className={mode === 'manual' ? 'on' : ''} onClick={() => setMode('manual')}>
            직접 매매
          </button>
          <button className={mode === 'backtest' ? 'on' : ''} onClick={() => setMode('backtest')}>
            자동 백테스트
          </button>
        </div>
        {real && !synthetic ? (
          <span className="notice ok">
            <b>금융위원회 실제 일봉</b>으로 동작합니다 (공공데이터포털 주식시세정보)
          </span>
        ) : real ? (
          <span className="notice">
            <b>금융위원회 실제 일봉</b> 사용 중 · 아직 가상 일봉인 종목은 고르면 실제 일봉으로 바꿔 불러와요
          </span>
        ) : (
          <span className="notice">
            공공데이터 키가 없어 <b>교육용 가상 과거 시세</b>로 동작합니다 ({symbols[0]?.start} ~ {symbols[0]?.end})
          </span>
        )}
      </div>
      {symbols.length === 0 ? (
        <p className="empty">과거 시세가 없습니다</p>
      ) : mode === 'manual' ? (
        <ManualTrading symbols={symbols} />
      ) : (
        <Backtest symbols={symbols} />
      )}
    </div>
  )
}
