// Turns value history into SVG polyline points for the Home chart (D32, D33).

export interface HistoryPoint {
  at: string
  total_value: string
  benchmark_value: string
}

export interface ChartLines {
  portfolio: string
  benchmark: string
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

// Both lines share one scale so they are comparable; points are evenly spaced.
function valueScale(points: HistoryPoint[], width: number, height: number) {
  const portfolio = points.map((p) => Number(p.total_value))
  const benchmark = points.map((p) => Number(p.benchmark_value))
  const min = Math.min(...portfolio, ...benchmark)
  const max = Math.max(...portfolio, ...benchmark)
  const x = (i: number) => (i / (points.length - 1)) * width
  const y = (v: number) => (max === min ? height / 2 : height - ((v - min) / (max - min)) * height)
  return { portfolio, benchmark, min, max, x, y }
}

export function chartLines(points: HistoryPoint[], width: number, height: number): ChartLines | null {
  if (points.length < 2) return null
  const { portfolio, benchmark, min, max, x, y } = valueScale(points, width, height)
  const line = (values: number[]) => values.map((v, i) => `${x(i).toFixed(1)},${y(v).toFixed(1)}`).join(' ')
  return { portfolio: line(portfolio), benchmark: line(benchmark), min, max }
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
export function valueMarkers(points: HistoryPoint[], runs: RunTrades[], width: number, height: number): ValueMarker[] {
  if (points.length < 2) return []
  const { portfolio, x, y } = valueScale(points, width, height)
  const times = points.map((p) => Date.parse(p.at))
  const markers: ValueMarker[] = []
  for (const run of runs) {
    const index = times.findIndex((t) => t >= Date.parse(run.at))
    if (index < 0 || run.orders.length === 0) continue
    const sides = new Set(run.orders.map((o) => o.side))
    markers.push({
      x: x(index),
      y: y(portfolio[index]),
      side: sides.size > 1 ? 'mixed' : run.orders[0].side,
      runId: run.run_id,
      at: run.at,
      orders: run.orders,
    })
  }
  return markers
}
