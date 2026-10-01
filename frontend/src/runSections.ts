// How an open Decision log run is laid out (D31): each order with the research on its stock, the rest folded away.
import type { Finding, OrderRow, Run } from './api'

export interface OrderWithEvidence {
  order: OrderRow
  evidence: Finding[]
}

export interface RunSections {
  decision: Finding | undefined
  market: Finding | undefined
  orders: OrderWithEvidence[]
  other: Finding[]
}

export function runSections(run: Pick<Run, 'findings' | 'orders'>): RunSections {
  const decision = run.findings.find((f) => f.symbol === 'OVERALL')
  const market = run.findings.find((f) => f.symbol === 'MARKET')
  const research = run.findings.filter((f) => f !== decision && f !== market)

  // A stock traded twice in one run shows its research under the first order only.
  const shown = new Set<string>()
  const orders = run.orders.map((order) => {
    const evidence = shown.has(order.symbol) ? [] : research.filter((f) => f.symbol === order.symbol)
    shown.add(order.symbol)
    return { order, evidence }
  })

  const other = research.filter((f) => !shown.has(f.symbol)).sort(byDayChange)
  return { decision, market, orders, other }
}

// Biggest fall first; stocks with no saved quote keep their order at the end.
function byDayChange(a: Finding, b: Finding): number {
  if (a.change_percent === null || b.change_percent === null) {
    return Number(a.change_percent === null) - Number(b.change_percent === null)
  }
  return Number(a.change_percent) - Number(b.change_percent)
}
