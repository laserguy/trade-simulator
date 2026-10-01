import { describe, expect, it } from 'vitest'
import type { StrategyReviewEntry, StrategyTiming } from './api'
import { closedTradeSummary, followedTone, resultLabel, reviewHint, targetsLabel, targetsTone } from './strategy'

const TZ = 'America/New_York'

function timing(overrides: Partial<StrategyTiming> = {}): StrategyTiming {
  return {
    first: false,
    can_review: false,
    trading_days: 8,
    trading_runs: 5,
    min_trading_days: 10,
    min_trading_runs: 5,
    days_met_at: '2026-10-02T20:00:00+00:00',
    next_scheduled: '2026-10-02T20:15:00+00:00',
    ...overrides,
  }
}

function entry(overrides: Partial<StrategyReviewEntry> = {}): StrategyReviewEntry {
  return {
    id: 'r', trigger: 'scheduled', started_at: '2026-09-12T20:15:00+00:00', status: 'completed', failure_reason: null,
    decision: 'change', reviewed_version: 2, written_version: 3, reason: 'Because.', targets_verdict: 'partly_met',
    targets_note: '', followed: 'partly', followed_note: '', changes: [], scorecard: null,
    cost: { input_tokens: 0, output_tokens: 0, searches: 0, model: null, estimated_usd: null }, trace_url: null,
    ...overrides,
  }
}

describe('reviewHint', () => {
  it('says when the day minimum is met while waiting', () => {
    expect(reviewHint(timing(), TZ)).toEqual([
      'Review possible from Fri 2 Oct, 4:00 PM EDT',
      'Scheduled review: Fri 2 Oct, 4:15 PM EDT',
    ])
  })

  it('says how many runs are still needed', () => {
    expect(reviewHint(timing({ trading_days: 10, trading_runs: 3 }), TZ)[0]).toBe('Needs 2 more trading runs')
  })

  it('says both when days and runs are short', () => {
    expect(reviewHint(timing({ trading_runs: 4 }), TZ)[0]).toBe(
      'Review possible from Fri 2 Oct, 4:00 PM EDT, after 1 more trading run',
    )
  })

  it('says the minimum is met once a review is possible', () => {
    expect(reviewHint(timing({ can_review: true, trading_days: 10 }), TZ)[0]).toBe('Minimum period met')
  })
})

describe('review labels', () => {
  it('names the result of each kind of review', () => {
    expect(resultLabel(entry())).toBe('v2 → v3')
    expect(resultLabel(entry({ decision: 'keep', written_version: null }))).toBe('Kept v2')
    expect(resultLabel(entry({ decision: 'first', reviewed_version: null, written_version: 1 }))).toBe('First strategy · v1')
    expect(resultLabel(entry({ status: 'failed', decision: null, written_version: null }))).toBe('Failed')
  })

  it('colours verdicts green, amber or red', () => {
    expect([targetsTone('met'), targetsTone('partly_met'), targetsTone('missed')]).toEqual(['good', 'mid', 'bad'])
    expect([followedTone('yes'), followedTone('partly'), followedTone('no')]).toEqual(['good', 'mid', 'bad'])
    expect(targetsLabel('partly_met')).toBe('partly met')
  })
})

describe('closedTradeSummary', () => {
  it('counts won and lost trades with their totals', () => {
    const trades = [
      { symbol: 'NVDA', gain: '84.10' },
      { symbol: 'AMD', gain: '-41.00' },
      { symbol: 'MU', gain: '10.00' },
    ]
    expect(closedTradeSummary(trades)).toEqual({ won: 2, lost: 1, gained: '94.10', lostAmount: '-41.00' })
  })
})
