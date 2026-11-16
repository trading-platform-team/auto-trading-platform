// 레슨용 연습 차트 데이터 (항상 같은 모양이 나오도록 고정 생성)
const wiggle = (i, amp = 1) => Math.sin(i * 1.7) * amp + Math.sin(i * 0.9 + 1) * amp * 0.6

// 하락하다가 반등 → 5일선이 20일선을 뚫고 올라가는 골든크로스 1번
export const GOLDEN = Array.from({ length: 50 }, (_, i) =>
  Math.round(100 + (i < 26 ? -i * 0.9 : -26 * 0.9 + (i - 26) * 1.5) + wiggle(i, 0.6)),
)

// 상승하다가 꺾임 → 데드크로스 1번
export const DEAD = GOLDEN.map((v) => 200 - v)

// 잔잔하다가 며칠 연속 급락 → RSI 30 아래
export const RSI_DROP = Array.from({ length: 50 }, (_, i) => {
  if (i < 30) return Math.round((100 + wiggle(i, 1.2)) * 10) / 10
  if (i < 37) return Math.round((100 - (i - 29) * 2.4) * 10) / 10
  return Math.round((83 + (i - 37) * 0.6 + wiggle(i, 0.8)) * 10) / 10
})

// 좁은 범위에서 움직이다가 하루 크게 빠짐 → 볼린저 하단 이탈
export const BB_BREAK = Array.from({ length: 45 }, (_, i) => {
  if (i === 36) return 93
  if (i > 36) return Math.round((94 + (i - 36) * 0.8 + wiggle(i, 0.5)) * 10) / 10
  return Math.round((100 + wiggle(i, 0.9)) * 10) / 10
})

// 횡보 → 이평선이 자주 엇갈림 (속임수 신호)
export const CHOPPY = Array.from({ length: 50 }, (_, i) => Math.round((100 + Math.sin(i * 0.55) * 3 + wiggle(i, 0.8)) * 10) / 10)
