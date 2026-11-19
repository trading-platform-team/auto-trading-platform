import Practice from './education/Practice.jsx'
import './education/edu.css'

// 모의투자: 가상계좌 하나로 직접 주문(지정가·시장가)과 자동매매를 같이 한다
export default function PaperTradingPage({ symbols, alerts, anomalies }) {
  return (
    <main className="paper-main">
      <section className="mode-intro">
        <div>
          <span className="mode-kicker">가상자금으로 안전하게</span>
          <h2>모의투자</h2>
          <p>실제 돈은 사용하지 않습니다. 호가창을 보며 직접 주문하거나, 주문 영역의 자동매매 탭에서 전략을 걸어 두세요.</p>
        </div>
      </section>
      <div className="paper-content"><Practice symbols={symbols} alerts={alerts} anomalies={anomalies} /></div>
    </main>
  )
}
