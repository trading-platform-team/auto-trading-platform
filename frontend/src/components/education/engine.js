// 레슨 진행 규칙 (화면과 분리된 순수 함수 → 단위 테스트)

export const MAX_HEARTS = 3
export const GRADED = new Set(['choice', 'ox', 'match', 'input', 'spot', 'slider', 'build'])

export const gradedCount = (cards) => cards.filter((c) => GRADED.has(c.type)).length

export function checkInput(card, value) {
  const v = Number(String(value).replace(/[,\s원%]/g, ''))
  if (!Number.isFinite(v) || String(value).trim() === '') return false
  const tol = Math.max(Math.abs(card.answer) * 0.005, 0.01)
  return Math.abs(v - card.answer) <= tol
}

// 레슨 진행 상태: {index, hearts, correct, wrong, done, failed}
export function start() {
  return { index: 0, hearts: MAX_HEARTS, correct: 0, wrong: 0, done: false, failed: false }
}

// result: true(정답) / false(오답) / null(채점 안 하는 카드)
export function answer(state, result) {
  if (result === true) return { ...state, correct: state.correct + 1 }
  if (result === false) {
    const hearts = state.hearts - 1
    return { ...state, wrong: state.wrong + 1, hearts, failed: hearts <= 0 }
  }
  return state
}

export function next(state, total) {
  const index = state.index + 1
  return index >= total ? { ...state, done: true } : { ...state, index }
}

// **굵게** 표시를 조각으로 나눔 → [{text, bold}]
export function parseBold(text) {
  return text.split(/(\*\*[^*]+\*\*)/g).filter(Boolean).map((t) =>
    t.startsWith('**') ? { text: t.slice(2, -2), bold: true } : { text: t, bold: false },
  )
}

// 연습 매매 미션 (계좌 상태로 판단)
export function missions(account) {
  const trades = account?.trades ?? []
  const buys = trades.filter((t) => t.side === 'buy')
  const sells = trades.filter((t) => t.side === 'sell')
  const symbolsBought = new Set(buys.map((t) => t.symbol))
  const boughtTwiceSame = [...symbolsBought].some((s) => buys.filter((t) => t.symbol === s).length >= 2)
  return [
    { id: 'buy', title: '첫 매수 해보기', hint: '아무 종목이나 1주 이상 사 보세요', done: buys.length > 0 },
    { id: 'avg', title: '같은 종목 두 번 나눠 사기', hint: '두 번 사면 평균 단가가 어떻게 바뀌는지 보세요', done: boughtTwiceSame },
    { id: 'diversify', title: '두 종목 이상 보유하기 (분산 투자)', hint: '한 종목에만 몰지 않기', done: (account?.positions ?? []).length >= 2 },
    { id: 'sell', title: '매도해서 손익 확정하기', hint: '판 순간 실현손익이 생겨요', done: sells.length > 0 },
    { id: 'profit', title: '이익을 보고 팔기', hint: '평단보다 비쌀 때 팔아 보세요', done: sells.some((t) => t.realized_pnl > 0) },
  ]
}

// 슬라이더 카드: 모든 값이 정답과 같은지 (허용 오차 tol)
export function checkSlider(card, values) {
  return card.fields.every((f) => Math.abs(Number(values[f.key]) - f.answer) <= (f.tol ?? 0))
}

// 손익비 = 익절폭 / 손절폭
export const rewardRisk = (tpPct, slPct) => (slPct === 0 ? null : Math.abs(tpPct) / Math.abs(slPct))

// 전략 만들기 카드: 만든 전략이 목표와 같은지 (조건 순서는 상관없음)
function normCond(c) {
  const ind = (x) => (typeof x === 'number' ? Number(x) : { name: x.name, period: x.period == null ? null : Number(x.period) })
  return JSON.stringify({ left: ind(c.left), op: c.op, right: ind(c.right) })
}

export function matchStrategy(target, built) {
  const problems = []
  if (target.symbol && built.symbol !== target.symbol) problems.push('종목')
  if (target.side && built.side !== target.side) problems.push('매수/매도')
  if (target.quantity && Number(built.quantity) !== target.quantity) problems.push('수량')
  if (target.cooldown_sec != null && Number(built.cooldown_sec) !== target.cooldown_sec) problems.push('쿨다운')
  const want = target.conditions.map(normCond).sort()
  const got = built.conditions.map(normCond).sort()
  if (JSON.stringify(want) !== JSON.stringify(got)) problems.push('조건')
  return { ok: problems.length === 0, problems }
}
