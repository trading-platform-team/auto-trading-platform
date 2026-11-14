import { useState } from 'react'
import AlertFeed from './AlertFeed.jsx'
import AnomalyPanel from './AnomalyPanel.jsx'
import OrderTable from './OrderTable.jsx'
import PriceChart from './PriceChart.jsx'
import PriceTable from './PriceTable.jsx'
import StrategyPanel from './StrategyPanel.jsx'

const HELP = {
  welcome: { title: '초보자 쉬운 모드', simple: '실시간 자동매매 화면과 기능은 같지만, 어려운 용어를 누르면 이곳에서 바로 설명해드려요.', example: '오른쪽의 “RSI 과매도 매수”를 누르면 RSI가 무엇인지, 언제 주문하는 전략인지 설명이 나타나요.', caution: '이 화면의 주문은 모두 모의투자이며 수익을 보장하지 않아요.' },
  realtimePrice: { title: '실시간 시세', simple: '종목별로 지금 형성된 가격과 거래량을 1초마다 새로 보여주는 표예요.', example: '종목 행을 누르면 가운데 차트가 그 종목으로 바뀌어요.', caution: '현재는 실제 키움 시세가 아닌 연습용 모의 시세예요.' },
  price: { title: '현재가', simple: '지금 시장에서 거래되고 있는 주식 한 주의 가격이에요.', example: '현재가가 70,000원이면 1주를 사는 데 약 70,000원이 필요해요.', caution: '가격은 계속 변하므로 실제 체결 가격과 조금 다를 수 있어요.' },
  change: { title: '등락률', simple: '처음 관찰한 가격과 비교해 얼마나 오르거나 내렸는지를 백분율로 표시해요.', example: '+2%는 가격이 2% 올랐고, -2%는 2% 내렸다는 뜻이에요.', caution: '등락률만 보고 매수·매도를 결정하지 마세요.' },
  volume: { title: '거래량', simple: '일정 시간 동안 거래된 주식 수예요. 시장의 관심이 얼마나 큰지 살펴볼 때 사용해요.', example: '가격과 거래량이 함께 크게 늘면 강한 움직임일 가능성이 있어요.', caution: '거래량이 많다고 가격이 반드시 오르는 것은 아니에요.' },
  chart: { title: '실시간 가격 차트', simple: '시간이 흐르면서 가격과 보조지표가 어떻게 변했는지 선으로 보여줘요.', example: '흰색은 현재가, 주황색과 파란색은 이동평균선이에요.', caution: '짧은 구간의 모양만 보고 긴 흐름을 단정하기는 어려워요.' },
  sma5: { title: '최근 5개 평균선 · SMA5', simple: '현재 가격만 보면 순간적인 흔들림에 속기 쉬워요. 그래서 최근 가격 5개를 모두 더한 뒤 5로 나눈 평균을 선으로 이어서 흐름을 봐요.', terms: [{ name: 'SMA', meaning: 'Simple Moving Average의 줄임말로, 우리말로는 단순이동평균선이에요.' }, { name: '숫자 5', meaning: '최근 가격 5개를 사용한다는 뜻이에요. 숫자가 작아 현재 가격에 빠르게 반응해요.' }], example: '최근 가격이 10,000원, 10,100원, 10,200원, 10,300원, 10,400원이면 5개 평균은 10,200원이에요.', caution: '빠르게 움직이는 대신 잠깐의 가격 변화에도 방향이 자주 바뀔 수 있어요.' },
  sma20: { title: '최근 20개 평균선 · SMA20', simple: '최근 가격 20개의 평균을 이어 만든 선이에요. 5개 평균선보다 더 많은 가격을 사용해서 큰 흐름을 천천히 보여줘요.', terms: [{ name: 'SMA', meaning: '최근 가격을 똑같은 비중으로 더해 평균을 내는 단순이동평균선이에요.' }, { name: '숫자 20', meaning: '최근 가격 20개를 사용한다는 뜻이에요. 숫자가 커서 작은 흔들림에는 덜 반응해요.' }], example: '현재가가 20개 평균선보다 위에 있으면 현재 가격이 최근의 긴 평균보다 높은 상태예요.', caution: '여러 가격을 평균하기 때문에 실제 가격이 먼저 움직이고 평균선이 나중에 따라갈 수 있어요.' },
  rsi: { title: '가격의 과열 정도 · RSI', simple: '최근에 오른 힘과 내린 힘을 비교해서 0부터 100까지 숫자로 보여주는 값이에요.', terms: [{ name: 'RSI', meaning: 'Relative Strength Index의 줄임말이며, 최근 상승과 하락 중 어느 힘이 강한지 보여주는 지표예요.' }, { name: 'RSI(14)', meaning: '최근 가격 14개를 사용해 계산했다는 뜻이에요.' }, { name: '30과 70', meaning: '보통 30 아래는 많이 내려간 상태, 70 위는 많이 오른 상태로 참고해요.' }], example: 'RSI(14)가 30보다 작다는 조건은 최근 14개 가격을 봤을 때 하락 힘이 강한 경우를 찾는다는 뜻이에요.', caution: '30 아래라고 반드시 오르고, 70 위라고 반드시 내려가는 것은 아니에요.' },
  bollinger: { title: '평소 가격 범위 · 볼린저밴드', simple: '최근 평균 가격을 중심으로 평소 어느 정도까지 오르내렸는지 위쪽 선과 아래쪽 선으로 보여줘요.', terms: [{ name: '밴드', meaning: '위쪽 선과 아래쪽 선 사이의 띠 모양 가격 범위를 뜻해요.' }, { name: '볼린저 하단', meaning: '평소 가격 범위의 아래쪽 경계선이에요.' }, { name: '볼린저 상단', meaning: '평소 가격 범위의 위쪽 경계선이에요.' }], example: '현재가가 아래쪽 선보다 낮아지면 최근의 평소 범위보다 많이 내려온 상태로 볼 수 있어요.', caution: '급락하거나 급등하는 중에는 범위 밖에서 계속 움직일 수 있어요.' },
  strategy: { title: '자동매매 전략', simple: '미리 정한 조건이 모두 맞으면 시스템이 자동으로 모의 주문을 실행하는 규칙이에요.', example: '“RSI가 30보다 작으면 삼성전자 1주 매수”처럼 만들 수 있어요.', caution: '전략을 켜기 전에 조건·종목·수량을 다시 확인하세요.' },
  presetRsiBuy: { title: '많이 떨어졌을 때 사기 · RSI 과매도 매수', simple: '최근에 가격이 내려간 힘이 매우 강해졌을 때, 다시 오를 가능성을 기대하고 자동으로 사는 전략이에요.', terms: [{ name: 'RSI', meaning: '최근에 오른 힘과 내린 힘을 0~100으로 나타내는 값이에요.' }, { name: '과매도', meaning: '짧은 기간에 파는 사람이 많아 가격이 많이 내려간 상태를 뜻해요.' }, { name: 'RSI(14) < 30', meaning: '최근 가격 14개로 계산한 과열 정도가 30보다 낮을 때라는 뜻이에요.' }], example: '가격의 과열 정도가 30 아래로 내려오면 선택한 종목을 정한 수량만큼 모의 매수해요.', caution: '많이 떨어졌다고 바로 반등하는 것은 아니며 하락이 계속될 수 있어요.' },
  presetGoldenCross: { title: '상승 흐름이 시작될 때 사기 · 골든크로스', simple: '최근의 짧은 가격 흐름이 긴 가격 흐름보다 강해지는 순간을 상승 신호로 보고 자동으로 사는 전략이에요.', terms: [{ name: 'SMA', meaning: '최근 가격 여러 개를 더해서 평균 낸 값을 선으로 이어 놓은 단순이동평균선이에요.' }, { name: 'SMA5', meaning: '최근 가격 5개의 평균이에요. 짧은 흐름이라 가격 변화에 빠르게 반응해요.' }, { name: 'SMA20', meaning: '최근 가격 20개의 평균이에요. 긴 흐름이라 천천히 움직여요.' }, { name: '상향 돌파', meaning: '짧은 5개 평균선이 긴 20개 평균선 아래에 있다가 위로 넘어가는 순간이에요.' }], example: 'SMA5, 즉 최근 5개 가격의 평균선이 SMA20, 즉 최근 20개 가격의 평균선을 아래에서 위로 넘어가면 모의 매수해요.', caution: '가격이 뚜렷한 방향 없이 오르내릴 때는 두 선이 자주 교차해 불필요한 주문이 생길 수 있어요.' },
  presetBollingerBuy: { title: '평소보다 싸졌을 때 사기 · 볼린저 하단', simple: '현재 가격이 최근에 주로 움직이던 범위보다 아래로 내려오면 반등 가능성을 기대하고 자동으로 사는 전략이에요.', terms: [{ name: '볼린저밴드', meaning: '최근 평균 가격을 중심으로 평소 가격이 움직인 위·아래 범위를 표시한 띠예요.' }, { name: '하단', meaning: '그 가격 범위의 아래쪽 경계선이에요.' }, { name: '기간 20', meaning: '최근 가격 20개로 평균과 범위를 계산한다는 뜻이에요.' }], example: '지금 가격이 최근 가격 20개로 만든 아래쪽 경계선보다 낮아지면 모의 매수해요.', caution: '급락 중에는 평소 범위 아래로 내려간 뒤에도 가격이 계속 떨어질 수 있어요.' },
  presetRsiSell: { title: '많이 올랐을 때 팔기 · RSI 과매수 매도', simple: '최근에 가격이 오른 힘이 매우 강해졌을 때, 다시 내려갈 가능성을 생각해 자동으로 파는 전략이에요.', terms: [{ name: 'RSI', meaning: '최근 상승 힘과 하락 힘을 비교해 0~100으로 나타낸 값이에요.' }, { name: '과매수', meaning: '짧은 기간에 사는 사람이 많아 가격이 많이 오른 상태를 뜻해요.' }, { name: 'RSI(14) > 70', meaning: '최근 가격 14개로 계산한 과열 정도가 70보다 높을 때라는 뜻이에요.' }], example: '가격의 과열 정도가 70 위로 올라가면 선택한 종목을 정한 수량만큼 모의 매도해요.', caution: '상승 힘이 강하면 70을 넘은 뒤에도 가격이 계속 오를 수 있어요.' },
  strategyName: { title: '전략 이름', simple: '등록한 규칙을 나중에 쉽게 구분하기 위한 이름이에요.', example: '“삼성전자 과매도 반등”처럼 조건과 종목이 드러나게 적어보세요.', caution: '같은 이름을 여러 번 사용하면 주문 내역을 구분하기 어려워요.' },
  symbol: { title: '종목', simple: '자동매매 규칙을 적용할 주식이에요.', example: '삼성전자를 선택하면 조건도 삼성전자 시세로 판단해요.', caution: '전략을 등록하기 전에 원하는 종목이 맞는지 확인하세요.' },
  tradeSide: { title: '매수와 매도', simple: '매수는 주식을 사는 것, 매도는 보유한 주식을 파는 것이에요.', example: '가격이 많이 떨어졌을 때 매수하고, 많이 올랐을 때 매도하도록 만들 수 있어요.', caution: '보유 수량보다 많이 매도할 수는 없어요.' },
  quantity: { title: '수량', simple: '조건이 맞았을 때 한 번에 사고팔 주식의 개수예요.', example: '10주로 설정하면 조건 충족 시 10주를 주문해요.', caution: '처음에는 작은 수량으로 시험하는 것이 좋아요.' },
  cooldown: { title: '쿨다운', simple: '같은 조건이 계속 맞아도 주문이 너무 자주 반복되지 않도록 기다리는 시간이에요.', example: '60초면 주문 후 60초 동안 같은 전략은 다시 주문하지 않아요.', caution: '너무 짧으면 비슷한 가격에 주문이 여러 번 생길 수 있어요.' },
  condition: { title: '주문 조건', simple: '어떤 상황에서 자동 주문할지를 정하는 규칙이에요. 여러 조건은 모두 맞아야 주문돼요.', example: 'RSI < 30 그리고 현재가 < 볼린저 하단처럼 조합할 수 있어요.', caution: '조건이 너무 많으면 주문이 거의 발생하지 않을 수 있어요.' },
  operator: { title: '비교 방법', simple: '<는 작을 때, >는 클 때, 상향 돌파는 두 선이 아래에서 위로 교차할 때를 뜻해요.', example: 'RSI < 30은 RSI가 30보다 작다는 뜻이에요.', caution: '부등호 방향을 반대로 선택하지 않았는지 확인하세요.' },
  value: { title: '비교 값', simple: '지표와 비교할 기준 숫자예요.', example: 'RSI 과매도 기준으로 30을 자주 사용해요.', caution: '기준값에 따라 주문 빈도와 위험이 크게 달라져요.' },
  orders: { title: '모의 주문 내역', simple: '전략 조건을 만족해 자동으로 체결된 연습 주문을 보여줘요.', example: '어떤 전략이 언제 몇 주를 얼마에 거래했는지 확인할 수 있어요.', caution: '실제 증권계좌에서 체결된 주문이 아니에요.' },
  filledPrice: { title: '체결가', simple: '모의 주문이 실제로 처리됐다고 기록된 한 주의 가격이에요.', example: '10주를 70,000원에 매수했다면 주문 금액은 약 700,000원이에요.', caution: '현재가와 체결가는 시점 차이로 다를 수 있어요.' },
  alerts: { title: '실시간 알림', simple: '자동 주문이나 이상거래가 발생하면 시간순으로 알려주는 목록이에요.', example: '전략 주문 체결과 AI 이상 징후가 한곳에 표시돼요.', caution: '알림이 많을 때는 중요한 항목을 놓치지 않도록 내용을 확인하세요.' },
  anomaly: { title: 'AI 이상거래 탐지', simple: '가격·거래량·호가가 평소와 크게 다르게 움직이는 순간을 찾아 알려줘요.', example: '거래량이 평소보다 급증하거나 가격이 짧은 시간에 크게 움직이면 경보가 나와요.', caution: '이상 신호는 매수 추천이 아니라 주의해서 보라는 알림이에요.' },
  lof: { title: '평소와 다른 움직임 찾기 · LOF', simple: '주변의 평범한 움직임과 비교해 혼자 동떨어진 가격·거래량 움직임을 찾아내는 인공지능 방식이에요.', terms: [{ name: 'LOF', meaning: 'Local Outlier Factor의 줄임말로, 주변 데이터와 얼마나 다르게 떨어져 있는지 계산하는 방법이에요.' }, { name: '이상 점수', meaning: '평소 패턴과 다른 정도를 숫자로 나타낸 값이에요. 크다고 무조건 사고팔아야 한다는 뜻은 아니에요.' }], example: '대부분의 시세와 달리 한 종목의 거래량만 갑자기 크게 늘면 평소와 다른 움직임으로 감지할 수 있어요.', caution: '가상 데이터로 학습했기 때문에 실제 시장에서는 결과가 달라질 수 있어요.' },
}

