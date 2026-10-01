import { useEffect } from 'react'
import type { Scorecard, StrategyPage, StrategyReviewEntry } from '../api'
import { comparisonText, formatDateTime, formatMoney, formatPercent, formatUsdCost, signClass, tokens } from '../format'
import { closedTradeSummary, followedTone, resultLabel, reviewHint, targetsLabel, targetsTone } from '../strategy'

// Strategy tab (D44): review bar, the current version's results so far, the strategy, and the review history.

interface Props {
  page: StrategyPage | null
  currency: string
  timezone: string
  disabled: boolean // a run is in progress or no AI key
  onReview: () => void
  focusVersion?: number | null // from a run's strategy tag: open the review that wrote this version
}

const TRIGGERS = { button: 'Button', scheduled: 'Scheduled', automatic: 'Automatic' }

export function StrategyView({ page, currency, timezone, disabled, onReview, focusVersion = null }: Props) {
  useEffect(() => {
    if (focusVersion) document.getElementById(`review-v${focusVersion}`)?.scrollIntoView({ block: 'start' })
  }, [focusVersion, page])

  if (!page) return <div className="card"><div className="empty">Loading…</div></div>
  const { current, timing } = page

  if (!current) {
    return (
      <div className="card empty-state">
        <h2>No strategy yet</h2>
        <p>
          The Trading Agent writes its own strategy before it trades, from its goal (beat the S&amp;P 500), the trading
          rules, the watchlist and the latest market overview.
        </p>
        <button className="btn primary" disabled={disabled} onClick={onReview}>Write first strategy</button>
      </div>
    )
  }

  const tooEarly = !timing.can_review
  return (
    <>
      <div className="card">
        <div className="review-bar">
          <div>
            <div className="title">Strategy v{current.number}</div>
            <div className="muted small">In use since {formatDateTime(current.started_at)} · written by the Trading Agent</div>
          </div>
          <span className="grow" />
          <div className="review-hint">
            {reviewHint(timing, timezone).map((line) => <div key={line}>{line}</div>)}
          </div>
          <button
            className="btn primary"
            disabled={disabled || tooEarly}
            title={tooEarly ? `A version must run ${timing.min_trading_days} trading days and ${timing.min_trading_runs} runs before a review` : 'Ask the Trading Agent to review its strategy now'}
            onClick={onReview}
          >
            Review strategy
          </button>
        </div>
        <div className="progress">
          <Meter label="Trading days" done={timing.trading_days} needed={timing.min_trading_days} />
          <Meter label="Trading runs" done={timing.trading_runs} needed={timing.min_trading_runs} />
        </div>
      </div>

      {page.scorecard && <ScoreTiles card={page.scorecard} version={current.number} currency={currency} />}

      <div className="card">
        <div className="card-head">
          <h2>Current strategy</h2>
          {current.number > 1 && <span className="small muted">Changes from v{current.number - 1} are marked</span>}
        </div>
        {current.sections.map((s) => (
          <div key={s.key} className={`section ${s.key === 'targets' ? 'targets' : ''}`}>
            <div className="name">
              {s.title}
              {s.changed && <div><span className="badge changed">changed in v{current.number}</span></div>}
            </div>
            <div>
              <p className="voice">{s.text}</p>
              {s.changed && s.changed_why && <div className="why">Why: {s.changed_why}</div>}
              {s.key === 'targets' && <div className="why">Checked against the scorecard at the next review.</div>}
            </div>
          </div>
        ))}
      </div>

      <div className="card">
        <div className="card-head">
          <h2>Review history</h2>
          <span className="small muted">Newest first · click a row to open</span>
        </div>
        {page.reviews.map((entry, i) => (
          <ReviewRow
            key={entry.id}
            entry={entry}
            currency={currency}
            open={focusVersion ? entry.written_version === focusVersion : i === 0}
          />
        ))}
      </div>
    </>
  )
}

function Meter({ label, done, needed }: { label: string; done: number; needed: number }) {
  const met = done >= needed
  return (
    <span className={`meter ${met ? 'done' : ''}`}>
      <span>{label}</span>
      <span className="track"><span className="fill" style={{ width: `${Math.min(100, (done / needed) * 100)}%` }} /></span>
      <b>{done} / {needed}</b>
    </span>
  )
}

