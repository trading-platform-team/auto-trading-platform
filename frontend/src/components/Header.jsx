import { api, auth } from '../api.js'
import { usePolling } from '../hooks.js'
import { PAGE_INFO, PAGES } from '../navigation.js'

const LABEL = { kafka: 'Kafka', redis: 'Redis', postgres: 'DB', vault: 'Vault', ai: 'AI' }

export default function Header({ voice, onToggleVoice, wsConnected, page, onPage, username }) {
  const { data } = usePolling(api.health, 5000)
  const deps = data?.deps ?? {}
  const current = PAGE_INFO[page] ?? PAGE_INFO.education

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
        {PAGES.map((item) => (
          <button key={item.id} className={page === item.id ? 'on' : ''} onClick={() => onPage(item.id)}>
            <small>{item.eyebrow}</small><span>{item.title}</span>
          </button>
        ))}
      </nav>
      <div className="header-right">
        <div className="mode-chip" title={current.description}>
          <small>{current.eyebrow}</small><b>{current.title}</b>
        </div>
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
