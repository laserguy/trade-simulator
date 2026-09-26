import type { ModeEstimate, RunModeId, Settings } from '../api'
import { allowanceText, formatExchangeTime, formatUsdCost } from '../format'

// Run mode section of the Settings page (D35): how often the agents decide, and what each option costs.

const MODES: { id: RunModeId; label: string; when: string }[] = [
  { id: 'manual', label: 'Manual', when: 'Only when you click Run now' },
  { id: 'daily', label: 'Daily', when: 'Once at market open' },
  { id: 'every_15_min', label: 'Every 15 min', when: 'Every 15 minutes while the market is open' },
]

interface Props {
  settings: Settings
  timezone: string
  onSelect: (mode: RunModeId) => void
}

export function RunModeSection({ settings, timezone, onSelect }: Props) {
  const estimates = settings.run_mode_estimates
  const model = settings.models.find((m) => m.model_id === settings.selected_model_id)
  return (
    <div className="card">
      <div className="card-head">
        <h2>Run mode</h2>
        {estimates && model && (
          <span className="muted small">
            Estimates for {model.label} · {estimates.basis === 'rough' ? 'rough estimate' : `based on ${estimates.basis}`}
          </span>
        )}
      </div>
      <p className="muted small" style={{ marginTop: 0 }}>
        How often the agents make a trading decision. Runs only happen while the market is open.
      </p>
      <div className="mode-grid">
        {MODES.map((m) => {
          const selected = settings.run_mode === m.id
          const estimate = estimates?.modes.find((e) => e.mode === m.id)
          return (
            <label key={m.id} className={`mode-card ${selected ? 'selected' : ''}`}>
              <span className="mode-title">
                <input type="radio" name="run-mode" checked={selected} onChange={() => onSelect(m.id)} /> {m.label}
              </span>
              <span className="muted small">{m.when}</span>
              {estimate ? <EstimateLines estimate={estimate} /> : <span className="muted small">Add an AI key to see costs</span>}
            </label>
          )
        })}
      </div>
      {settings.next_scheduled_run && (
        <div className="next-run small">
          Next scheduled run: <strong>{formatExchangeTime(settings.next_scheduled_run, timezone)}</strong>
        </div>
      )}
    </div>
  )
}

function EstimateLines({ estimate }: { estimate: ModeEstimate }) {
  if (estimate.mode === 'manual') {
    return <span className="small">AI cost about {formatUsdCost(estimate.ai_cost_per_run)} per run</span>
  }
  return (
    <>
      <span className="small">
        About {estimate.runs_per_month} runs a month · AI cost up to about {formatUsdCost(estimate.ai_cost_per_month)} a month
      </span>
      <span className={`small ${estimate.within_free_allowance ? 'up' : 'warn-text'}`}>
        {allowanceText(estimate.within_free_allowance, estimate.allowance_lasts_trading_days, estimate.searches_per_month ?? 0)}
      </span>
    </>
  )
}
