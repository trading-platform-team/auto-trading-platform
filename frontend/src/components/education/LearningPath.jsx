import { LESSONS } from './content/index.js'

export default function LearningPath({ progress, onStart, onGo }) {
  const all = progress.units.flatMap((u) => u.lessons)
  const done = all.filter((l) => l.stars).length
  return (
    <div className="path">
      {done === all.length ? (
        <div className="graduate">
          <div className="grad-icon">🎓</div>
          <div>
            <b>교육 과정 수료!</b>
            <p className="muted small">레슨 {all.length}개를 모두 마쳤어요. 이제 실제 화면에서 전략을 검증하고 운영해 보세요.</p>
          </div>
          {onGo && (
            <div className="grad-actions">
              <button className="btn" onClick={() => onGo('timemachine')}>타임머신 백테스트</button>
              <button className="btn btn-primary" onClick={() => onGo('live')}>실시간 자동매매</button>
            </div>
          )}
        </div>
      ) : (
        <div className="course-progress">
          <span>교육 과정 진행률</span>
          <div className="lesson-progress"><i style={{ width: `${(done / all.length) * 100}%` }} /></div>
          <b>{done}/{all.length}</b>
        </div>
      )}
      {progress.units.map((u, ui) => {
        const unitLocked = !u.lessons[0].unlocked
        return (
          <section key={u.id} className={`unit ${unitLocked ? 'locked' : ''}`}>
            <div className="unit-head">
              <div>
                <span className="unit-no">유닛 {ui + 1}</span>
                <h3>{u.title}</h3>
                <p className="muted small">{u.description}</p>
              </div>
              <span className="unit-count">{u.completed}/{u.total}</span>
            </div>
            <div className="nodes">
              {u.lessons.map((l, i) => {
                const ready = l.available && LESSONS[l.id]
                const state = !ready ? 'soon' : l.stars ? 'done' : l.unlocked ? 'open' : 'locked'
                return (
                  <button
                    key={l.id}
                    className={`node ${state}`}
                    style={{ marginLeft: `${[0, 40, 70, 40][i % 4]}px` }}
                    disabled={state === 'locked' || state === 'soon'}
                    onClick={() => onStart(l.id)}
                    title={state === 'soon' ? '준비 중' : state === 'locked' ? '이전 레슨을 먼저 완료하세요' : l.title}
                  >
                    <span className="node-circle">
                      {state === 'done' ? '✓' : state === 'locked' ? '🔒' : state === 'soon' ? '…' : '▶'}
                    </span>
                    <span className="node-label">
                      {l.title}
                      {l.stars && <span className="node-stars">{'★'.repeat(l.stars)}{'☆'.repeat(3 - l.stars)}</span>}
                      {state === 'soon' && <span className="muted small"> 준비 중</span>}
                    </span>
                  </button>
                )
              })}
            </div>
          </section>
        )
      })}
    </div>
  )
}
