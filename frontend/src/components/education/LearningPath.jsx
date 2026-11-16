import { LESSONS } from './content/index.js'

export default function LearningPath({ progress, onStart }) {
  return (
    <div className="path">
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
