// Display helpers. The API sends money and percentages as decimal strings to avoid float drift.
import type { HomePeriod } from './chart'

const DASH = '—'

export function formatMoney(value: string | null, currency: string): string {
  if (value === null) return DASH
  return new Intl.NumberFormat('en-US', { style: 'currency', currency }).format(Number(value))
}

export function formatPercent(value: string | null): string {
  if (value === null) return DASH
  const number = Number(value)
  const sign = number > 0 ? '+' : ''
  return `${sign}${number.toFixed(2)}%`
}

export function signClass(value: string | null): '' | 'up' | 'down' {
  if (value === null) return ''
  const number = Number(value)
  return number > 0 ? 'up' : number < 0 ? 'down' : ''
}

// Colour of a price-change chip (D31). A change under 0.05% counts as flat, so -0.01% isn't shown as a fall.
export function moveTone(changePercent: string): 'up' | 'down' | 'flat' {
  const number = Number(changePercent)
  return Math.abs(number) < 0.05 ? 'flat' : number > 0 ? 'up' : 'down'
}

export function comparisonText(agentReturn: string | null, benchmarkReturn: string | null, benchmark: string): string {
  if (agentReturn === null || benchmarkReturn === null) return 'Comparison unavailable'
  const gap = Number(agentReturn) - Number(benchmarkReturn)
  if (Math.abs(gap) < 0.005) return `Level with ${benchmark}`
  return gap > 0
    ? `Ahead of ${benchmark} by ${gap.toFixed(2)} pts`
    : `Behind ${benchmark} by ${Math.abs(gap).toFixed(2)} pts`
}

const PERIOD_NAMES: Record<HomePeriod, string> = {
  '1W': 'Last week',
  '1M': 'Last month',
  '3M': 'Last 3 months',
  ALL: 'Since start',
}

// The line under the Home chart's period buttons (D32).
export function periodResultText(period: HomePeriod, change: { agent: string; benchmark: string }, benchmark: string): string {
  return (
    `${PERIOD_NAMES[period]}: Agent ${formatPercent(change.agent)}, ${benchmark} ${formatPercent(change.benchmark)} · ` +
    comparisonText(change.agent, change.benchmark, benchmark)
  )
}

// Web search is described without naming the provider (D34, D35).
export function allowanceText(withinAllowance: boolean, lastsTradingDays: number | null, searchesPerMonth: number): string {
  const searches = `Up to ${searchesPerMonth.toLocaleString('en-US')} web searches a month`
  if (withinAllowance) return `${searches} · within the free allowance`
  return (
    `${searches} · free allowance runs out after about ${lastsTradingDays} trading days, ` +
    'then research continues without web search until the month resets'
  )
}

// The trading rules (D6) in plain words for the Settings card (D29). Fee and cap come from the backend's enforced values.
export function tradingRuleLines(rules: { fee_per_trade: string; max_position_percent: string }, currency: string): string[] {
  return [
    `${formatMoney(rules.fee_per_trade, currency)} broker fee per trade (buy or sell)`,
    'Whole shares only',
    `At most ${rules.max_position_percent}% of the portfolio in one stock, checked after each buy`,
    'No short selling: only shares you hold can be sold',
    'Buy only watchlist stocks; any stock you hold can be sold',
    'Cash can never go negative, fees included',
    'In each run, sells happen before buys, so their cash can fund the buys',
  ]
}

export function formatUsdCost(value: string | null): string {
  if (value === null) return DASH
  const number = Number(value)
  return number < 0.01 ? `$${number.toFixed(4)}` : `$${number.toFixed(2)}`
}

export function tokens(count: number): string {
  if (count >= 1_000_000) return `${(count / 1_000_000).toFixed(1)}M`
  if (count >= 1_000) return `${(count / 1_000).toFixed(1)}k`
  return String(count)
}

export function formatDateTime(iso: string | null): string {
  if (!iso) return DASH
  return new Date(iso).toLocaleString(undefined, {
    weekday: 'short',
    day: 'numeric',
    month: 'short',
    hour: '2-digit',
    minute: '2-digit',
  })
}

// Market times are shown in the exchange's timezone (e.g. "9:30 AM EDT"), which is how opening times are known.
export function formatExchangeTime(iso: string, timeZone: string): string {
  const parts = new Intl.DateTimeFormat('en-US', {
    timeZone,
    weekday: 'short',
    day: 'numeric',
    month: 'short',
    hour: 'numeric',
    minute: '2-digit',
    timeZoneName: 'short',
  }).formatToParts(new Date(iso))
  const part = (type: Intl.DateTimeFormatPartTypes) => parts.find((p) => p.type === type)?.value ?? ''
  return `${part('weekday')} ${part('day')} ${part('month')}, ${part('hour')}:${part('minute')} ${part('dayPeriod')} ${part('timeZoneName')}`
}

export function duration(startIso: string, endIso: string | null): string {
  if (!endIso) return 'running'
  const seconds = Math.round((new Date(endIso).getTime() - new Date(startIso).getTime()) / 1000)
  return seconds < 60 ? `${seconds}s` : `${Math.floor(seconds / 60)}m ${seconds % 60}s`
}
