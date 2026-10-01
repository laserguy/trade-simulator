import { useEffect, useState } from 'react'
import type { MouseEvent } from 'react'
import type { Finding, Run } from '../api'
import { duration, formatDateTime, formatMoney, formatPercent, formatUsdCost, moveTone, tokens } from '../format'
import { runSections } from '../runSections'
import { runAsText, TRIGGER_LABEL } from '../runText'

interface Props {
  runs: Run[]
  currency: string
  openRunId?: string | null
  onOpenStrategy?: (version: number) => void // a run's strategy tag opens that version on the Strategy tab (D31, D44)
}

// `openRunId` expands that run and scrolls to it (a marker on the Home chart, D32); otherwise the newest is open.
export function RunLog({ runs, currency, openRunId = null, onOpenStrategy }: Props) {
  useEffect(() => {
    if (openRunId) document.getElementById(`run-${openRunId}`)?.scrollIntoView({ block: 'start' })
  }, [openRunId])

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
        <RunItem
          key={run.id}
          run={run}
          currency={currency}
          open={openRunId ? run.id === openRunId : index === 0}
          onOpenStrategy={onOpenStrategy}
        />
      ))}
    </>
  )
}

function RunItem({ run, currency, open, onOpenStrategy }: { run: Run; currency: string; open: boolean; onOpenStrategy?: (version: number) => void }) {
  const executed = run.orders.filter((o) => o.status === 'executed').length
  const rejected = run.orders.length - executed
  const warnings = run.findings.reduce((n, f) => n + f.warnings.length, 0)
  const { decision, market, orders, other } = runSections(run)

  return (
    <details className="run" id={`run-${run.id}`} open={open}>
      <summary>
        <span className="when">{formatDateTime(run.started_at)}</span>
        <span className="badge">{TRIGGER_LABEL[run.trigger]}</span>
        <span className={`badge ${run.status}`}>{run.status}</span>
        {run.strategy_version !== null && (
          <button
            className="badge strategy-tag"
            title="Open this strategy version on the Strategy tab"
            onClick={(e) => {
              e.preventDefault() // inside <summary>: don't open or close the row
              e.stopPropagation()
              onOpenStrategy?.(run.strategy_version as number)
            }}
          >
            Strategy v{run.strategy_version}
          </button>
        )}
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
        {decision && (
          <>
            <h3>Decision summary</h3>
            <p style={{ margin: 0 }}>{decision.summary}</p>
            <SourceLinks sources={decision.sources} />
          </>
        )}

        {orders.length > 0 && (
          <>
            <h3>Orders</h3>
            {orders.map(({ order: o, evidence }, i) => (
              <div className={`order ${o.status === 'rejected' ? 'rejected' : o.side}`} key={i}>
                <div className="order-head">
                  <span className={`badge ${o.side}`}>{o.side.toUpperCase()}</span>
                  <span>
                    {o.quantity} <strong>{o.symbol}</strong>
                  </span>
                  <QuoteChip finding={run.findings.find((f) => f.symbol === o.symbol && f.price !== null)} currency={currency} />
                  <span className={`badge ${o.status}`}>{o.status}</span>
                  {o.follows_label && (
                    <span
                      className={`badge ${o.follows === 'deviation' ? 'mid' : ''}`}
                      title={o.follows === 'deviation' ? 'The agent broke its strategy for this order; the reason says why' : 'The strategy section this order follows'}
                    >
                      {o.follows_label}
                    </span>
                  )}
                  {o.status === 'executed' ? (
                    <span className="muted num">
                      at {formatMoney(o.price, currency)} + {formatMoney(o.fee, currency)} fee
                    </span>
                  ) : (
                    <span className="muted">{o.rejection_reason}</span>
                  )}
                </div>
                <div>{o.reason}</div>
                {evidence.map((f, j) => (
                  <div className="evidence" key={j}>
                    <span className="muted">Research: </span>
                    {f.summary}
                    <Warnings warnings={f.warnings} />
                    <SourceLinks sources={f.sources} />
                  </div>
                ))}
              </div>
            ))}
          </>
        )}

        {market && (
          <>
            <h3>Market overview</h3>
            <div className="market">
              {market.summary}
              <Warnings warnings={market.warnings} />
              <SourceLinks sources={market.sources} />
            </div>
          </>
        )}

        {other.length > 0 && (
          <>
            <h3>
              {orders.length > 0 ? 'Other stocks researched' : 'Stocks researched'} ({other.length})
            </h3>
            {other.map((f, i) => (
              <FindingRow key={i} finding={f} currency={currency} />
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

// One line when closed; a finding with a warning starts open so the warning isn't hidden.
function FindingRow({ finding, currency }: { finding: Finding; currency: string }) {
  return (
    <details className="finding" open={finding.warnings.length > 0}>
      <summary>
        <span className="sym">{finding.symbol}</span>
        <QuoteChip finding={finding} currency={currency} />
        {finding.summary}
      </summary>
      <Warnings warnings={finding.warnings} />
      <SourceLinks sources={finding.sources} />
    </details>
  )
}

function Warnings({ warnings }: { warnings: string[] }) {
  return (
    <>
      {warnings.map((w, i) => (
        <div key={i}>
          <span className="warning">⚠ {w}</span>
        </div>
      ))}
    </>
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

// The stock's price and day change when the agent looked it up; nothing for runs saved before these were recorded.
function QuoteChip({ finding, currency }: { finding: Finding | undefined; currency: string }) {
  if (!finding || finding.price === null || finding.change_percent === null) return null
  return (
    <span
      className={`chip num ${moveTone(finding.change_percent)}`}
      title="Price when the agent checked, and its change from the previous day's close."
    >
      <span className="px">{formatMoney(finding.price, currency)}</span>
      {formatPercent(finding.change_percent)}
    </span>
  )
}
