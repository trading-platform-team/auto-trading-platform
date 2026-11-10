// 화면 표시용 포맷·변환 함수 (단위 테스트 대상)

export const INDICATORS = [
  { value: 'PRICE', label: '현재가', period: false },
  { value: 'SMA', label: '단순이동평균', period: 20 },
  { value: 'EMA', label: '지수이동평균', period: 20 },
  { value: 'RSI', label: 'RSI', period: 14 },
  { value: 'BB_UPPER', label: '볼린저 상단', period: 20 },
  { value: 'BB_MIDDLE', label: '볼린저 중간', period: 20 },
  { value: 'BB_LOWER', label: '볼린저 하단', period: 20 },
]

export const OPERATORS = [
  { value: '<', label: '<' },
  { value: '<=', label: '≤' },
  { value: '>', label: '>' },
  { value: '>=', label: '≥' },
  { value: 'cross_up', label: '상향 돌파' },
  { value: 'cross_down', label: '하향 돌파' },
]

export const fmtNum = (n) => (n == null ? '-' : Number(n).toLocaleString('ko-KR'))

export function fmtTime(iso) {
  if (!iso) return '-'
  // 시간대 표시가 없으면 UTC로 간주 (DB에 따라 생략되는 경우)
  const d = new Date(/[zZ]|[+-]\d\d:?\d\d$/.test(iso) ? iso : iso + 'Z')
  return d.toLocaleTimeString('ko-KR', { hour12: false })
}

export function indicatorLabel(ind) {
  if (typeof ind === 'number') return String(ind)
  const meta = INDICATORS.find((i) => i.value === ind.name)
  if (!meta || meta.period === false) return meta?.label ?? ind.name
  return `${meta.label}(${ind.period ?? meta.period})`
}

export function conditionLabel(cond) {
  const op = OPERATORS.find((o) => o.value === cond.op)?.label ?? cond.op
  return `${indicatorLabel(cond.left)} ${op} ${indicatorLabel(cond.right)}`
}

// 폼 상태 → API 요청 body
export function toStrategyPayload(form) {
  const toIndicator = (side) => {
    const meta = INDICATORS.find((i) => i.value === side.name)
    const ind = { name: side.name }
    if (meta && meta.period !== false) ind.period = Number(side.period) || meta.period
    return ind
  }
  return {
    name: form.name.trim(),
    symbol: form.symbol,
    side: form.side,
    quantity: Number(form.quantity),
    cooldown_sec: Number(form.cooldown_sec),
    enabled: true,
    conditions: form.conditions.map((c) => ({
      left: toIndicator(c.left),
      op: c.op,
      right: c.rightType === 'number' ? Number(c.rightValue) : toIndicator(c.right),
    })),
  }
}

// 시연용 전략 프리셋
export const PRESETS = [
  {
    name: 'RSI 과매도 매수',
    side: 'buy',
    conditions: [{ left: { name: 'RSI', period: 14 }, op: '<', rightType: 'number', rightValue: 30 }],
  },
  {
    name: '골든크로스 매수',
    side: 'buy',
    conditions: [
      { left: { name: 'SMA', period: 5 }, op: 'cross_up', rightType: 'indicator', right: { name: 'SMA', period: 20 } },
    ],
  },
  {
    name: '볼린저 하단 이탈 매수',
    side: 'buy',
    conditions: [{ left: { name: 'PRICE' }, op: '<', rightType: 'indicator', right: { name: 'BB_LOWER', period: 20 } }],
  },
  {
    name: 'RSI 과매수 매도',
    side: 'sell',
    conditions: [{ left: { name: 'RSI', period: 14 }, op: '>', rightType: 'number', rightValue: 70 }],
  },
]

// 음성 알림 문장
export function speechText(alert) {
  if (alert.type === 'order') return alert.message.replace(/@.*/, '').replace(/\[.*?\]/, '').trim() + ' 주문 체결'
  if (alert.type === 'anomaly') return `${alert.name} 이상거래 감지`
  return alert.message ?? ''
}

// 백엔드 조건 형식 → 폼 상태 (백테스트 프리셋 불러오기용)
export function toFormCondition(c) {
  return typeof c.right === 'number'
    ? { left: c.left, op: c.op, rightType: 'number', rightValue: c.right, right: { name: 'SMA', period: 20 } }
    : { left: c.left, op: c.op, rightType: 'indicator', rightValue: 30, right: c.right }
}

// 폼 조건 목록 → 백엔드 형식
export function toApiConditions(conditions) {
  return toStrategyPayload({ name: 'x', symbol: '', side: 'buy', quantity: 1, cooldown_sec: 0, conditions }).conditions
}

export const fmtPct = (n) => (n == null ? '-' : `${n > 0 ? '+' : ''}${Number(n).toFixed(2)}%`)
export const pctClass = (n) => (n > 0 ? 'up' : n < 0 ? 'down' : '')
export const fmtWon = (n) => (n == null ? '-' : `${Math.round(n).toLocaleString('ko-KR')}원`)