export default function BeginnerMode({ symbols, selected, onSelected, selectedName, anomalySymbols, alerts, anomalies }) {
  const [helpKey, setHelpKey] = useState('welcome')
  const [lockedKey, setLockedKey] = useState(null)
  const help = HELP[helpKey] ?? HELP.welcome
  const previewFromEvent = (event) => {
    const target = event.target.closest?.('[data-explain]')
    if (!lockedKey && target?.dataset.explain && HELP[target.dataset.explain]) setHelpKey(target.dataset.explain)
  }
  const lockFromEvent = (event) => {
    const target = event.target.closest?.('[data-explain]')
    if (target?.dataset.explain && HELP[target.dataset.explain]) {
      setHelpKey(target.dataset.explain)
      setLockedKey(target.dataset.explain)
    }
  }

  return (
    <main className="beginner-dashboard" onClickCapture={lockFromEvent} onMouseOverCapture={previewFromEvent}>
      <aside className="beginner-guide card" aria-live="polite">
        <div className="guide-topline">
          <div className="guide-eyebrow">마우스로 배우는 쉬운 설명</div>
          {lockedKey && <button type="button" className="guide-unlock" onClick={(e) => { e.stopPropagation(); setLockedKey(null) }}>📌 고정 해제</button>}
        </div>
        <div className={`guide-pin-state ${lockedKey ? 'locked' : ''}`}>{lockedKey ? '이 설명은 고정되어 있어요' : '용어에 마우스를 올려보세요'}</div>
        <div className="guide-title-row"><span>💡</span><h2>{help.title}</h2></div>
        <p id="beginner-help-text" className="guide-simple">{help.simple}</p>
        {help.terms?.length > 0 && (
          <div className="guide-definitions">
            <b>용어부터 알아보기</b>
            {help.terms.map((term) => <div key={term.name}><strong>{term.name}</strong><p>{term.meaning}</p></div>)}
          </div>
        )}
        <div className="guide-block"><b>예를 들면</b><p>{help.example}</p></div>
        <div className="guide-block caution"><b>주의할 점</b><p>{help.caution}</p></div>
        <div className="guide-howto">
          <b>이용 방법</b>
          <ol><li>점선 밑줄이 있는 말에 마우스를 올리면 설명을 미리 볼 수 있어요.</li><li>용어를 클릭하면 📌 고정되어 마우스를 옮겨도 설명이 바뀌지 않아요.</li><li>다른 용어를 클릭하면 새 설명이 고정되고, 고정 해제를 누르면 다시 둘러볼 수 있어요.</li></ol>
          <b className="guide-terms-title">처음 알아둘 용어</b>
          <div className="guide-term-list">
            <button type="button" data-explain="price"><span>현재가</span><small>지금 주식 1주의 가격</small></button>
            <button type="button" data-explain="sma5"><span>최근 5개 평균선</span><small>짧은 가격 흐름 · SMA5</small></button>
            <button type="button" data-explain="sma20"><span>최근 20개 평균선</span><small>긴 가격 흐름 · SMA20</small></button>
            <button type="button" data-explain="rsi"><span>과열 정도</span><small>많이 올랐는지 확인 · RSI</small></button>
            <button type="button" data-explain="bollinger"><span>평소 가격 범위</span><small>위·아래 예상 범위 · 볼린저밴드</small></button>
          </div>
        </div>
      </aside>
      <div className="beginner-center">
        <PriceChart symbol={selected} name={selectedName} beginner />
        <OrderTable beginner />
      </div>
      <div className="beginner-right">
        <StrategyPanel symbols={symbols} selected={selected} beginner />
        <PriceTable selected={selected} onSelect={onSelected} anomalySymbols={anomalySymbols} beginner />
        <details className="beginner-fold card">
          <summary data-explain="alerts"><span>🔔 실시간 알림</span><small>클릭해서 펼치기</small></summary>
          <div className="beginner-fold-body"><AlertFeed alerts={alerts} beginner /></div>
        </details>
        <details className="beginner-fold card">
          <summary data-explain="anomaly"><span>⚠️ AI 이상거래 탐지</span><small>클릭해서 펼치기</small></summary>
          <div className="beginner-fold-body"><AnomalyPanel anomalies={anomalies} onSelect={onSelected} beginner /></div>
        </details>
      </div>
    </main>
  )
}
