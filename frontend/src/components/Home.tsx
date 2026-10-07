import { useState } from 'react'
import type { HomePeriod, Portfolio, Run, ValueHistory } from '../api'
import { chartLines, nearestIndex, periodChange, readoutAt, valueMarkers, type Readout, type ValueMarker } from '../chart'
import { comparisonText, formatDateTime, formatMoney, formatPercent, periodResultText, signClass } from '../format'

// Home (D32): key numbers, value chart vs the benchmark, the agent's latest decision, compact holdings.

interface Props {
  portfolio: Portfolio | null
  history: ValueHistory
  period: HomePeriod
  onPeriod: (period: HomePeriod) => void
  runs: Run[]
  running: boolean
  onOpenLog: (runId?: string) => void
}

export function Home({ portfolio, history, period, onPeriod, runs, running, onOpenLog }: Props) {
  if (!portfolio) return <p className="muted">Loading…</p>
  const { currency } = portfolio
  const latest = runs.find((r) => r.trigger !== 'refresh')

  return (
    <>
      <div className="kpis">
        <div className="kpi">
          <div className="label">Total value</div>
          <div className="value num">{formatMoney(portfolio.total_value, currency)}</div>
          <div className="sub">Started with {formatMoney(portfolio.starting_capital, currency)}</div>
        </div>
        <div className="kpi">
          <div className="label">Agent return</div>
          <div className={`value num ${signClass(portfolio.return_percent)}`}>{formatPercent(portfolio.return_percent)}</div>
          <div className="sub">
            {comparisonText(portfolio.return_percent, portfolio.benchmark_return_percent, portfolio.benchmark_symbol)}
          </div>
        </div>
        <div className="kpi">
          <div className="label">S&amp;P 500 ({portfolio.benchmark_symbol}), same period</div>
          <div className={`value num ${signClass(portfolio.benchmark_return_percent)}`}>
            {formatPercent(portfolio.benchmark_return_percent)}
          </div>
          <div className="sub">Since {formatDateTime(portfolio.tracking_since)}</div>
        </div>
      </div>

      <ValueChart
        history={history}
        period={period}
        onPeriod={onPeriod}
        currency={currency}
        benchmark={portfolio.benchmark_symbol}
        startingCapital={portfolio.starting_capital}
        onOpenRun={onOpenLog}
      />

      <div className="home-grid">
        <div className="card">
          <div className="card-head">
            <h2>Agent's latest decision</h2>
            {latest && <span className="muted small">{formatDateTime(latest.started_at)}</span>}
          </div>
          {running ? (
            <p className="muted">The agents are working right now. <a href="#" onClick={() => onOpenLog()}>Follow along in the Decision log</a></p>
          ) : !latest ? (
            <p className="muted">No decisions yet. Use “Run now” during market hours.</p>
          ) : (
            <LatestDecision run={latest} currency={currency} />
          )}
          {latest && !running && (
            <a href="#" className="small" onClick={() => onOpenLog()}>Full decision log →</a>
          )}
        </div>

        <div className="card">
          <div className="card-head">
            <h2>Holdings</h2>
            <span className="muted small">Cash {formatMoney(portfolio.cash, currency)}</span>
          </div>
          {portfolio.positions.length === 0 ? (
            <p className="muted">No holdings yet.</p>
          ) : (
            <table>
              <tbody>
                {portfolio.positions.map((p) => (
                  <tr key={p.symbol}>
                    <td><strong>{p.symbol}</strong></td>
                    <td className="r num">{p.quantity}</td>
                    <td className="r num">{formatMoney(p.market_value, currency)}</td>
                    <td className={`r num ${signClass(p.unrealized_pnl)}`}>{formatMoney(p.unrealized_pnl, currency)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>
    </>
  )
}

function LatestDecision({ run, currency }: { run: Run; currency: string }) {
  if (run.status === 'failed') return <p className="down">Run failed: {run.failure_reason}</p>
  const summary = run.findings.find((f) => f.symbol === 'OVERALL')?.summary
  const warnings = run.findings.flatMap((f) => f.warnings.map((w) => `${f.symbol}: ${w}`))
  return (
    <>
      {summary && <p className="voice">“{summary}”</p>}
      {run.orders.length === 0 ? (
        <p className="muted small">No trades this run.</p>
      ) : (
        <ul className="plain">
          {run.orders.map((o, i) => (
            <li key={i}>
              <span className={o.side === 'buy' ? 'up' : 'down'}>{o.side.toUpperCase()}</span> {o.quantity} {o.symbol} ·{' '}
              {o.status === 'executed' ? (
                <span className="muted">executed {formatMoney(o.price, currency)}</span>
              ) : (
                <span className="down">rejected</span>
              )}
            </li>
          ))}
        </ul>
      )}
      {warnings.map((w, i) => (
        <div key={i}><span className="warning">⚠ {w}</span></div>
      ))}
    </>
  )
}

interface ValueChartProps {
  history: ValueHistory
  period: HomePeriod
  onPeriod: (period: HomePeriod) => void
  currency: string
  benchmark: string
  startingCapital: string
  onOpenRun: (runId: string) => void
}

const PERIODS: HomePeriod[] = ['1W', '1M', '3M', 'ALL']
const PERIOD_BUTTON: Record<HomePeriod, string> = { '1W': '1W', '1M': '1M', '3M': '3M', ALL: 'All' }

function ValueChart({ history: { points, now, trades }, period, onPeriod, currency, benchmark, startingCapital, onOpenRun }: ValueChartProps) {
  const [hover, setHover] = useState<number | null>(null)
  const width = 600
  const height = 150
  const lines = chartLines(points, width, height, now)
  const markers = valueMarkers(points, trades, width, height, now)
  const change = periodChange(points, now)
  const count = points.length + (now ? 1 : 0)

  // Hover (or touch) anywhere snaps to the nearest point (D32).
  const track = (event: React.PointerEvent<HTMLDivElement>) => {
    const box = event.currentTarget.getBoundingClientRect()
    setHover(nearestIndex((event.clientX - box.left) / box.width, count))
  }

  return (
    <div className="card">
      <div className="card-head">
        <h2>Portfolio value vs S&amp;P 500</h2>
        <span className="legend small">
          <span className="swatch agent" /> Agent <span className="swatch bench" /> {benchmark}
        </span>
      </div>
      <div className="chart-controls">
        <span className="period-buttons">
          {PERIODS.map((p) => (
            <button key={p} className={`btn small ${p === period ? 'active' : ''}`} onClick={() => onPeriod(p)}>
              {PERIOD_BUTTON[p]}
            </button>
          ))}
        </span>
        {change && <span className="small muted">{periodResultText(period, change, benchmark)}</span>}
      </div>
      {!lines ? (
        <p className="muted">
          {period === 'ALL'
            ? 'The chart fills in as runs happen: a point is added after every run.'
            : 'No runs in this period yet. Try a longer period.'}
        </p>
      ) : (
        <>
          {/* Markers and the hover readout are HTML over the stretched SVG so they stay round and can be clicked. */}
          <div className="chart-wrap" onPointerMove={track} onPointerDown={track} onPointerLeave={() => setHover(null)}>
            <svg viewBox={`0 0 ${width} ${height}`} className="chart" preserveAspectRatio="none" role="img" aria-label="Portfolio value compared with the S&P 500">
              <polyline className="line-bench" points={lines.benchmark} />
              <polyline className="line-agent" points={lines.portfolio} />
              {/* The stretch to "now" is dashed: it moves with live prices and isn't saved (D32). */}
              <polyline className="line-bench live" points={lines.benchmarkLive} />
              <polyline className="line-agent live" points={lines.portfolioLive} />
            </svg>
            {markers.map((m) => (
              <button
                key={m.runId}
                className={`value-marker ${m.side}`}
                style={{ left: `${(m.x / width) * 100}%`, top: `${(m.y / height) * 100}%` }}
                aria-label={markerText(m, currency)}
                onClick={() => onOpenRun(m.runId)}
              />
            ))}
            {hover !== null && hover < count && (
              <HoverReadout
                readout={readoutAt(points, now, hover, startingCapital)}
                left={(hover / (count - 1)) * 100}
                marker={markers.find((m) => Math.abs(m.x - (hover / (count - 1)) * width) < 0.5)}
                currency={currency}
                benchmark={benchmark}
              />
            )}
          </div>
          <div className="chart-axis small muted">
            <span>{formatDateTime(points[0].at)}</span>
            <span>
              {formatMoney(String(lines.min), currency)} – {formatMoney(String(lines.max), currency)}
            </span>
            <span>{now ? 'Now' : formatDateTime(points[points.length - 1].at)}</span>
          </div>
        </>
      )}
    </div>
  )
}

interface HoverReadoutProps {
  readout: Readout
  left: number // percent across the chart
  marker: ValueMarker | undefined
  currency: string
  benchmark: string
}

function HoverReadout({ readout, left, marker, currency, benchmark }: HoverReadoutProps) {
  return (
    <>
      <div className="hover-line" style={{ left: `${left}%` }} />
      {/* The box sits on the side of the line with more room. */}
      <div className={`readout small ${left > 60 ? 'flip' : ''}`} style={{ left: `${left}%` }}>
        <div className="readout-head">{readout.isNow ? 'Now' : formatDateTime(readout.at)}</div>
        <div className="readout-row">
          <span>Agent</span>
          <span className="num">{formatMoney(readout.agentValue, currency)}</span>
          <span className={`num ${signClass(readout.agentReturn)}`}>{formatPercent(readout.agentReturn)}</span>
        </div>
        <div className="readout-row">
          <span>{benchmark}</span>
          <span className="num">{formatMoney(readout.benchmarkValue, currency)}</span>
          <span className={`num ${signClass(readout.benchmarkReturn)}`}>{formatPercent(readout.benchmarkReturn)}</span>
        </div>
        <div className="muted">{comparisonText(readout.agentReturn, readout.benchmarkReturn, benchmark)}</div>
        {marker && (
          <ul className="plain readout-trades">
            {marker.orders.map((o, i) => (
              <li key={i}>
                <span className={o.side === 'buy' ? 'up' : 'down'}>{o.side.toUpperCase()}</span> {o.quantity} {o.symbol} @{' '}
                {formatMoney(o.price, currency)}
              </li>
            ))}
            <li className="muted">Click the dot to open in the Decision log</li>
          </ul>
        )}
      </div>
    </>
  )
}

function markerText(marker: ValueMarker, currency: string): string {
  const orders = marker.orders.map(
    (o) => `${o.side.toUpperCase()} ${o.quantity} ${o.symbol} @ ${formatMoney(o.price, currency)}`,
  )
  return [formatDateTime(marker.at), ...orders, 'Click to open in the Decision log'].join('\n')
}
