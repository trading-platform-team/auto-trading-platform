import { useState } from 'react'
import { HELP } from './explain.js'

const TERMS = [
  ['price', '현재가', '지금 주식 1주의 가격'],
  ['sma5', '최근 5개 평균선', '짧은 가격 흐름 · SMA5'],
  ['sma20', '최근 20개 평균선', '긴 가격 흐름 · SMA20'],
  ['rsi', '과열 정도', '많이 올랐는지 확인 · RSI'],
  ['bollinger', '평소 가격 범위', '위·아래 예상 범위 · 볼린저밴드'],
]

// 용어 설명 상태: 감싼 영역 안의 [data-explain] 요소에 마우스를 올리면 미리 보기, 누르면 고정
export function useExplain() {
  const [key, setKey] = useState('welcome')
  const [locked, setLocked] = useState(null)
  const [open, setOpen] = useState(true)
  const find = (e) => {
    const k = e.target.closest?.('[data-explain]')?.dataset.explain
    return k && HELP[k] ? k : null
  }
  return {
    help: HELP[key] ?? HELP.welcome,
    locked,
    open,
    setOpen,
    unlock: () => setLocked(null),
    handlers: {
      onMouseOverCapture: (e) => {
        const k = find(e)
        if (k && !locked) setKey(k)
      },
      onClickCapture: (e) => {
        const k = find(e)
        if (!k) return
        setKey(k)
        setLocked(k)
        setOpen(true) // 누르면 접혀 있어도 펼쳐서 보여 준다
      },
    },
  }
}

export default function ExplainPanel({ explain }) {
  const { help, locked, open, setOpen, unlock } = explain
  return (
    <details className="explain-panel" open={open} onToggle={(e) => setOpen(e.currentTarget.open)}>
      <summary>
        <span>💡 {help.title}</span>
        <small className="muted">{locked ? '📌 고정됨' : open ? '용어에 마우스를 올려 보세요' : '용어 설명 펼치기'}</small>
      </summary>
      <div className="explain-body" aria-live="polite">
        {locked && (
          <button type="button" className="guide-unlock" onClick={(e) => (e.preventDefault(), unlock())}>📌 고정 해제</button>
        )}
        <p className="guide-simple">{help.simple}</p>
        {help.terms?.length > 0 && (
          <div className="guide-definitions">
            <b>용어부터 알아보기</b>
            {help.terms.map((t) => <div key={t.name}><strong>{t.name}</strong><p>{t.meaning}</p></div>)}
          </div>
        )}
        <div className="guide-block"><b>예를 들면</b><p>{help.example}</p></div>
        <div className="guide-block caution"><b>주의할 점</b><p>{help.caution}</p></div>
        <div className="explain-terms">
          <b className="muted small">처음 알아둘 용어</b>
          <div className="guide-term-list">
            {TERMS.map(([k, name, sub]) => (
              <button key={k} type="button" data-explain={k}><span>{name}</span><small>{sub}</small></button>
            ))}
          </div>
        </div>
      </div>
    </details>
  )
}
