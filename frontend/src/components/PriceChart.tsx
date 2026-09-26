import { useEffect, useState } from 'react'
import { api, type ChartPeriod, type PriceHistory } from '../api'
import { linePoints, tradeMarkers } from '../chart'
import { formatMoney } from '../format'

// Expanded price chart for one watchlist stock (D37): daily adjusted close, period buttons,
// low/high, and the agent's buys and sells marked on the line.

const PERIODS: ChartPeriod[] = ['1M', '3M', '1Y']
const WIDTH = 600
const HEIGHT = 150

export function PriceChart({ symbol, currency }: { symbol: string; currency: string }) {
  const [period, setPeriod] = useState<ChartPeriod>('3M')
  const [data, setData] = useState<PriceHistory | null>(null)
  const [failed, setFailed] = useState(false)

  useEffect(() => {
    let cancelled = false
    setData(null)
    setFailed(false)
    api
      .priceHistory(symbol, period)
      .then((d) => !cancelled && setData(d))
      .catch(() => !cancelled && setFailed(true))
    return () => {
      cancelled = true
    }
  }, [symbol, period])

  return (
    <div className="price-chart">
      <div className="card-head">
        <strong>{symbol} · daily closing price</strong>
        <span className="period-buttons">
          {PERIODS.map((p) => (
            <button key={p} className={`btn small ${p === period ? 'active' : ''}`} onClick={() => setPeriod(p)}>
              {p}
            </button>
          ))}
        </span>
      </div>
      {failed ? (
        <p className="muted small">Couldn't load the price history. Try again in a moment.</p>
      ) : !data ? (
        <p className="muted small">Loading…</p>
      ) : !data.available ? (
        <p className="muted small">Price charts aren't set up yet.</p>
      ) : data.bars.length < 2 ? (
        <p className="muted small">No price history for this stock yet.</p>
      ) : (
        <>
          <svg viewBox={`0 0 ${WIDTH} ${HEIGHT}`} className="chart" preserveAspectRatio="none" role="img" aria-label={`${symbol} price chart`}>
            <polyline className="line-agent" points={linePoints(data.bars.map((b) => b.close), WIDTH, HEIGHT)} />
            {tradeMarkers(data.bars, data.trades, WIDTH, HEIGHT).map((m, i) => (
              <circle key={i} cx={m.x} cy={m.y} r={6} className={`marker ${m.side}`} vectorEffect="non-scaling-stroke">
                <title>{m.label}</title>
              </circle>
            ))}
          </svg>
          <div className="chart-axis small muted">
            <span>{data.bars[0].day}</span>
            <span>
              Low {formatMoney(data.low, currency)} · High {formatMoney(data.high, currency)}
              {data.trades.length > 0 && ` · ${data.trades.length} agent trade${data.trades.length > 1 ? 's' : ''} marked`}
            </span>
            <span>{data.bars[data.bars.length - 1].day}</span>
          </div>
        </>
      )}
    </div>
  )
}
