import { INDICATORS, OPERATORS } from '../format.js'

// 보조지표 조건 편집기 (실시간 전략 등록·백테스트 공용)

export const emptyCond = () => ({ left: { name: 'RSI', period: 14 }, op: '<', rightType: 'number', rightValue: 30, right: { name: 'SMA', period: 20 } })

function IndicatorPicker({ value, onChange }) {
  const meta = INDICATORS.find((i) => i.value === value.name)
  return (
    <span className="picker">
      <select value={value.name} onChange={(e) => onChange({ name: e.target.value, period: INDICATORS.find((i) => i.value === e.target.value).period || undefined })}>
        {INDICATORS.map((i) => (
          <option key={i.value} value={i.value}>{i.label}</option>
        ))}
      </select>
      {meta?.period !== false && (
        <input type="number" min={2} max={200} value={value.period ?? meta.period} onChange={(e) => onChange({ ...value, period: e.target.value })} title="기간" />
      )}
    </span>
  )
}

export function ConditionRow({ cond, onChange, onRemove }) {
  const set = (patch) => onChange({ ...cond, ...patch })
  return (
    <div className="cond-row">
      <IndicatorPicker value={cond.left} onChange={(left) => set({ left })} />
      <select value={cond.op} onChange={(e) => set({ op: e.target.value })}>
        {OPERATORS.map((o) => (
          <option key={o.value} value={o.value}>{o.label}</option>
        ))}
      </select>
      <select className="sm" value={cond.rightType} onChange={(e) => set({ rightType: e.target.value })}>
        <option value="number">값</option>
        <option value="indicator">지표</option>
      </select>
      {cond.rightType === 'number' ? (
        <input type="number" value={cond.rightValue} onChange={(e) => set({ rightValue: e.target.value })} />
      ) : (
        <IndicatorPicker value={cond.right ?? { name: 'SMA', period: 20 }} onChange={(right) => set({ right })} />
      )}
      {onRemove && <button className="icon-btn" onClick={onRemove} title="조건 삭제">✕</button>}
    </div>
  )
}

export function ConditionList({ conditions, onChange }) {
  return (
    <>
      {conditions.map((c, i) => (
        <ConditionRow
          key={i}
          cond={c}
          onChange={(nc) => onChange(conditions.map((x, j) => (j === i ? nc : x)))}
          onRemove={conditions.length > 1 ? () => onChange(conditions.filter((_, j) => j !== i)) : null}
        />
      ))}
      <button type="button" className="btn btn-ghost" onClick={() => onChange([...conditions, emptyCond()])}>
        + 조건 추가
      </button>
    </>
  )
}
