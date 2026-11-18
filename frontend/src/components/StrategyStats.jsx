import { fmtNum, fmtWon, pctClass } from '../format.js'

// 가상계좌 전략별 성과: 직접 주문 vs 자동매매 전략 (거래 수·실현손익·승률)
export default function StrategyStats({ stats }) {
  if (!stats?.some((x) => x.auto)) return null // 자동매매 거래가 없으면 표시하지 않음
  return (
    <section className="card">
      <div className="card-head">
        <h2>전략별 성과</h2>
        <span className="muted small">실현손익·승률은 매도한 거래 기준 (수수료 포함)</span>
      </div>
      <div className="scroll">
        <table className="table">
          <thead>
            <tr>
              <th>구분</th>
              <th className="r">거래</th>
              <th className="r">매수 / 매도</th>
              <th className="r">실현손익</th>
              <th className="r">승률</th>
            </tr>
          </thead>
          <tbody>
            {stats.map((x) => (
              <tr key={x.strategy_id ?? 'manual'}>
                <td>{x.auto ? <><span className="tag">자동</span> {x.name}</> : x.name}</td>
                <td className="r num">{fmtNum(x.trades)}</td>
                <td className="r num">{fmtNum(x.buys)} / {fmtNum(x.sells)}</td>
                <td className={`r num ${pctClass(x.realized_pnl)}`}>{x.realized_pnl > 0 ? '+' : ''}{fmtWon(x.realized_pnl)}</td>
                <td className="r num">{x.win_rate == null ? '-' : `${x.win_rate}% (${x.wins}/${x.sells})`}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  )
}
