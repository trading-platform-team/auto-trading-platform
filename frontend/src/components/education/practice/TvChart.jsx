import { useEffect, useRef, useState } from 'react'
import { CrosshairMode, createChart } from 'lightweight-charts'
import { fmtNum } from '../../../format.js'

const UP = '#f2555a'
const day = (t) => (typeof t === 'string' ? t : t && `${t.year}-${String(t.month).padStart(2, '0')}-${String(t.day).padStart(2, '0')}`)
const DOWN = '#4c8ff5'

// 일봉 차트 (TradingView lightweight-charts): TradingView와 같은 조작
//   마우스 휠 → 시간축 확대·축소, 끌기 → 좌우 이동, 가격축 끌기 → 세로로 늘이기·줄이기,
//   시간축 끌기 → 가로로 늘이기·줄이기, 더블클릭 → 처음 보기(고른 기간)로 되돌리기
// bars: [{date: 'YYYY-MM-DD', open, high, low, close, volume}], kind: 'line' | 'candle', days: 처음 보여 줄 거래일 수
export default function TvChart({ bars, kind, days, height = 260 }) {
  const box = useRef(null)
  const chart = useRef(null)
  const series = useRef({})
  const [legend, setLegend] = useState(null)

  // 차트는 한 번 만들고, 종류·데이터가 바뀌면 시리즈만 바꾼다
  useEffect(() => {
    const c = createChart(box.current, {
      autoSize: true,
      layout: { background: { color: 'transparent' }, textColor: '#8b95a5', fontSize: 11 },
      grid: { vertLines: { color: '#1f252f' }, horzLines: { color: '#1f252f' } },
      crosshair: { mode: CrosshairMode.Normal },
      rightPriceScale: { borderColor: '#262d39', scaleMargins: { top: 0.08, bottom: 0.26 } },
      timeScale: { borderColor: '#262d39', rightOffset: 4, minBarSpacing: 2 },
      localization: { locale: 'ko-KR', priceFormatter: (p) => fmtNum(Math.round(p)) },
    })
    chart.current = c
    const onMove = (param) => {
      const s = series.current.main
      const d = s && param.seriesData?.get(s)
      setLegend(d ? { ...d, volume: param.seriesData.get(series.current.volume)?.value } : null)
    }
    c.subscribeCrosshairMove(onMove)
    return () => {
      c.unsubscribeCrosshairMove(onMove)
      c.remove()
      chart.current = null
      series.current = {}
    }
  }, [])

  useEffect(() => {
    const c = chart.current
    if (!c) return
    for (const s of Object.values(series.current)) c.removeSeries(s)
    const main =
      kind === 'candle'
        ? c.addCandlestickSeries({ upColor: UP, downColor: DOWN, borderVisible: false, wickUpColor: UP, wickDownColor: DOWN })
        : c.addAreaSeries({ lineColor: '#7c6cf2', topColor: 'rgba(124,108,242,0.35)', bottomColor: 'rgba(124,108,242,0)', lineWidth: 2 })
    const volume = c.addHistogramSeries({ priceFormat: { type: 'volume' }, priceScaleId: 'volume', lastValueVisible: false, priceLineVisible: false })
    c.priceScale('volume').applyOptions({ scaleMargins: { top: 0.8, bottom: 0 } })
    main.setData(
      bars.map((b) =>
        kind === 'candle'
          ? { time: b.date, open: b.open || b.close, high: b.high || b.close, low: b.low || b.close, close: b.close }
          : { time: b.date, value: b.close },
      ),
    )
    volume.setData(
      bars.map((b) => ({ time: b.date, value: b.volume ?? 0, color: b.close >= b.open ? 'rgba(242,85,90,0.45)' : 'rgba(76,143,245,0.45)' })),
    )
    series.current = { main, volume }
  }, [bars, kind])

  // 기간 버튼·종목 변경·더블클릭: 최근 days개 거래일이 보이게
  const reset = () => {
    const c = chart.current
    if (!c || !bars.length) return
    c.priceScale('right').applyOptions({ autoScale: true })
    c.timeScale().setVisibleLogicalRange({ from: Math.max(0, bars.length - days), to: bars.length + 3 })
  }
  useEffect(reset, [bars, days]) // eslint-disable-line react-hooks/exhaustive-deps

  const last = bars[bars.length - 1]
  const shown = legend ?? (last && { time: last.date, ...last, value: last.close })
  return (
    <div className="tv-chart" onDoubleClick={reset}>
      {shown && (
        <div className="tv-legend num">
          <span className="muted">{day(shown.time)}</span>
          {shown.open != null && kind === 'candle' ? (
            <>
              <span>시 {fmtNum(shown.open)}</span>
              <span className="up">고 {fmtNum(shown.high)}</span>
              <span className="down">저 {fmtNum(shown.low)}</span>
              <span>종 {fmtNum(shown.close)}</span>
            </>
          ) : (
            <span>종가 {fmtNum(shown.value ?? shown.close)}</span>
          )}
          {shown.volume != null && <span className="muted">거래량 {fmtNum(shown.volume)}</span>}
        </div>
      )}
      <div ref={box} style={{ height }} />
      <p className="muted small tv-help">휠: 확대·축소 · 끌기: 이동 · 가격축 끌기: 세로 크기 · 더블클릭: 처음 보기로</p>
    </div>
  )
}
