// 실거래 화면 계산·표시 함수 (단위 테스트 대상)

export const ENV_LABEL = { mock: '모의투자 서버', real: '실전 서버' }

export const STATUS = {
  SUBMITTED: { label: '접수', cls: 'st-wait' },
  PARTIAL: { label: '일부 체결', cls: 'st-wait' },
  FILLED: { label: '체결', cls: 'st-ok' },
  CANCELLED: { label: '취소', cls: 'st-off' },
  REJECTED: { label: '거부', cls: 'st-bad' },
  BLOCKED: { label: '차단', cls: 'st-bad' },
}

export const statusInfo = (s) => STATUS[s] ?? { label: s, cls: '' }
export const isOpen = (o) => o.status === 'SUBMITTED' || o.status === 'PARTIAL'

// API 오류 메시지: request()가 detail을 JSON 문자열로 넣으므로 따옴표 제거
export function errText(err) {
  const m = err?.message ?? String(err)
  try {
    const v = JSON.parse(m)
    if (typeof v === 'string') return v
    if (Array.isArray(v)) return v.map((d) => d.msg ?? JSON.stringify(d)).join(', ')
  } catch {
    /* JSON이 아니면 그대로 */
  }
  return m
}

// 주문 예상 금액 (지정가면 지정가, 시장가면 현재가 기준)
export function orderAmount({ quantity, orderType, price }, currentPrice) {
  const q = Number(quantity) || 0
  const p = orderType === 'limit' ? Number(price) || 0 : Number(currentPrice) || 0
  return q * p
}

// 주문 전 화면에서 미리 확인 (서버에서도 같은 제한을 다시 검사함)
export function checkOrder(form, currentPrice, settings) {
  const q = Number(form.quantity)
  if (!form.symbol) return '종목을 먼저 선택하세요'
  if (!Number.isInteger(q) || q < 1) return '수량은 1주 이상 정수로 입력하세요'
  if (form.orderType === 'limit' && !(Number(form.price) > 0)) return '지정가를 입력하세요'
  if (form.orderType === 'market' && !(currentPrice > 0)) return '현재가를 불러온 뒤 주문하세요'
  if (!settings?.enabled) return '실거래가 꺼져 있어요. 오른쪽에서 먼저 활성화하세요'
  const amount = orderAmount(form, currentPrice)
  if (settings.max_order_amount && amount > settings.max_order_amount)
    return `1회 주문 한도(${settings.max_order_amount.toLocaleString('ko-KR')}원)를 넘어요`
  return null
}

export function toOrderBody(form) {
  const body = { symbol: form.symbol, side: form.side, quantity: Number(form.quantity) }
  if (form.orderType === 'limit') body.price = Number(form.price)
  return body
}

// 오늘 손실 / 한도 비율 (0~1)
export function lossRatio(today, limit) {
  if (!today || !limit) return 0
  return Math.min(1, Math.max(0, today.loss / limit))
}

export const ORDER_RESULT_TEXT = {
  SUBMITTED: '주문이 키움에 접수됐어요. 체결되면 주문 내역에 표시돼요',
  BLOCKED: '위험 제한으로 주문을 막았어요',
  REJECTED: '키움이 주문을 거부했어요',
}

// 등록된 키움 키 표시: 실전 서버 키 = 실제 주계좌, 모의투자 서버 키 = 모의투자 계좌
export const KEY_LABEL = { real: '실전 계좌(실제 돈)', mock: '모의투자 계좌' }
export function keyStatus(settings) {
  const keys = settings?.keys
  if (!keys) return null
  const have = ['real', 'mock'].filter((e) => keys[e]?.registered)
  const selected = settings.env
  return {
    text: have.length ? `등록된 키: ${have.map((e) => KEY_LABEL[e]).join(' · ')}` : '등록된 키움 키가 없어요',
    real: have.includes('real'),
    // 고른 서버에 맞는 키가 없으면 주문이 안 나간다
    missing: keys[selected]?.registered ? null : `${KEY_LABEL[selected]} 키가 없어 ${selected === 'real' ? '실전' : '모의투자'} 서버로 주문할 수 없어요`,
  }
}
