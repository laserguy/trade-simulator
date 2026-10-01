// Display logic for the Strategy tab (D44).
import type { StrategyReviewEntry, StrategyTiming } from './api'
import { formatExchangeTime } from './format'

export type Tone = 'good' | 'mid' | 'bad'

// The lines under the "Review strategy" button: when a review becomes possible, and the next scheduled one.
export function reviewHint(timing: StrategyTiming, timeZone: string): string[] {
  const lines: string[] = []
  const runsShort = timing.min_trading_runs - timing.trading_runs
  const daysShort = timing.trading_days < timing.min_trading_days
  const runs = `${runsShort} more trading run${runsShort === 1 ? '' : 's'}`
  if (timing.can_review) lines.push('Minimum period met')
  else if (daysShort && timing.days_met_at) {
    const from = `Review possible from ${formatExchangeTime(timing.days_met_at, timeZone)}`
    lines.push(runsShort > 0 ? `${from}, after ${runs}` : from)
  } else lines.push(`Needs ${runs}`)
  if (timing.next_scheduled) lines.push(`Scheduled review: ${formatExchangeTime(timing.next_scheduled, timeZone)}`)
  return lines
}

export function resultLabel(entry: StrategyReviewEntry): string {
  if (entry.status === 'failed') return 'Failed'
  if (entry.decision === 'first') return `First strategy · v${entry.written_version}`
  if (entry.decision === 'keep') return `Kept v${entry.reviewed_version}`
  return `v${entry.reviewed_version} → v${entry.written_version}`
}

const TONES: Record<string, Tone> = { met: 'good', partly_met: 'mid', missed: 'bad', yes: 'good', partly: 'mid', no: 'bad' }

export const targetsTone = (verdict: string): Tone => TONES[verdict]
export const followedTone = (verdict: string): Tone => TONES[verdict]
export const targetsLabel = (verdict: string): string => verdict.replace('_', ' ')

export function closedTradeSummary(trades: { symbol: string; gain: string }[]) {
  const gains = trades.map((t) => Number(t.gain))
  const won = gains.filter((g) => g > 0)
  const lost = gains.filter((g) => g <= 0)
  const sum = (values: number[]) => values.reduce((a, b) => a + b, 0).toFixed(2)
  return { won: won.length, lost: lost.length, gained: sum(won), lostAmount: sum(lost) }
}
