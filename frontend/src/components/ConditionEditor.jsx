import { INDICATORS, OPERATORS } from '../format.js'

// 보조지표 조건 편집기 (실시간 전략 등록·백테스트 공용)

export const emptyCond = () => ({ left: { name: 'RSI', period: 14 }, op: '<', rightType: 'number', rightValue: 30, right: { name: 'SMA', period: 20 } })

const BEGINNER_LABEL = {
  PRICE: '지금 가격 (현재가)', SMA: '가격 평균선 (SMA)', EMA: '빠른 평균선 (EMA)', RSI: '과열 정도 (RSI)',
  BB_UPPER: '평소 범위 위쪽', BB_MIDDLE: '평균 가격 범위', BB_LOWER: '평소 범위 아래쪽',
}

function IndicatorPicker({ value, onChange, beginner }) {
  const meta = INDICATORS.find((i) => i.value === value.name)
  return (
    <span className="picker">
      <select value={value.name} onChange={(e) => onChange({ name: e.target.value, period: INDICATORS.find((i) => i.value === e.target.value).period || undefined })}>
        {INDICATORS.map((i) => (
          <option key={i.value} value={i.value}>{beginner ? BEGINNER_LABEL[i.value] : i.label}</option>
        ))}
      </select>
      {meta?.period !== false && (
        <input type="number" min={2} max={200} value={value.period ?? meta.period} onChange={(e) => onChange({ ...value, period: e.target.value })} title="기간" />
      )}
    </span>
  )
}

export function ConditionRow({ cond, onChange, onRemove, beginner = false }) {
  const set = (patch) => onChange({ ...cond, ...patch })
  return (
    <div className="cond-row">
      <IndicatorPicker value={cond.left} onChange={(left) => set({ left })} beginner={beginner} />
      <select value={cond.op} onChange={(e) => set({ op: e.target.value })}>
        {OPERATORS.map((o) => (
          <option key={o.value} value={o.value}>{beginner ? ({ '<': '보다 작을 때 (<)', '<=': '이하일 때 (≤)', '>': '보다 클 때 (>)', '>=': '이상일 때 (≥)', cross_up: '아래에서 위로 통과', cross_down: '위에서 아래로 통과' }[o.value]) : o.label}</option>
        ))}
      </select>
      <select className="sm" value={cond.rightType} onChange={(e) => set({ rightType: e.target.value })}>
        <option value="number">값</option>
        <option value="indicator">지표</option>
      </select>
      {cond.rightType === 'number' ? (
        <input type="number" value={cond.rightValue} onChange={(e) => set({ rightValue: e.target.value })} />
      ) : (
        <IndicatorPicker value={cond.right ?? { name: 'SMA', period: 20 }} onChange={(right) => set({ right })} beginner={beginner} />
      )}
      {onRemove && <button className="icon-btn" onClick={onRemove} title="조건 삭제">✕</button>}
    </div>
  )
}

export function ConditionList({ conditions, onChange, beginner = false }) {
  return (
    <>
      {conditions.map((c, i) => (
        <ConditionRow
          key={i}
          cond={c}
          onChange={(nc) => onChange(conditions.map((x, j) => (j === i ? nc : x)))}
          onRemove={conditions.length > 1 ? () => onChange(conditions.filter((_, j) => j !== i)) : null}
          beginner={beginner}
        />
      ))}
      <button type="button" className="btn btn-ghost" onClick={() => onChange([...conditions, emptyCond()])}>
        + 조건 추가
      </button>
    </>
  )
}
