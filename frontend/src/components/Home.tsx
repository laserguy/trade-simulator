import type { HistoryPoint, Portfolio, Run } from '../api'
import { chartLines } from '../chart'
import { comparisonText, formatDateTime, formatMoney, formatPercent, signClass } from '../format'

// Home (D32): key numbers, value chart vs the benchmark, the agent's latest decision, compact holdings.

interface Props {
  portfolio: Portfolio | null
  history: HistoryPoint[]
  runs: Run[]
  running: boolean
  onOpenLog: () => void
}

export function Home({ portfolio, history, runs, running, onOpenLog }: Props) {
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

      <ValueChart history={history} currency={currency} benchmark={portfolio.benchmark_symbol} />

      <div className="home-grid">
        <div className="card">
          <div className="card-head">
            <h2>Agent's latest decision</h2>
            {latest && <span className="muted small">{formatDateTime(latest.started_at)}</span>}
          </div>
          {running ? (
            <p className="muted">The agents are working right now. <a href="#" onClick={onOpenLog}>Follow along in the Decision log</a></p>
          ) : !latest ? (
            <p className="muted">No decisions yet. Use “Run now” during market hours.</p>
          ) : (
            <LatestDecision run={latest} currency={currency} />
          )}
          {latest && !running && (
            <a href="#" className="small" onClick={onOpenLog}>Full decision log →</a>
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

function ValueChart({ history, currency, benchmark }: { history: HistoryPoint[]; currency: string; benchmark: string }) {
  const width = 600
  const height = 150
  const lines = chartLines(history, width, height)
  return (
    <div className="card">
      <div className="card-head">
        <h2>Portfolio value vs S&amp;P 500</h2>
        <span className="legend small">
          <span className="swatch agent" /> Agent <span className="swatch bench" /> {benchmark}
        </span>
      </div>
      {!lines ? (
        <p className="muted">The chart fills in as runs happen: a point is added after every run.</p>
      ) : (
        <>
          <svg viewBox={`0 0 ${width} ${height}`} className="chart" preserveAspectRatio="none" role="img" aria-label="Portfolio value compared with the S&P 500">
            <polyline className="line-bench" points={lines.benchmark} />
            <polyline className="line-agent" points={lines.portfolio} />
          </svg>
          <div className="chart-axis small muted">
            <span>{formatDateTime(history[0].at)}</span>
            <span>
              {formatMoney(String(lines.min), currency)} – {formatMoney(String(lines.max), currency)}
            </span>
            <span>{formatDateTime(history[history.length - 1].at)}</span>
          </div>
        </>
      )}
    </div>
  )
}
