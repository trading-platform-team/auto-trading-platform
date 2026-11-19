import { useEffect, useState } from 'react'
import { api } from '../../../api.js'
import { fmtNum } from '../../../format.js'

// 호가창: 위는 매도호가(파랑), 아래는 매수호가(빨강). 가격을 누르면 주문 가격으로 들어간다
// load: 호가 조회 함수 (가상계좌는 연습용 호가, 실거래는 키움 실시간 호가 api.kwOrderbook)
export default function OrderBook({ symbol, onPick, picked, openPrices, onBook, load = api.eduOrderbook }) {
  const [book, setBook] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    let alive = true
    setBook(null)
    setError(null)
    const fetchBook = () =>
      load(symbol)
        .then((b) => {
          if (!alive) return
          setBook(b)
          setError(null)
          onBook?.(b)
        })
        .catch((e) => alive && setError(e.message.replace(/^"|"$/g, '')))
    fetchBook()
    const id = setInterval(fetchBook, 2500)
    return () => {
      alive = false
      clearInterval(id)
    }
  }, [symbol]) // eslint-disable-line react-hooks/exhaustive-deps

  if (!book) return <div className="orderbook"><p className="empty">{error ?? '호가 불러오는 중...'}</p></div>

  const max = Math.max(...book.asks.map((a) => a.quantity), ...book.bids.map((b) => b.quantity))
  const row = (lvl, kind) => (
    <button
      type="button"
      key={`${kind}${lvl.price}`}
      className={`ob-row ${kind} ${lvl.price === picked ? 'picked' : ''} ${lvl.price === book.price ? 'now' : ''}`}
      onClick={() => onPick(lvl.price)}
      title={`${fmtNum(lvl.price)}원을 주문 가격으로`}
    >
      <span className="ob-qty num">
        <i style={{ width: `${(lvl.quantity / max) * 100}%` }} />
        <em>{fmtNum(lvl.quantity)}</em>
      </span>
      <span className="ob-price num">
        {fmtNum(lvl.price)}
        {openPrices?.has(lvl.price) && <small className="ob-mine" title="내 미체결 주문">내 주문</small>}
      </span>
    </button>
  )

  return (
    <div className="orderbook">
      <div className="ob-head muted small" data-explain="orderbook"><span className="term">잔량</span><span className="term">호가</span></div>
      <div className="ob-list">
        {book.asks.map((a) => row(a, 'ask'))}
        {book.bids.map((b) => row(b, 'bid'))}
      </div>
      <div className="ob-foot muted small">
        <span>매도 {fmtNum(book.total_ask)}</span>
        <span>매수 {fmtNum(book.total_bid)}</span>
      </div>
      <p className="muted small ob-note">
        {book.simulated ? '재생 중인 가격을 기준으로 만든 연습용 호가예요 (실제 과거 호가 아님)' : '키움 실시간 호가'}
      </p>
    </div>
  )
}
