import { useState } from 'react'
import BeginnerMode from './BeginnerMode.jsx'
import Practice from './education/Practice.jsx'
import './education/edu.css'

export default function PaperTradingPage({
  symbols,
  selected,
  onSelected,
  selectedName,
  anomalySymbols,
  alerts,
  anomalies,
}) {
  const [tab, setTab] = useState('account')

  return (
    <main className="paper-main">
      <section className="mode-intro">
        <div>
          <span className="mode-kicker">가상자금으로 안전하게</span>
          <h2>모의투자</h2>
          <p>실제 돈은 사용하지 않습니다. 교육용 계좌로 주문을 연습하거나 초보자용 자동매매 화면을 이용하세요.</p>
        </div>
        <div className="seg" role="tablist" aria-label="모의투자 화면 선택">
          <button role="tab" aria-selected={tab === 'account'} className={tab === 'account' ? 'on' : ''} onClick={() => setTab('account')}>
            💰 가상계좌 연습
          </button>
          <button role="tab" aria-selected={tab === 'beginner'} className={tab === 'beginner' ? 'on' : ''} onClick={() => setTab('beginner')}>
            🌱 초보자 자동매매
          </button>
        </div>
      </section>

      {tab === 'account' ? (
        <div className="paper-content"><Practice /></div>
      ) : (
        <BeginnerMode
          symbols={symbols}
          selected={selected}
          onSelected={onSelected}
          selectedName={selectedName}
          anomalySymbols={anomalySymbols}
          alerts={alerts}
          anomalies={anomalies}
        />
      )}
    </main>
  )
}
