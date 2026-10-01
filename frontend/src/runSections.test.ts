import { describe, expect, it } from 'vitest'
import type { Finding, OrderRow } from './api'
import { runSections } from './runSections'

const finding = (symbol: string, summary = `${symbol} facts`, change_percent: string | null = null): Finding => ({
  symbol,
  summary,
  sources: [],
  warnings: [],
  price: change_percent === null ? null : '100',
  change_percent,
})
const order = (symbol: string, side: OrderRow['side'] = 'buy'): OrderRow => ({
  symbol,
  side,
  quantity: 1,
  reason: 'Because',
  status: 'executed',
  price: '100',
  fee: '1',
  rejection_reason: null,
  follows: null,
  follows_label: null,
})

describe('runSections', () => {
  it('puts each order with the research on its stock, and the rest under other', () => {
    const wmt = finding('WMT')
    const msft = finding('MSFT')
    const sections = runSections({ findings: [finding('OVERALL'), finding('MARKET'), msft, wmt], orders: [order('WMT')] })

    expect(sections.orders).toEqual([{ order: order('WMT'), evidence: [wmt] }])
    expect(sections.other).toEqual([msft])
  })

  it('separates the decision summary and the market overview', () => {
    const sections = runSections({ findings: [finding('OVERALL', 'Holding.'), finding('MARKET', 'Oil up.')], orders: [] })

    expect(sections.decision?.summary).toBe('Holding.')
    expect(sections.market?.summary).toBe('Oil up.')
    expect(sections.other).toEqual([])
  })

  it('keeps all research under other when the agent held', () => {
    const sections = runSections({ findings: [finding('OVERALL'), finding('NVDA'), finding('XOM')], orders: [] })

    expect(sections.orders).toEqual([])
    expect(sections.other.map((f) => f.symbol)).toEqual(['NVDA', 'XOM'])
  })

  it('shows every finding on a traded stock, and an order with no research has no evidence', () => {
    const first = finding('NVDA', 'First look')
    const second = finding('NVDA', 'Follow-up')
    const sections = runSections({ findings: [first, second], orders: [order('NVDA'), order('AAPL', 'sell')] })

    expect(sections.orders[0].evidence).toEqual([first, second])
    expect(sections.orders[1].evidence).toEqual([])
    expect(sections.other).toEqual([])
  })

  it('shows the research once when a stock has two orders', () => {
    const nvda = finding('NVDA')
    const sections = runSections({ findings: [nvda], orders: [order('NVDA', 'sell'), order('NVDA')] })

    expect(sections.orders[0].evidence).toEqual([nvda])
    expect(sections.orders[1].evidence).toEqual([])
  })

  it('sorts the other stocks from the biggest fall to the biggest rise, with unquoted ones last', () => {
    const findings = [finding('LLY', 'l', '0.3'), finding('OLD'), finding('META', 'm', '-4.12'), finding('MSFT', 'm', '-1.4')]

    expect(runSections({ findings, orders: [] }).other.map((f) => f.symbol)).toEqual(['META', 'MSFT', 'LLY', 'OLD'])
  })
})
