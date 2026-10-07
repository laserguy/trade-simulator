import { describe, expect, it } from 'vitest'
import { allowanceText, comparisonText, formatExchangeTime, formatMoney, formatPercent, formatUsdCost, moveTone, periodResultText, signClass, tokens, tradingRuleLines } from './format'

describe('tradingRuleLines', () => {
  it('states every rule in plain words, with the enforced fee and cap', () => {
    expect(tradingRuleLines({ fee_per_trade: '1.00', max_position_percent: '20' }, 'USD')).toEqual([
      '$1.00 broker fee per trade (buy or sell)',
      'Whole shares only',
      'At most 20% of the portfolio in one stock, checked after each buy',
      'No short selling: only shares you hold can be sold',
      'Buy only watchlist stocks; any stock you hold can be sold',
      'Cash can never go negative, fees included',
      'In each run, sells happen before buys, so their cash can fund the buys',
    ])
  })
})

describe('formatMoney', () => {
  it('formats with thousands separators and currency', () => {
    expect(formatMoney('10500.5', 'USD')).toBe('$10,500.50')
  })
  it('shows a dash when the value is unknown', () => {
    expect(formatMoney(null, 'USD')).toBe('—')
  })
})

describe('formatPercent', () => {
  it('adds an explicit sign', () => {
    expect(formatPercent('5.00')).toBe('+5.00%')
    expect(formatPercent('-1.25')).toBe('-1.25%')
    expect(formatPercent('0.00')).toBe('0.00%')
  })
  it('shows a dash when unknown', () => {
    expect(formatPercent(null)).toBe('—')
  })
})

describe('signClass', () => {
  it('maps sign to a colour class', () => {
    expect(signClass('2')).toBe('up')
    expect(signClass('-2')).toBe('down')
    expect(signClass('0')).toBe('')
    expect(signClass(null)).toBe('')
  })
})

describe('formatUsdCost', () => {
  it('shows small costs with enough precision', () => {
    expect(formatUsdCost('0.0042')).toBe('$0.0042')
    expect(formatUsdCost('1.5000')).toBe('$1.50')
    expect(formatUsdCost(null)).toBe('—')
  })
})

describe('periodResultText', () => {
  it('names the period and compares both lines', () => {
    expect(periodResultText('1M', { agent: '0.80', benchmark: '1.10' }, 'SPY')).toBe(
      'Last month: Agent +0.80%, SPY +1.10% · Behind SPY by 0.30 pts',
    )
  })

  it('calls the whole history "since start"', () => {
    expect(periodResultText('ALL', { agent: '1.32', benchmark: '1.00' }, 'SPY')).toBe(
      'Since start: Agent +1.32%, SPY +1.00% · Ahead of SPY by 0.32 pts',
    )
  })
})

describe('comparisonText', () => {
  it('says level when the two returns match', () => {
    expect(comparisonText('0.00', '0.00', 'SPY')).toBe('Level with SPY')
  })
  it('says ahead or behind by how many points', () => {
    expect(comparisonText('4.12', '2.80', 'SPY')).toBe('Ahead of SPY by 1.32 pts')
    expect(comparisonText('-1.00', '2.00', 'SPY')).toBe('Behind SPY by 3.00 pts')
  })
  it('handles missing data', () => {
    expect(comparisonText(null, '2.00', 'SPY')).toBe('Comparison unavailable')
  })
})

describe('allowanceText', () => {
  it('says the searches fit the free allowance', () => {
    expect(allowanceText(true, null, 105)).toBe('Up to 105 web searches a month · within the free allowance')
  })
  it('says when the allowance runs out and what happens after', () => {
    expect(allowanceText(false, 7, 2730)).toBe(
      'Up to 2,730 web searches a month · free allowance runs out after about 7 trading days, then research continues without web search until the month resets',
    )
  })
})

describe('formatExchangeTime', () => {
  it("shows the time in the exchange's own timezone, whatever the viewer's timezone", () => {
    expect(formatExchangeTime('2026-09-28T13:30:00+00:00', 'America/New_York')).toBe('Mon 28 Sep, 9:30 AM EDT')
  })
})

describe('tokens', () => {
  it('abbreviates large token counts', () => {
    expect(tokens(950)).toBe('950')
    expect(tokens(12_300)).toBe('12.3k')
    expect(tokens(2_500_000)).toBe('2.5M')
  })
})

describe('moveTone', () => {
  it('is up or down for a real move and flat when the change rounds to nothing', () => {
    expect(moveTone('0.3')).toBe('up')
    expect(moveTone('-4.12')).toBe('down')
    expect(moveTone('-0.01')).toBe('flat')
    expect(moveTone('0.04')).toBe('flat')
  })
})
