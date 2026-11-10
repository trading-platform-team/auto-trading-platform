// 백엔드 API 호출 (nginx / vite 프록시가 /api → backend 로 전달)
const BASE = '/api'

async function request(path, options = {}) {
  const res = await fetch(BASE + path, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  })
  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    throw new Error(body.detail ? JSON.stringify(body.detail) : `${res.status} ${res.statusText}`)
  }
  return res.status === 204 ? null : res.json()
}

export const api = {
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
  return `${proto}://${window.location.host}${BASE}/ws/alerts`
}
