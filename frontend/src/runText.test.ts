import { describe, expect, it } from 'vitest'
import type { Run } from './api'
import { runAsText } from './runText'

const baseRun: Run = {
  id: 'run-1',
  trigger: 'manual',
  status: 'completed',
  started_at: '2026-09-28T14:37:00+00:00',
  finished_at: '2026-09-28T14:39:10+00:00',
  failure_reason: null,
  findings: [
    { symbol: 'OVERALL', summary: 'Holding cash.', sources: [], warnings: [], price: null, change_percent: null },
    {
      symbol: 'NVDA',
      summary: 'Jumped with no news.',
      sources: ['https://www.example.com/nvda'],
      warnings: ['Up 9% with no matching news'],
      price: '230.25',
      change_percent: '9.1',
    },
  ],
  orders: [
    { symbol: 'AAPL', side: 'buy', quantity: 3, reason: 'Strong earnings', status: 'executed', price: '200', fee: '1', rejection_reason: null, follows: null, follows_label: null },
    { symbol: 'MSFT', side: 'buy', quantity: 50, reason: 'Momentum', status: 'rejected', price: null, fee: null, rejection_reason: 'Over the 20% cap', follows: null, follows_label: null },
  ],
  cost: { input_tokens: 12300, output_tokens: 4100, searches: 5, model: 'gpt-6-luna', estimated_usd: '0.04' },
  trace_url: 'https://platform.openai.com/traces/trace_1',
  strategy_version: null,
}

describe('runAsText', () => {
  const text = runAsText(baseRun, 'USD')

  it('starts with the header line: time, trigger, status, duration', () => {
    expect(text.split('\n')[0]).toBe('Run 2026-09-28T14:37:00+00:00 · Run now · completed · 2m 10s')
  })

  it('includes the decision summary', () => {
    expect(text).toContain('Decision summary:\nHolding cash.')
  })

  it('lists executed and rejected orders with reasons and results', () => {
    expect(text).toContain('- BUY 3 AAPL: executed at $200.00 + $1.00 fee. Reason: Strong earnings')
    expect(text).toContain('- BUY 50 MSFT: rejected (Over the 20% cap). Reason: Momentum')
  })

  it('includes findings with warnings and full source URLs', () => {
    expect(text).toContain('- NVDA: Jumped with no news.')
    expect(text).toContain('  Warning: Up 9% with no matching news')
    expect(text).toContain('  Sources: https://www.example.com/nvda')
  })

  it('ends with cost and trace link', () => {
    expect(text).toContain('Cost: model gpt-6-luna · 12.3k tokens in / 4.1k out · 5 web searches · est. $0.04')
    expect(text).toContain('Trace: https://platform.openai.com/traces/trace_1')
  })

  it('names the strategy version and the section each order followed', () => {
    const withStrategy = runAsText(
      {
        ...baseRun,
        strategy_version: 3,
        orders: [
          { ...baseRun.orders[0], follows: 'what_i_look_for', follows_label: 'What I look for' },
          { ...baseRun.orders[1], follows: 'deviation', follows_label: 'Deviation' },
        ],
      },
      'USD',
    )
    expect(withStrategy.split('\n')[0]).toBe('Run 2026-09-28T14:37:00+00:00 · Run now · completed · 2m 10s · Strategy v3')
    expect(withStrategy).toContain('- BUY 3 AAPL (What I look for): executed at $200.00 + $1.00 fee. Reason: Strong earnings')
    expect(withStrategy).toContain('- BUY 50 MSFT (Deviation): rejected (Over the 20% cap). Reason: Momentum')
  })

  it('says when there were no orders', () => {
    expect(runAsText({ ...baseRun, orders: [] }, 'USD')).toContain('Orders: none')
  })

  it('includes the failure reason and a market overview heading', () => {
    const failed = runAsText(
      {
        ...baseRun,
        trigger: 'refresh',
        status: 'failed',
        failure_reason: 'Model timed out',
        findings: [{ symbol: 'MARKET', summary: 'Oil shock.', sources: [], warnings: [], price: null, change_percent: null }],
        trace_url: null,
      },
      'USD',
    )
    expect(failed).toContain('Failed: Model timed out')
    expect(failed).toContain('Market overview:\nOil shock.')
    expect(failed).not.toContain('Trace:')
  })
})
