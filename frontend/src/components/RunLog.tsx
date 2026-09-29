import { useState } from 'react'
import type { MouseEvent } from 'react'
import type { Finding, Run } from '../api'
import { duration, formatDateTime, formatMoney, formatUsdCost, tokens } from '../format'
import { runAsText, TRIGGER_LABEL } from '../runText'

export function RunLog({ runs, currency }: { runs: Run[]; currency: string }) {
  if (runs.length === 0) {
    return (
      <div className="card">
        <div className="empty">No runs yet. Refresh the watchlist, then use “Run now” during market hours.</div>
      </div>
    )
  }
  return (
    <>
      {runs.map((run, index) => (
        <RunItem key={run.id} run={run} currency={currency} open={index === 0} />
      ))}
    </>
  )
}

function RunItem({ run, currency, open }: { run: Run; currency: string; open: boolean }) {
  const executed = run.orders.filter((o) => o.status === 'executed').length
  const rejected = run.orders.length - executed
  const warnings = run.findings.reduce((n, f) => n + f.warnings.length, 0)
  const overall = run.findings.find((f) => f.symbol === 'OVERALL' || f.symbol === 'MARKET')
  const research = run.findings.filter((f) => f !== overall)

  return (
    <details className="run" open={open}>
      <summary>
        <span className="when">{formatDateTime(run.started_at)}</span>
        <span className="badge">{TRIGGER_LABEL[run.trigger]}</span>
        <span className={`badge ${run.status}`}>{run.status}</span>
        <span className="grow muted">
          {run.trigger === 'refresh'
            ? 'Watchlist rebuilt'
            : run.status === 'completed'
              ? `${executed} executed · ${rejected} rejected`
              : run.failure_reason}
        </span>
        {warnings > 0 && <span className="warning">{warnings} warning{warnings > 1 ? 's' : ''}</span>}
        <span className="muted num">{duration(run.started_at, run.finished_at)}</span>
        <CopyButton text={() => runAsText(run, currency)} />
      </summary>

      <div className="body">
        {run.failure_reason && <div className="banner error" style={{ marginTop: 12 }}>{run.failure_reason}</div>}
        {overall && (
          <>
            <h3>{overall.symbol === 'MARKET' ? 'Market overview' : 'Decision summary'}</h3>
            <p style={{ margin: 0 }}>{overall.summary}</p>
            <SourceLinks sources={overall.sources} />
          </>
        )}

        {run.orders.length > 0 && (
          <>
            <h3>Orders</h3>
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Order</th>
                    <th>Reason</th>
                    <th>Result</th>
                  </tr>
                </thead>
                <tbody>
                  {run.orders.map((o, i) => (
                    <tr key={i}>
                      <td style={{ whiteSpace: 'nowrap' }}>
                        <span className={`badge ${o.side}`}>{o.side.toUpperCase()}</span> {o.quantity} <strong>{o.symbol}</strong>
                      </td>
                      <td>{o.reason}</td>
                      <td>
                        <span className={`badge ${o.status}`}>{o.status}</span>{' '}
                        {o.status === 'executed' ? (
                          <span className="muted num">
                            at {formatMoney(o.price, currency)} + {formatMoney(o.fee, currency)} fee
                          </span>
                        ) : (
                          <span className="muted">{o.rejection_reason}</span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        )}

        {research.length > 0 && (
          <>
            <h3>Research findings</h3>
            {research.map((f, i) => (
              <FindingRow key={i} finding={f} />
            ))}
          </>
        )}

        <div className="cost">
          <span>Model: {run.cost.model ?? '—'}</span>
          <span>
            Tokens: {tokens(run.cost.input_tokens)} in / {tokens(run.cost.output_tokens)} out
          </span>
          <span>Web searches: {run.cost.searches}</span>
          <span>Est. cost: {formatUsdCost(run.cost.estimated_usd)}</span>
          {run.trace_url && (
            <a href={run.trace_url} target="_blank" rel="noreferrer">
              View trace ↗
            </a>
          )}
        </div>
      </div>
    </details>
  )
}

// Sits inside <summary>, so the click must not open or close the row.
function CopyButton({ text }: { text: () => string }) {
  const [label, setLabel] = useState('Copy')
  const copy = async (e: MouseEvent) => {
    e.preventDefault()
    e.stopPropagation()
    try {
      await navigator.clipboard.writeText(text())
      setLabel('Copied ✓')
    } catch {
      setLabel('Copy failed')
    }
    setTimeout(() => setLabel('Copy'), 1500)
  }
  return (
    <button className="btn small" onClick={copy} title="Copy this run as text">
      {label}
    </button>
  )
}

function FindingRow({ finding }: { finding: Finding }) {
  return (
    <div className="finding">
      <span className="sym">{finding.symbol}</span>
      {finding.summary}
      {finding.warnings.map((w, i) => (
        <div key={i}>
          <span className="warning">⚠ {w}</span>
        </div>
      ))}
      <SourceLinks sources={finding.sources} />
    </div>
  )
}

function SourceLinks({ sources }: { sources: string[] }) {
  if (sources.length === 0) return null
  return (
    <div className="sources">
      {sources.map((s, i) => (
        <a key={i} href={s} target="_blank" rel="noreferrer">
          {hostname(s)}
        </a>
      ))}
    </div>
  )
}

function hostname(url: string): string {
  try {
    return new URL(url).hostname.replace(/^www\./, '')
  } catch {
    return url
  }
}
