// Typed client for the FastAPI backend (backend/src/trade_simulator/adapters/web/api.py).
import type { Bar, HistoryPoint, RunTrades, Trade } from './chart'

export type { HistoryPoint, RunTrades }

// Value chart points and each run's executed trades, for the Home chart's markers (D32, D33).
export interface ValueHistory {
  points: HistoryPoint[]
  trades: RunTrades[]
}

export interface Status {
  market_open: boolean
  next_open: string | null
  run_in_progress: boolean
  exchange: string
  currency: string
  timezone: string
}

export interface PositionRow {
  symbol: string
  quantity: number
  average_cost: string
  price: string | null
  market_value: string | null
  unrealized_pnl: string | null
  weight_percent: string | null
}

export interface Portfolio {
  currency: string
  cash: string
  total_value: string | null
  starting_capital: string
  return_percent: string | null
  benchmark_symbol: string
  benchmark_return_percent: string | null
  tracking_since: string | null
  positions: PositionRow[]
}

export interface WatchlistRow {
  symbol: string
  reason: string
  sources: string[]
  price: string | null
  change_percent: string | null
  held_quantity: number
  trend: string[]
}

export interface Watchlist {
  refreshed_at: string
  charts_available: boolean
  rows: WatchlistRow[]
}

export type ChartPeriod = '1M' | '3M' | '1Y'

export type PriceHistory =
  | { available: false }
  | { available: true; symbol: string; period: ChartPeriod; bars: Bar[]; low: string | null; high: string | null; trades: Trade[] }

export interface ActivityEvent {
  at: string
  actor: string
  text: string
}

export interface Activity {
  active: boolean
  label: string | null
  events: ActivityEvent[]
}

export interface Finding {
  symbol: string
  summary: string
  sources: string[]
  warnings: string[]
  price: string | null // the stock's quote when the agent looked it up; null for older runs and for OVERALL or MARKET
  change_percent: string | null
}

export interface OrderRow {
  symbol: string
  side: 'buy' | 'sell'
  quantity: number
  reason: string
  status: 'executed' | 'rejected'
  price: string | null
  fee: string | null
  rejection_reason: string | null
  follows: string | null // the strategy section it followed, or 'deviation' (D43); null before strategies
  follows_label: string | null
}

export interface Run {
  id: string
  trigger: 'manual' | 'daily' | 'every_15_min' | 'refresh'
  status: 'completed' | 'failed' | 'skipped'
  started_at: string
  finished_at: string | null
  failure_reason: string | null
  findings: Finding[]
  orders: OrderRow[]
  cost: {
    input_tokens: number
    output_tokens: number
    searches: number
    model: string | null
    estimated_usd: string | null
  }
  trace_url: string | null
  strategy_version: number | null // the strategy the run followed (D43)
}

export interface ProviderStatus {
  provider: 'openai' | 'anthropic'
  has_key: boolean
  masked_key: string | null
}

export interface ModelOption {
  provider: string
  model_id: string
  label: string
  input_usd_per_million: string
  output_usd_per_million: string
  note: string
}

export type RunModeId = 'manual' | 'daily' | 'every_15_min'

export interface ModeEstimate {
  mode: RunModeId
  runs_per_month: number | null
  ai_cost_per_run: string
  ai_cost_per_month: string | null
  searches_per_month: number | null
  within_free_allowance: boolean
  allowance_lasts_trading_days: number | null
}

export interface Settings {
  providers: ProviderStatus[]
  models: ModelOption[]
  selected_model_id: string | null
  catalogue_as_of: string
  run_mode: RunModeId
  next_scheduled_run: string | null
  run_mode_estimates: { basis: string; modes: ModeEstimate[] } | null
  trading_rules: TradingRules
}

export interface TradingRules {
  fee_per_trade: string
  max_position_percent: string
}

// The Strategy tab (D43, D44).
export interface StrategySection {
  key: string
  title: string
  text: string
  changed: boolean // differs from the previous version
  changed_why: string
}

export interface StrategyTiming {
  first: boolean
  can_review: boolean
  trading_days: number
  trading_runs: number
  min_trading_days: number
  min_trading_runs: number
  days_met_at: string | null
  next_scheduled: string | null
}

export interface Scorecard {
  period_start: string
  period_end: string
  portfolio_percent: string
  benchmark_percent: string
  trading_runs: number
  trades: number
  fees: string
  closed_trades: { symbol: string; gain: string }[]
  holdings: { symbol: string; gain_percent: string }[]
  average_cash_percent: string
  followed_orders: number
  deviations: number
}

export interface StrategyReviewEntry {
  id: string
  trigger: 'button' | 'scheduled' | 'automatic'
  started_at: string
  status: 'completed' | 'failed'
  failure_reason: string | null
  decision: 'first' | 'keep' | 'change' | null
  reviewed_version: number | null
  written_version: number | null
  reason: string
  targets_verdict: 'met' | 'partly_met' | 'missed' | null
  targets_note: string
  followed: 'yes' | 'partly' | 'no' | null
  followed_note: string
  changes: { key: string; title: string; old: string; new: string; why: string }[]
  scorecard: Scorecard | null
  cost: Run['cost']
  trace_url: string | null
}

export interface StrategyPage {
  current: { number: number; started_at: string; sections: StrategySection[] } | null
  timing: StrategyTiming
  scorecard: Scorecard | null
  reviews: StrategyReviewEntry[]
}

export class ApiError extends Error {
  readonly status: number
  readonly body: Record<string, unknown>

  constructor(status: number, body: Record<string, unknown>) {
    super(typeof body.detail === 'string' ? body.detail : `Request failed (${status})`)
    this.status = status
    this.body = body
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, {
    ...init,
    headers: { 'Content-Type': 'application/json', ...init?.headers },
  })
  const body = await response.json().catch(() => ({}))
  if (!response.ok) throw new ApiError(response.status, body)
  return body as T
}

export const api = {
  status: () => request<Status>('/api/status'),
  portfolio: () => request<Portfolio>('/api/portfolio'),
  watchlist: () => request<Watchlist | null>('/api/watchlist'),
  runs: (limit = 50) => request<Run[]>(`/api/runs?limit=${limit}`),
  history: () => request<ValueHistory>('/api/history'),
  activity: () => request<Activity>('/api/activity'),
  priceHistory: (symbol: string, period: ChartPeriod) =>
    request<PriceHistory>(`/api/price-history/${encodeURIComponent(symbol)}?period=${period}`),
  runNow: () => request<{ status: string }>('/api/runs', { method: 'POST' }),
  refreshWatchlist: () => request<{ status: string }>('/api/watchlist/refresh', { method: 'POST' }),
  strategy: () => request<StrategyPage>('/api/strategy'),
  reviewStrategy: () => request<{ status: string }>('/api/strategy/review', { method: 'POST' }),
  settings: () => request<Settings>('/api/settings'),
  saveKey: (provider: string, apiKey: string | null) =>
    request<Settings>(`/api/settings/keys/${provider}`, {
      method: 'PUT',
      body: JSON.stringify({ api_key: apiKey }),
    }),
  setRunMode: (mode: RunModeId) =>
    request<Settings>('/api/settings/run-mode', { method: 'PUT', body: JSON.stringify({ mode }) }),
  selectModel: (modelId: string) =>
    request<Settings>('/api/settings/model', { method: 'PUT', body: JSON.stringify({ model_id: modelId }) }),
}
