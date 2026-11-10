import { api, auth } from '../api.js'
import { usePolling } from '../hooks.js'

const LABEL = { kafka: 'Kafka', redis: 'Redis', postgres: 'DB', vault: 'Vault', ai: 'AI' }

export default function Header({ voice, onToggleVoice, wsConnected, page, onPage, username }) {
  const { data } = usePolling(api.health, 5000)
  const deps = data?.deps ?? {}

  return (
    <header className="header">
      <div className="brand">
        <span className="logo">◆</span>
        <div>
          <h1>지능형 자동매매 플랫폼</h1>
          <p>보조지표 전략 자동 실행 · AI 이상거래 탐지 · 모의투자</p>
        </div>
      </div>
      <nav className="tabs">
        <button className={page === 'live' ? 'on' : ''} onClick={() => onPage('live')}>
          실시간 자동매매
        </button>
        <button className={page === 'timemachine' ? 'on' : ''} onClick={() => onPage('timemachine')}>
          타임머신 트레이딩
        </button>
      </nav>
      <div className="header-right">
        <div className="status-chips">
          {Object.keys(LABEL).map((k) => (
            <span key={k} className={`chip ${deps[k] ? 'ok' : 'bad'}`} title={deps[k] ? '연결됨' : '연결 안 됨'}>
              <i /> {LABEL[k]}
            </span>
          ))}
          <span className={`chip ${wsConnected ? 'ok' : 'bad'}`} title="실시간 알림 연결">
            <i /> 실시간
          </span>
        </div>
        <button className={`btn ${voice ? 'btn-on' : ''}`} onClick={onToggleVoice}>
          {voice ? '🔊 음성 알림 켜짐' : '🔈 음성 알림 꺼짐'}
        </button>
        <span className="user-chip" title="로그인한 계정">
          👤 {username}
          <button className="icon-btn" onClick={() => auth.set(null)} title="로그아웃">
            로그아웃
          </button>
        </span>
      </div>
    </header>
  )
}
