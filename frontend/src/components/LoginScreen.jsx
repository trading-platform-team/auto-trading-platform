import { useState } from 'react'
import { api, auth } from '../api.js'

const FEATURES = [
  ['📈', '자동매매', '보조지표 조건을 만들면 실시간 시세로 자동 모의 주문'],
  ['🛡️', 'AI 이상거래 탐지', '룰 + LOF 모델로 거래량·가격·호가 이상 징후 경보'],
  ['⏳', '타임머신 트레이딩', '과거로 돌아가 직접 매매하고 전략과 성과 비교'],
]

function parseError(msg) {
  if (msg.includes('pattern')) return '아이디는 영문·숫자·밑줄(_) 3~30자로 입력하세요'
  if (msg.includes('at least 3')) return '아이디는 3자 이상이어야 합니다'
  if (msg.includes('at least 8')) return '비밀번호는 8자 이상이어야 합니다'
  try {
    return JSON.parse(msg)
  } catch {
    return msg
  }
}

export default function LoginScreen() {
  const [mode, setMode] = useState('login')
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [err, setErr] = useState(null)
  const [loading, setLoading] = useState(false)

  const submit = async (e) => {
    e.preventDefault()
    setErr(null)
    setLoading(true)
    try {
      const res = mode === 'login' ? await api.login(username, password) : await api.register(username, password)
      auth.set(res)
    } catch (e2) {
      setErr(parseError(e2.message))
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="login-page">
      <div className="login-intro">
        <div className="brand">
          <span className="logo">◆</span>
          <h1>지능형 자동매매 플랫폼</h1>
        </div>
        <p className="muted">보조지표 기반 전략 자동 실행 · AI 이상거래 탐지 · 모든 거래는 모의투자</p>
        <ul className="feature-list">
          {FEATURES.map(([icon, title, desc]) => (
            <li key={title}>
              <span className="feature-icon">{icon}</span>
              <div>
                <b>{title}</b>
                <p className="muted small">{desc}</p>
              </div>
            </li>
          ))}
        </ul>
      </div>

      <form className="login-card" onSubmit={submit}>
        <div className="seg">
          <button type="button" className={mode === 'login' ? 'on' : ''} onClick={() => setMode('login')}>
            로그인
          </button>
          <button type="button" className={mode === 'register' ? 'on' : ''} onClick={() => setMode('register')}>
            회원가입
          </button>
        </div>
        <label>
          아이디
          <input value={username} autoComplete="username" onChange={(e) => setUsername(e.target.value)} required />
        </label>
        <label>
          비밀번호
          <input
            type="password"
            value={password}
            autoComplete={mode === 'login' ? 'current-password' : 'new-password'}
            onChange={(e) => setPassword(e.target.value)}
            required
          />
        </label>
        {mode === 'register' && <p className="muted small">아이디는 영문·숫자 3자 이상, 비밀번호는 8자 이상</p>}
        <button className="btn btn-primary" disabled={loading}>
          {loading ? '처리 중...' : mode === 'login' ? '로그인' : '가입하고 시작하기'}
        </button>
        {err && <p className="msg-err">{err}</p>}
      </form>
    </div>
  )
}
