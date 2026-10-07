// Turns value history into SVG polyline points for the Home chart (D32, D33).

export interface HistoryPoint {
  at: string
  total_value: string
  benchmark_value: string
}

// Saved history is drawn solid; the live stretch from the last saved point to "now" is drawn
// dashed (empty when there is no now point).
export interface ChartLines {
  portfolio: string
  benchmark: string
  portfolioLive: string
  benchmarkLive: string
  min: number
  max: number
}

export interface Bar {
  day: string
  close: string
}

export interface Trade {
  day: string
  side: 'buy' | 'sell'
  quantity: number
  price: string
}

export interface TradeMarker {
  x: number
  y: number
  side: 'buy' | 'sell'
  label: string
}

// Polyline points for a series of values scaled into a width x height box (watchlist charts, D37).
export function linePoints(values: string[], width: number, height: number): string {
  if (values.length < 2) return ''
  const numbers = values.map(Number)
  const min = Math.min(...numbers)
  const max = Math.max(...numbers)
  const x = (i: number) => (i / (numbers.length - 1)) * width
  const y = (v: number) => (max === min ? height / 2 : height - ((v - min) / (max - min)) * height)
  return numbers.map((v, i) => `${x(i).toFixed(1)},${y(v).toFixed(1)}`).join(' ')
}

// Where to draw the agent's trades on a price chart: on the bar of the trade's day, or the next bar.
export function tradeMarkers(bars: Bar[], trades: Trade[], width: number, height: number): TradeMarker[] {
  if (bars.length < 2) return []
  const closes = bars.map((b) => Number(b.close))
  const min = Math.min(...closes)
  const max = Math.max(...closes)
  const markers: TradeMarker[] = []
  for (const trade of trades) {
    const index = bars.findIndex((b) => b.day >= trade.day)
    if (index < 0) continue
    const value = closes[index]
    markers.push({
      x: (index / (bars.length - 1)) * width,
      y: max === min ? height / 2 : height - ((value - min) / (max - min)) * height,
      side: trade.side,
      label: `Agent ${trade.side === 'buy' ? 'bought' : 'sold'} ${trade.quantity}`,
    })
  }
  return markers
}

// Both lines share one scale so they are comparable; points are evenly spaced. The live "now"
// point (D32), when there is one, is the last slot and counts towards the scale.
function valueScale(points: HistoryPoint[], now: HistoryPoint | null, width: number, height: number) {
  const all = now ? [...points, now] : points
  const portfolio = all.map((p) => Number(p.total_value))
  const benchmark = all.map((p) => Number(p.benchmark_value))
  const min = Math.min(...portfolio, ...benchmark)
  const max = Math.max(...portfolio, ...benchmark)
  const x = (i: number) => (i / (all.length - 1)) * width
  const y = (v: number) => (max === min ? height / 2 : height - ((v - min) / (max - min)) * height)
  return { count: all.length, portfolio, benchmark, min, max, x, y }
}

export function chartLines(
  points: HistoryPoint[],
  width: number,
  height: number,
  now: HistoryPoint | null = null,
): ChartLines | null {
  if (points.length === 0) return null
  const { count, portfolio, benchmark, min, max, x, y } = valueScale(points, now, width, height)
  if (count < 2) return null
  const line = (values: number[], from: number, to: number) =>
    values.slice(from, to).map((v, i) => `${x(from + i).toFixed(1)},${y(v).toFixed(1)}`).join(' ')
  const saved = points.length
  return {
    portfolio: saved > 1 ? line(portfolio, 0, saved) : '',
    benchmark: saved > 1 ? line(benchmark, 0, saved) : '',
    portfolioLive: now ? line(portfolio, saved - 1, saved + 1) : '',
    benchmarkLive: now ? line(benchmark, saved - 1, saved + 1) : '',
    min,
    max,
  }
}

export interface RunOrder {
  side: 'buy' | 'sell'
  quantity: number
  symbol: string
  price: string
}

export interface RunTrades {
  run_id: string
  at: string
  orders: RunOrder[]
}

export interface ValueMarker {
  x: number
  y: number
  side: 'buy' | 'sell' | 'mixed'
  runId: string
  at: string
  orders: RunOrder[]
}

// Where to mark a run's trades on the Home chart (D32): on the agent line, at the first
// value point recorded at or after the run started (a point is recorded after every run, D33).
// Only saved points get markers; the now point only takes part in the scale.
export function valueMarkers(
  points: HistoryPoint[],
  runs: RunTrades[],
  width: number,
  height: number,
  now: HistoryPoint | null = null,
): ValueMarker[] {
  if (points.length === 0) return []
  const { count, portfolio, x, y } = valueScale(points, now, width, height)
  if (count < 2) return []
  const times = points.map((p) => Date.parse(p.at))
  // Runs landing on the same point (one point per day on longer periods) share one marker
  // listing all their trades; a click opens the first of them.
  const byIndex = new Map<number, ValueMarker>()
  for (const run of runs) {
    const index = times.findIndex((t) => t >= Date.parse(run.at))
    if (index < 0 || run.orders.length === 0) continue
    const existing = byIndex.get(index)
    const orders = existing ? [...existing.orders, ...run.orders] : run.orders
    const sides = new Set(orders.map((o) => o.side))
    byIndex.set(index, {
      x: x(index),
      y: y(portfolio[index]),
      side: sides.size > 1 ? 'mixed' : orders[0].side,
      runId: existing?.runId ?? run.run_id,
      at: existing?.at ?? run.at,
      orders,
    })
  }
  return [...byIndex.values()]
}

// Home chart periods (D32): 1W shows every run, the others one point per trading day.
export type HomePeriod = '1W' | '1M' | '3M' | 'ALL'

// The point a hover position snaps to: `fraction` is how far across the chart (0 to 1).
export function nearestIndex(fraction: number, count: number): number {
  return Math.min(count - 1, Math.max(0, Math.round(fraction * (count - 1))))
}

export interface Readout {
  at: string
  isNow: boolean
  agentValue: string
  benchmarkValue: string
  agentReturn: string // percent since start, like the Home numbers
  benchmarkReturn: string
}

const percentChange = (from: number, to: number) => (((to - from) / from) * 100).toFixed(2)

// What the hover box shows at a chart slot. The benchmark line is already "the starting capital
// in SPY", so its return since start is measured against the starting capital too.
export function readoutAt(points: HistoryPoint[], now: HistoryPoint | null, index: number, startingCapital: string): Readout {
  const all = now ? [...points, now] : points
  const point = all[index]
  const capital = Number(startingCapital)
  return {
    at: point.at,
    isNow: now !== null && index === all.length - 1,
    agentValue: point.total_value,
    benchmarkValue: point.benchmark_value,
    agentReturn: percentChange(capital, Number(point.total_value)),
    benchmarkReturn: percentChange(capital, Number(point.benchmark_value)),
  }
}

// Each line's change over the shown period, from its first point to its last (now included).
export function periodChange(points: HistoryPoint[], now: HistoryPoint | null): { agent: string; benchmark: string } | null {
  const all = now ? [...points, now] : points
  if (all.length < 2) return null
  const [first, last] = [all[0], all[all.length - 1]]
  return {
    agent: percentChange(Number(first.total_value), Number(last.total_value)),
    benchmark: percentChange(Number(first.benchmark_value), Number(last.benchmark_value)),
  }
}
