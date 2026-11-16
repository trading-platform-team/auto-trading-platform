import { useState } from 'react'
import { api } from '../../api.js'
import { CARD_COMPONENTS, Rich } from './Cards.jsx'
import { LESSONS } from './content/index.js'
import { answer, gradedCount, MAX_HEARTS, next, start } from './engine.js'

const PRAISE = ['정답이에요!', '좋아요!', '완벽해요!', '잘했어요!']

export default function LessonPlayer({ lessonId, badgesMeta, onExit, onDone }) {
  const lesson = LESSONS[lessonId]
  const [state, setState] = useState(start)
  const [feedback, setFeedback] = useState(null) // {ok, text}
  const [result, setResult] = useState(null)
  const [error, setError] = useState(null)
  const total = lesson.cards.length
  const card = lesson.cards[state.index]
  const Card = CARD_COMPONENTS[card.type]

  const finish = async (s) => {
    try {
      const r = await api.eduComplete(lessonId, s.correct, Math.max(1, gradedCount(lesson.cards)))
      setResult(r)
      onDone?.(r)
    } catch (e) {
      setError(e.message)
    }
  }

  const onCheck = (ok) => {
    const s = answer(state, ok)
    setState(s)
    if (ok === null) {
      if (!['predict', 'duel', 'deploy'].includes(card.type)) proceed(s)
      return
    }
    setFeedback({ ok, text: card.explain ?? '' })
  }

  const onPredict = ({ hit, change, text }) =>
    setFeedback({
      ok: hit,
      neutral: true,
      text: text ?? `실제로는 ${change > 0 ? '+' : ''}${change}% ${change > 0 ? '올랐어요' : '내렸어요'}. ${hit ? '감이 좋네요!' : '예측은 어려워요.'} 그래서 **정해진 규칙**과 **손절·익절**로 매매하는 게 중요해요. 자동매매가 필요한 이유죠!`,
    })

  const proceed = (s = state) => {
    setFeedback(null)
    if (s.failed) return
    const n = next(s, total)
    setState(n)
    if (n.done) finish(n)
  }

  const retry = () => {
    setState(start())
    setFeedback(null)
  }

  // ----- 결과 화면 -----
  if (state.failed && !feedback) {
    return (
      <div className="lesson">
        <div className="lesson-end">
          <div className="end-icon">💔</div>
          <h2>하트를 모두 잃었어요</h2>
          <p className="muted">괜찮아요. 틀린 문제의 해설을 기억하면서 다시 도전해 봐요!</p>
          <button className="btn btn-primary big" onClick={retry}>다시 도전</button>
          <button className="btn btn-ghost" onClick={onExit}>학습 경로로</button>
        </div>
      </div>
    )
  }
  if (state.done) {
    const names = Object.fromEntries((badgesMeta ?? []).map((b) => [b.id, b]))
    return (
      <div className="lesson">
        <div className="lesson-end">
          {!result && !error && <p className="muted">결과 저장 중...</p>}
          {error && <p className="msg-err">{error}</p>}
          {result && (
            <>
              <div className="stars">
                {[1, 2, 3].map((i) => (
                  <span key={i} className={i <= result.stars ? 'on' : ''}>★</span>
                ))}
              </div>
              <h2>{lesson.title} 완료!</h2>
              <div className="end-stats">
                <div><b>+{result.xp_gained}</b><span>XP</span></div>
                <div><b>🔥 {result.streak}</b><span>연속 학습일</span></div>
                <div><b>{state.correct}/{gradedCount(lesson.cards)}</b><span>정답</span></div>
              </div>
              {result.new_badges.map((b) => (
                <div key={b} className="new-badge">🏅 새 배지 <b>{names[b]?.name ?? b}</b> · {names[b]?.description}</div>
              ))}
              <button className="btn btn-primary big" onClick={onExit}>계속</button>
            </>
          )}
        </div>
      </div>
    )
  }

  // ----- 진행 화면 -----
  return (
    <div className="lesson">
      <div className="lesson-top">
        <button className="icon-btn" onClick={onExit} title="나가기">✕</button>
        <div className="lesson-progress">
          <i style={{ width: `${(state.index / total) * 100}%` }} />
        </div>
        <span className="hearts" title="하트">
          {Array.from({ length: MAX_HEARTS }, (_, i) => (
            <span key={i} className={i < state.hearts ? '' : 'lost'}>♥</span>
          ))}
        </span>
      </div>

      <div className={`lesson-card type-${card.type}`} key={state.index}>
        <Card card={card} onCheck={onCheck} onPredict={onPredict} locked={!!feedback} />
        {card.type === 'concept' && !feedback && (
          <button className="btn btn-primary big" onClick={() => onCheck(null)}>계속</button>
        )}
      </div>

      {feedback && (
        <div className={`feedback ${feedback.neutral ? 'neutral' : feedback.ok ? 'ok' : 'bad'}`}>
          <div>
            <b>{feedback.neutral ? '결과 공개!' : feedback.ok ? PRAISE[state.index % PRAISE.length] : '아쉬워요'}</b>
            {!feedback.ok && !feedback.neutral && <span className="muted small"> · 하트 -1</span>}
            {feedback.text && <div className="rich"><Rich text={feedback.text} /></div>}
          </div>
          <button className="btn big" onClick={() => proceed()}>{state.failed ? '결과 보기' : '계속'}</button>
        </div>
      )}
    </div>
  )
}
