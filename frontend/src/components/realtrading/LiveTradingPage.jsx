import { useState } from 'react'
import { Bot, Briefcase } from 'lucide-react'
import RealTradingPage from './RealTradingPage.jsx'

// 실거래 메뉴: 자동매매 전략(기존 대시보드) + 키움 계좌·주문
export default function LiveTradingPage({ children }) {
  const [tab, setTab] = useState('strategy')

  return (
    <div className="paper-main">
      <section className="mode-intro">
        <div>
          <span className="mode-kicker">키움 계좌 연결</span>
          <h2>실거래</h2>
          <p>
            키움 계좌 탭에서 실거래를 켜야 주문이 나가요. 전략의 주문 계좌를 &apos;키움 실거래&apos;로 고르면
            자동매매도 키움으로 주문해요.
          </p>
        </div>
        <div className="seg" role="tablist" aria-label="실거래 화면 선택">
          <button role="tab" aria-selected={tab === 'strategy'} className={tab === 'strategy' ? 'on' : ''} onClick={() => setTab('strategy')}>
            <Bot size={16} aria-hidden />
            자동매매 전략
          </button>
          <button role="tab" aria-selected={tab === 'kiwoom'} className={tab === 'kiwoom' ? 'on' : ''} onClick={() => setTab('kiwoom')}>
            <Briefcase size={16} aria-hidden />
            키움 계좌·주문
          </button>
        </div>
      </section>
      {tab === 'kiwoom' ? (
        <main className="tm-main">
          <RealTradingPage />
        </main>
      ) : (
        children
      )}
    </div>
  )
}