function ScoreTiles({ card, version, currency }: { card: Scorecard; version: number; currency: string }) {
  const closed = closedTradeSummary(card.closed_trades)
  const gap = comparisonText(card.portfolio_percent, card.benchmark_percent, 'S&P 500')
  return (
    <div className="kpis">
      <div className="kpi">
        <div className="label">Return since v{version}</div>
        <div className={`value ${signClass(card.portfolio_percent)}`}>{formatPercent(card.portfolio_percent)}</div>
        <div className="sub">S&amp;P 500 {formatPercent(card.benchmark_percent)} · {gap}</div>
      </div>
      <div className="kpi">
        <div className="label">Trades</div>
        <div className="value">{card.trades}</div>
        <div className="sub">in {card.trading_runs} runs · {formatMoney(card.fees, currency)} fees</div>
      </div>
      <div className="kpi">
        <div className="label">Closed trades</div>
        <div className="value">{closed.won} won · {closed.lost} lost</div>
        <div className="sub">
          <span className="up">{formatMoney(closed.gained, currency)}</span> ·{' '}
          <span className="down">{formatMoney(closed.lostAmount, currency)}</span>
        </div>
      </div>
      <div className="kpi">
        <div className="label">Followed the strategy</div>
        <div className="value">{card.followed_orders} of {card.trades}</div>
        <div className="sub">
          {card.deviations} deviation{card.deviations === 1 ? '' : 's'} · avg cash {Number(card.average_cash_percent).toFixed(0)}%
        </div>
      </div>
    </div>
  )
}

function ReviewRow({ entry, currency, open }: { entry: StrategyReviewEntry; currency: string; open: boolean }) {
  const failed = entry.status === 'failed'
  return (
    <details className="run" open={open} id={entry.written_version ? `review-v${entry.written_version}` : undefined}>
      <summary>
        <span className="when">{formatDateTime(entry.started_at)}</span>
        <span className="badge">{TRIGGERS[entry.trigger]}</span>
        <span className={`badge ${failed ? 'failed' : entry.decision === 'keep' ? '' : 'changed'}`}>{resultLabel(entry)}</span>
        <span className="grow" />
        {entry.targets_verdict && (
          <span className={`badge ${targetsTone(entry.targets_verdict)}`}>Targets: {targetsLabel(entry.targets_verdict)}</span>
        )}
        {entry.followed && <span className={`badge ${followedTone(entry.followed)}`}>Followed: {entry.followed}</span>}
      </summary>
      <div className="body">
        {failed ? (
          <>
            <h3>Why it failed</h3>
            <p className="small">{entry.failure_reason}. The strategy was left as it was.</p>
          </>
        ) : (
          <>
            <h3>Reason</h3>
            <p className="voice">{entry.reason}</p>
          </>
        )}
        {entry.targets_verdict && (
          <>
            <h3>Verdict on v{entry.reviewed_version}'s targets</h3>
            <p className="small">{capitalise(targetsLabel(entry.targets_verdict))}{entry.targets_note && `: ${entry.targets_note}`}</p>
          </>
        )}
        {entry.followed && (
          <>
            <h3>Was it followed?</h3>
            <p className="small">{capitalise(entry.followed)}{entry.followed_note && `: ${entry.followed_note}`}</p>
          </>
        )}
        {entry.changes.length > 0 && (
          <>
            <h3>What changed</h3>
            {entry.changes.map((c) => (
              <div key={c.key} className="change">
                <b className="small">{c.title}</b>
                <div className="from">{c.old}</div>
                <div className="to">{c.new}</div>
                {c.why && <div className="why">{c.why}</div>}
              </div>
            ))}
          </>
        )}
        {entry.scorecard && <ShownScorecard card={entry.scorecard} version={entry.reviewed_version} currency={currency} />}
        <div className="cost">
          {entry.cost.model && <span>Model {entry.cost.model}</span>}
          <span>{tokens(entry.cost.input_tokens)} tokens in / {tokens(entry.cost.output_tokens)} out</span>
          <span>≈ {formatUsdCost(entry.cost.estimated_usd)}</span>
          {entry.trace_url && <a href={entry.trace_url} target="_blank" rel="noreferrer">View trace</a>}
        </div>
      </div>
    </details>
  )
}

function ShownScorecard({ card, version, currency }: { card: Scorecard; version: number | null; currency: string }) {
  const closed = closedTradeSummary(card.closed_trades)
  return (
    <>
      <h3>
        Scorecard shown to the agent (v{version}, {formatDateTime(card.period_start)} – {formatDateTime(card.period_end)})
      </h3>
      <div className="score">
        <div><span>Return vs S&amp;P 500</span><b className={signClass(card.portfolio_percent)}>{formatPercent(card.portfolio_percent)}</b> vs {formatPercent(card.benchmark_percent)}</div>
        <div><span>Runs · trades</span>{card.trading_runs} · {card.trades}</div>
        <div><span>Fees</span>{formatMoney(card.fees, currency)}</div>
        <div><span>Closed trades</span>{closed.won} won · {closed.lost} lost</div>
        <div><span>Average cash</span>{Number(card.average_cash_percent).toFixed(0)}%</div>
        <div><span>Followed · deviations</span>{card.followed_orders} · {card.deviations}</div>
      </div>
    </>
  )
}

function capitalise(text: string): string {
  return text.charAt(0).toUpperCase() + text.slice(1)
}
