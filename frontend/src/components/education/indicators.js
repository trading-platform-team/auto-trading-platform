// 레슨 차트용 지표 계산 (백엔드 TA-Lib와 같은 방식)

export function sma(arr, n) {
  return arr.map((_, i) => (i < n - 1 ? null : arr.slice(i - n + 1, i + 1).reduce((a, b) => a + b, 0) / n))
}

// RSI (Wilder 평활)
export function rsi(arr, n = 14) {
  const out = arr.map(() => null)
  if (arr.length <= n) return out
  let gain = 0
  let loss = 0
  for (let i = 1; i <= n; i++) {
    const d = arr[i] - arr[i - 1]
    gain += Math.max(d, 0)
    loss += Math.max(-d, 0)
  }
  gain /= n
  loss /= n
  out[n] = loss === 0 ? 100 : 100 - 100 / (1 + gain / loss)
  for (let i = n + 1; i < arr.length; i++) {
    const d = arr[i] - arr[i - 1]
    gain = (gain * (n - 1) + Math.max(d, 0)) / n
    loss = (loss * (n - 1) + Math.max(-d, 0)) / n
    out[i] = loss === 0 ? 100 : 100 - 100 / (1 + gain / loss)
  }
  return out
}

// 볼린저밴드 (모표준편차, TA-Lib 기본과 동일)
export function bollinger(arr, n = 20, k = 2) {
  const mid = sma(arr, n)
  return arr.map((_, i) => {
    if (mid[i] == null) return { upper: null, mid: null, lower: null }
    const w = arr.slice(i - n + 1, i + 1)
    const sd = Math.sqrt(w.reduce((s, v) => s + (v - mid[i]) ** 2, 0) / n)
    return { upper: mid[i] + k * sd, mid: mid[i], lower: mid[i] - k * sd }
  })
}

export function crosses(a, b, dir = 'up') {
  const idx = []
  for (let i = 1; i < a.length; i++) {
    if ([a[i - 1], b[i - 1], a[i], b[i]].some((v) => v == null)) continue
    if (dir === 'up' && a[i - 1] <= b[i - 1] && a[i] > b[i]) idx.push(i)
    if (dir === 'down' && a[i - 1] >= b[i - 1] && a[i] < b[i]) idx.push(i)
  }
  return idx
}

// 'spot' 카드의 정답 위치(인덱스) 목록
export function targets(find, closes) {
  if (find === 'golden_cross') return crosses(sma(closes, 5), sma(closes, 20), 'up')
  if (find === 'dead_cross') return crosses(sma(closes, 5), sma(closes, 20), 'down')
  if (find === 'rsi_oversold') return rsi(closes).flatMap((v, i) => (v != null && v < 30 ? [i] : []))
  if (find === 'rsi_overbought') return rsi(closes).flatMap((v, i) => (v != null && v > 70 ? [i] : []))
  if (find === 'bb_lower_break') {
    const bb = bollinger(closes)
    return closes.flatMap((c, i) => (bb[i].lower != null && c < bb[i].lower ? [i] : []))
  }
  throw new Error(`알 수 없는 find: ${find}`)
}

// 클릭한 위치가 정답 근처(±tolerance 칸)인지
export function isHit(index, answers, tolerance = 1) {
  return answers.some((a) => Math.abs(a - index) <= tolerance)
}
