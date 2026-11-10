import { useCallback, useEffect, useMemo, useState } from 'react'
import { api, auth } from './api.js'
import AlertFeed from './components/AlertFeed.jsx'
import AnomalyPanel from './components/AnomalyPanel.jsx'
import Header from './components/Header.jsx'
import LoginScreen from './components/LoginScreen.jsx'
import OrderTable from './components/OrderTable.jsx'
import PriceChart from './components/PriceChart.jsx'
import PriceTable from './components/PriceTable.jsx'
import StrategyPanel from './components/StrategyPanel.jsx'
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
  const [page, setPage] = useState('live')
  const [selected, setSelected] = useState('005930')
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
  const recentAnomalySymbols = useMemo(() => {
    const cutoff = Date.now() - 60_000
    return new Set(anomalies.filter((a) => new Date(a.timestamp).getTime() > cutoff).map((a) => a.symbol))
  }, [anomalies])
  const selectedName = symbols.find((s) => s.symbol === selected)?.name

  return (
    <div className="app">
      <Header voice={voice} onToggleVoice={() => setVoice((v) => !v)} wsConnected={wsConnected} page={page} onPage={setPage} username={username} />
      {page === 'timemachine' ? (
        <main className="tm-main">
          <TimeMachinePage />
        </main>
      ) : (
      <main className="grid">
        <div className="col-left">
          <PriceTable selected={selected} onSelect={setSelected} anomalySymbols={recentAnomalySymbols} />
          <AlertFeed alerts={alerts} />
        </div>
        <div className="col-center">
          <PriceChart symbol={selected} name={selectedName} />
          <OrderTable />
        </div>
        <div className="col-right">
          <StrategyPanel symbols={symbols} selected={selected} />
          <AnomalyPanel anomalies={anomalies} onSelect={setSelected} />
        </div>
      </main>
      )}
    </div>
  )
}
