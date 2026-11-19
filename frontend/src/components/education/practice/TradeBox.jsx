import { useEffect, useMemo, useState } from 'react'
import { fmtNum, fmtTime, fmtWon } from '../../../format.js'
import StrategyPanel from '../../StrategyPanel.jsx'
import OrderBook from './OrderBook.jsx'
import { estimate, maxBuy, quickQty, stepPrice, tickSize, validPrice } from './trade.js'

const TABS = [
  { key: 'buy', label: '매수' },
  { key: 'sell', label: '매도' },
  { key: 'auto', label: '자동매매' },
]

// 주문 영역: 매수·매도는 호가창을 보며 지정가/시장가 주문, 자동매매는 이 종목에 전략 등록
// 점선 밑줄 용어(data-explain)는 차트 아래 용어 설명 패널에 풀이가 나온다
// 가상계좌(Practice)와 실거래(RealTradingPage)가 같이 쓴다:
//   account: { available_cash, positions: [{symbol, quantity, sellable, avg_price}], open_orders: [{id, symbol, name, side, price, quantity, created_at}] }
//   loadBook: 호가 조회 함수, fallbackPrice: 호가를 못 받을 때 쓸 현재가
//   guard(side, qty, price): 주문 전 확인 (문제가 있으면 안내 문장 → 주문 버튼 꺼짐)
//   strategyAccount: 자동매매 탭 전략의 주문 계좌 ('paper' | 'kiwoom'), autoBlock: 자동매매를 못 쓰는 이유
export default function TradeBox({
  symbol, name, account, onOrder, onCancel, msg, symbols,
  loadBook, fallbackPrice = 0, guard, strategyAccount = 'paper', autoBlock = null,
}) {
  const [tab, setTab] = useState('buy')
  const [type, setType] = useState('limit')
  const [price, setPrice] = useState(null) // 지정가 (null이면 아직 호가를 못 받음)
  const [qty, setQty] = useState(1)
  const [now, setNow] = useState(0)
  const [tick, setTick] = useState(null) // 호가창이 알려 준 호가 단위

  // 종목이 바뀌면 주문 가격은 새 호가를 받을 때 현재가로 다시 채운다
  useEffect(() => {
    setPrice(null)
    setNow(0)
    setTick(null)
  }, [symbol])

  const onBook = (book) => {
    setNow(book.price)
    setTick(book.tick)
    setPrice((p) => p ?? book.price)
  }

  const side = tab === 'sell' ? 'sell' : 'buy'
  const held = account?.positions.find((p) => p.symbol === symbol)
  const sellable = held?.sellable ?? held?.quantity ?? 0
  const cash = account?.available_cash ?? account?.cash ?? 0
  const current = now || fallbackPrice
  const orderPrice = type === 'market' ? current : price ?? 0
  const ctx = { cash, price: orderPrice, held: sellable }
  const est = estimate(side, orderPrice, qty)
  const unit = tick || tickSize(price || current || 1)
  const priceOk = type === 'market' || validPrice(orderPrice, tick)
  const mine = useMemo(() => (account?.open_orders ?? []).filter((o) => o.symbol === symbol), [account, symbol])
  const openPrices = useMemo(() => new Set(mine.map((o) => o.price)), [mine])
  const problem = guard?.(side, qty, orderPrice) ?? null

  // 호가를 못 받으면(실거래에서 키움 키가 없을 때 등) 현재가로 주문 가격을 채운다
  useEffect(() => {
    if (!now && fallbackPrice) setPrice((p) => p ?? fallbackPrice)
  }, [now, fallbackPrice])

  const submit = () =>
    onOrder(symbol, name, side, qty, type === 'limit' ? { order_type: 'limit', price } : { order_type: 'market' })

  return (
    <section className="card trade-box">
      <div className="seg trade-tabs" role="tablist" aria-label="주문 종류">
        {TABS.map((t) => (
          <button
            key={t.key}
            role="tab"
            aria-selected={tab === t.key}
            className={`${tab === t.key ? 'on' : ''} ${t.key}`}
            onClick={() => setTab(t.key)}
          >
            {t.label}
          </button>
        ))}
      </div>

      {tab === 'auto' ? (
        <div className="trade-auto">
          {autoBlock && <p className="msg-err small">{autoBlock}</p>}
          <StrategyPanel symbols={symbols} selected={symbol} selectedName={name} beginner fixedSymbol fixedAccount={strategyAccount} disabled={!!autoBlock} />
        </div>
      ) : (
        <div className="trade-split">
          <OrderBook symbol={symbol} load={loadBook} onPick={(p) => (setType('limit'), setPrice(p))} picked={type === 'limit' ? price : null} openPrices={openPrices} onBook={onBook} />

          <div className="order-form">
            <div className="seg small-seg order-type">
              <button className={type === 'limit' ? 'on' : ''} onClick={() => setType('limit')}>지정가</button>
              <button className={type === 'market' ? 'on' : ''} onClick={() => setType('market')}>시장가</button>
            </div>

            <label className="field">
              <span className="muted small"><span className="term" data-explain="tick">가격</span></span>
              {type === 'market' ? (
                <div className="price-input market">{current ? `${fmtNum(current)}원 (지금 가격)` : '-'}</div>
              ) : (
                <div className="price-input">
                  <button type="button" aria-label="한 호가 내리기" onClick={() => setPrice((p) => stepPrice(p ?? current, -1, tick))}>−</button>
                  <input
                    type="number"
                    value={price ?? ''}
                    step={unit}
                    onChange={(e) => setPrice(Math.max(0, Math.floor(Number(e.target.value))))}
                    aria-label="주문 가격"
                  />
                  <button type="button" aria-label="한 호가 올리기" onClick={() => setPrice((p) => stepPrice(p ?? current, 1, tick))}>+</button>
                </div>
              )}
              {type === 'limit' && price > 0 && !priceOk && (
                <span className="msg-err small">호가 단위({fmtNum(unit)}원)에 맞춰 주세요</span>
              )}
            </label>

            <label className="field">
              <span className="muted small">수량</span>
              <div className="qty-row">
                <input type="number" min={1} value={qty} onChange={(e) => setQty(Math.max(0, Math.floor(Number(e.target.value))))} aria-label="수량" />
                <span>주</span>
              </div>
              <div className="qty-row">
                {[0.1, 0.25, 0.5, 1].map((r) => (
                  <button key={r} className="chip-btn" onClick={() => setQty(quickQty(side, r, ctx))}>
                    {r === 1 ? '최대' : `${r * 100}%`}
                  </button>
                ))}
              </div>
            </label>

            <p className="muted small">
              {side === 'buy'
                ? `주문 가능 ${fmtWon(cash)} · 최대 ${fmtNum(maxBuy(cash, orderPrice))}주`
                : `팔 수 있는 수량 ${fmtNum(sellable)}주${held ? ` · 평단 ${fmtNum(held.avg_price)}원` : ''}`}
            </p>
            {est && (
              <p className="estimate">
                {side === 'buy' ? '예상 결제 금액' : '예상 받을 금액'} <b className="num">{fmtWon(est.total)}</b>
                <small className="muted"> (<span className="term" data-explain="fee">수수료</span> {fmtWon(est.fee)})</small>
              </p>
            )}
            <p className="muted small term" data-explain={type === 'market' ? 'marketOrder' : 'limitOrder'}>
              {type === 'market'
                ? '지금 가격으로 바로 체결돼요'
                : side === 'buy'
                  ? '지금 가격 이상이면 바로 체결, 낮으면 가격이 내려올 때까지 기다려요'
                  : '지금 가격 이하면 바로 체결, 높으면 가격이 올라올 때까지 기다려요'}
            </p>
            <button
              className={`btn ${side === 'buy' ? 'btn-buy' : 'btn-sell'} order-go`}
              disabled={!orderPrice || !qty || !priceOk || !!problem}
              onClick={submit}
            >
              {type === 'limit' && price ? `${fmtNum(price)}원 ` : ''}
              {fmtNum(qty)}주 {side === 'buy' ? '매수' : '매도'}
            </button>
            {problem && <p className="msg-err small">{problem}</p>}
            {msg && <p className={msg.ok ? 'msg-ok' : 'msg-err'}>{msg.text}</p>}
          </div>
        </div>
      )}

      <div className="open-orders">
        <div className="card-head"><h3><span className="term" data-explain="openOrders">미체결</span></h3><span className="muted small">{fmtNum(account?.open_orders?.length ?? 0)}건</span></div>
        {(account?.open_orders ?? []).length === 0 ? (
          <p className="empty small">걸어 둔 주문이 없어요</p>
        ) : (
          <table className="table">
            <tbody>
              {account.open_orders.map((o) => (
                <tr key={o.id} className={o.symbol === symbol ? 'active' : ''}>
                  <td className="muted num">{fmtTime(o.created_at)}</td>
                  <td>{o.name}</td>
                  <td className={o.side === 'buy' ? 'up' : 'down'}>{o.side === 'buy' ? '매수' : '매도'}</td>
                  <td className="r num">{fmtNum(o.price)}원</td>
                  <td className="r num">{fmtNum(o.quantity)}주</td>
                  <td className="r"><button className="btn btn-ghost small-btn" onClick={() => onCancel(o.id)}>취소</button></td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </section>
  )
}
