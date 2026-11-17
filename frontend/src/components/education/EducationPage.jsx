import { useCallback, useEffect, useState } from 'react'
import { api } from '../../api.js'
import './edu.css'
import Glossary from './Glossary.jsx'
import LearningPath from './LearningPath.jsx'
import LessonPlayer from './LessonPlayer.jsx'

const TABS = [
  ['path', '📚 학습'],
  ['glossary', '📖 용어 사전'],
  ['badges', '🏅 배지'],
]

function Stats({ p }) {
  const pct = p.xp_for_next ? Math.min(100, (p.xp_in_level / p.xp_for_next) * 100) : 100
  return (
    <div className="edu-stats">
      <div className="lvl">Lv.{p.level}</div>
      <div className="xpbar" title={`${p.xp} XP`}>
        <i style={{ width: `${pct}%` }} />
        <span>{p.xp_for_next ? `${p.xp_in_level} / ${p.xp_for_next} XP` : `${p.xp} XP · 최고 레벨`}</span>
      </div>
      <div className={`streak ${p.studied_today ? 'on' : ''}`} title={p.studied_today ? '오늘 학습 완료' : '오늘 레슨 1개로 연속 기록 유지'}>
        🔥 {p.streak}일
      </div>
      <div className="badge-count" title="모은 배지">🏅 {p.badges.filter((b) => b.owned).length}</div>
    </div>
  )
}

export default function EducationPage({ onNavigate }) {
  const [progress, setProgress] = useState(null)
  const [tab, setTab] = useState('path')
  const [lesson, setLesson] = useState(null)
  const [error, setError] = useState(null)

  const load = useCallback(() => api.eduProgress().then(setProgress).catch((e) => setError(e.message)), [])
  useEffect(() => {
    load()
  }, [load])

  if (error) return <p className="msg-err">{error}</p>
  if (!progress) return <p className="empty">학습 정보 불러오는 중...</p>

  if (lesson) {
    return (
      <LessonPlayer
        lessonId={lesson}
        badgesMeta={progress.badges}
        onDone={(r) => setProgress(r)}
        onExit={() => {
          setLesson(null)
          load()
        }}
      />
    )
  }

  const completed = new Set(progress.units.flatMap((u) => u.lessons.filter((l) => l.stars).map((l) => l.id)))

  return (
    <div className="edu">
      <div className="edu-top">
        <div className="seg">
          {TABS.map(([k, label]) => (
            <button key={k} className={tab === k ? 'on' : ''} onClick={() => setTab(k)}>{label}</button>
          ))}
        </div>
        <Stats p={progress} />
      </div>

      {tab === 'path' && <LearningPath progress={progress} onStart={setLesson} onGo={onNavigate} />}
      {tab === 'glossary' && <Glossary completed={completed} units={progress.units} />}
      {tab === 'badges' && (
        <div className="badges">
          {progress.badges.map((b) => (
            <div key={b.id} className={`badge ${b.owned ? 'owned' : ''}`}>
              <div className="badge-icon">{b.owned ? '🏅' : '🔒'}</div>
              <b>{b.name}</b>
              <p className="muted small">{b.description}</p>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
