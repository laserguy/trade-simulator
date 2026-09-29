// A decision log run as plain text, for the Copy button (D31). Full source URLs and ISO times, so it pastes well into an AI chat.
import type { Run } from './api'
import { duration, formatMoney, formatUsdCost, tokens } from './format'

export const TRIGGER_LABEL: Record<Run['trigger'], string> = {
  manual: 'Run now',
  daily: 'Daily',
  every_15_min: 'Every 15 min',
  refresh: 'Watchlist refresh',
}

export function runAsText(run: Run, currency: string): string {
  const overall = run.findings.find((f) => f.symbol === 'OVERALL' || f.symbol === 'MARKET')
  const research = run.findings.filter((f) => f !== overall)
  const lines = [
    `Run ${run.started_at} · ${TRIGGER_LABEL[run.trigger]} · ${run.status} · ${duration(run.started_at, run.finished_at)}`,
  ]

  if (run.failure_reason) lines.push('', `Failed: ${run.failure_reason}`)

  if (overall) {
    lines.push('', `${overall.symbol === 'MARKET' ? 'Market overview' : 'Decision summary'}:`, overall.summary)
    if (overall.sources.length > 0) lines.push(`Sources: ${overall.sources.join(' ')}`)
  }

  if (run.trigger !== 'refresh') {
    lines.push('')
    if (run.orders.length === 0) lines.push('Orders: none')
    else {
      lines.push('Orders:')
      for (const o of run.orders) {
        const result =
          o.status === 'executed'
            ? `executed at ${formatMoney(o.price, currency)} + ${formatMoney(o.fee, currency)} fee`
            : `rejected (${o.rejection_reason})`
        lines.push(`- ${o.side.toUpperCase()} ${o.quantity} ${o.symbol}: ${result}. Reason: ${o.reason}`)
      }
    }
  }

  if (research.length > 0) {
    lines.push('', 'Research findings:')
    for (const f of research) {
      lines.push(`- ${f.symbol}: ${f.summary}`)
      for (const w of f.warnings) lines.push(`  Warning: ${w}`)
      if (f.sources.length > 0) lines.push(`  Sources: ${f.sources.join(' ')}`)
    }
  }

  const c = run.cost
  lines.push(
    '',
    `Cost: model ${c.model ?? '—'} · ${tokens(c.input_tokens)} tokens in / ${tokens(c.output_tokens)} out · ` +
      `${c.searches} web searches · est. ${formatUsdCost(c.estimated_usd)}`,
  )
  if (run.trace_url) lines.push(`Trace: ${run.trace_url}`)
  return lines.join('\n')
}
