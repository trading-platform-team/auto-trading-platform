// 백엔드 API 호출 (nginx / vite 프록시가 /api → backend 로 전달)
const BASE = '/api'
const TOKEN_KEY = 'auth'

// 로그인 정보는 이 브라우저에만 저장 (사생활 보호 모드 등에서 실패해도 동작하도록 try/catch)
export const auth = {
  get() {
    try {
      return JSON.parse(localStorage.getItem(TOKEN_KEY)) ?? null
    } catch {
      return null
    }
  },
  set(value) {
    try {
      if (value) localStorage.setItem(TOKEN_KEY, JSON.stringify(value))
      else localStorage.removeItem(TOKEN_KEY)
    } catch {
      /* 저장 실패해도 이번 세션은 메모리로 동작 */
    }
    window.dispatchEvent(new CustomEvent('auth:change', { detail: value }))
  },
}

async function request(path, options = {}) {
  const token = auth.get()?.access_token
  const res = await fetch(BASE + path, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...options.headers,
    },
  })
  if (res.status === 401 && token) auth.set(null) // 토큰 만료 → 로그아웃
  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    throw new Error(body.detail ? JSON.stringify(body.detail) : `${res.status} ${res.statusText}`)
  }
  return res.status === 204 ? null : res.json()
}

export const api = {
  register: (username, password) =>
    request('/auth/register', { method: 'POST', body: JSON.stringify({ username, password }) }),
  login: (username, password) => request('/auth/login', { method: 'POST', body: JSON.stringify({ username, password }) }),
  health: () => request('/health/deps'),
  prices: () => request('/market/prices'),
  chart: (symbol, limit = 120) => request(`/market/chart/${symbol}?limit=${limit}`),
  indicators: (symbol) => request(`/indicators/${symbol}`),
  strategies: () => request('/strategies'),
  createStrategy: (body) => request('/strategies', { method: 'POST', body: JSON.stringify(body) }),
  updateStrategy: (id, body) => request(`/strategies/${id}`, { method: 'PUT', body: JSON.stringify(body) }),
  deleteStrategy: (id) => request(`/strategies/${id}`, { method: 'DELETE' }),
  orders: (limit = 30) => request(`/orders?limit=${limit}`),
  alerts: (limit = 30) => request(`/alerts?limit=${limit}`),
  anomalies: (limit = 30) => request(`/anomalies?limit=${limit}`),
  // 타임머신
  historySymbols: () => request('/history/symbols'),
  backtestPresets: () => request('/backtest/presets'),
  backtest: (body) => request('/backtest', { method: 'POST', body: JSON.stringify(body) }),
  tmCreate: (body) => request('/timemachine/sessions', { method: 'POST', body: JSON.stringify(body) }),
  tmStep: (id, days = 1) => request(`/timemachine/sessions/${id}/step`, { method: 'POST', body: JSON.stringify({ days }) }),
  tmOrder: (id, side, quantity) =>
    request(`/timemachine/sessions/${id}/order`, { method: 'POST', body: JSON.stringify({ side, quantity }) }),
  tmFinish: (id) => request(`/timemachine/sessions/${id}/finish`, { method: 'POST' }),
}

export function alertsSocketUrl() {
  const proto = window.location.protocol === 'https:' ? 'wss' : 'ws'
  const token = auth.get()?.access_token
  return `${proto}://${window.location.host}${BASE}/ws/alerts${token ? `?token=${encodeURIComponent(token)}` : ''}`
}
