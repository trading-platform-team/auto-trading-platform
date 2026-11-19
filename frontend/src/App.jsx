import { useCallback, useEffect, useState } from 'react'
import { api, auth } from './api.js'
import EducationPage from './components/education/EducationPage.jsx'
import Header from './components/Header.jsx'
import LoginScreen from './components/LoginScreen.jsx'
import PaperTradingPage from './components/PaperTradingPage.jsx'
import RealTradingPage from './components/realtrading/RealTradingPage.jsx'
import TimeMachinePage from './components/timemachine/TimeMachinePage.jsx'
import { speechText } from './format.js'
import { useAlertSocket, usePolling } from './hooks.js'

function speak(text) {
  if (!('speechSynthesis' in window) || window.speechSynthesis.pending) return // 밀려 있으면 건너뜀
  const u = new SpeechSynthesisUtterance(text)
  u.lang = 'ko-KR'
  u.rate = 1.1
  window.speechSynthesis.speak(u)
}

export default function App() {
  const [user, setUser] = useState(auth.get())

  useEffect(() => {
    const onChange = (e) => setUser(e.detail)
    window.addEventListener('auth:change', onChange)
    return () => window.removeEventListener('auth:change', onChange)
  }, [])

  if (!user) return <LoginScreen />
  // key: 다른 계정으로 바꾸면 화면 상태·WebSocket을 새로 시작
  return <Dashboard key={user.username} username={user.username} />
}

function Dashboard({ username }) {
  const [page, setPage] = useState('education')
  const [voice, setVoice] = useState(false)
  const [alerts, setAlerts] = useState([])
  const { data: prices } = usePolling(api.prices, 5000)
  const { data: anomaliesData } = usePolling(() => api.anomalies(30), 2000)

  // 처음 열었을 때 최근 알림 불러오기
  useEffect(() => {
    api.alerts(30).then(setAlerts).catch(() => {})
  }, [])

  const onAlert = useCallback(
    (a) => {
      setAlerts((prev) => [a, ...prev].slice(0, 50))
      if (voice && (a.type === 'order' || a.level === 'high')) speak(speechText(a))
    },
    [voice],
  )
  const wsConnected = useAlertSocket(onAlert)

  const symbols = prices ?? []
  const anomalies = anomaliesData ?? []

  return (
    <div className="app">
      <Header voice={voice} onToggleVoice={() => setVoice((v) => !v)} wsConnected={wsConnected} page={page} onPage={setPage} username={username} />
      {page === 'education' ? (
        <main className="tm-main">
          <EducationPage onNavigate={setPage} />
        </main>
      ) : page === 'paper' ? (
        <PaperTradingPage symbols={symbols} alerts={alerts} anomalies={anomalies} />
      ) : page === 'timemachine' ? (
        <main className="tm-main">
          <TimeMachinePage />
        </main>
      ) : (
        <RealTradingPage symbols={symbols} alerts={alerts} anomalies={anomalies} />
      )}
    </div>
  )
}
