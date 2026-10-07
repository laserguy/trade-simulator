import { describe, expect, it } from 'vitest'
import { chartLines, linePoints, nearestIndex, periodChange, readoutAt, tradeMarkers, valueMarkers } from './chart'

describe('linePoints', () => {
  it('draws values left to right, highest at the top', () => {
    expect(linePoints(['10', '15', '20'], 100, 40)).toBe('0.0,40.0 50.0,20.0 100.0,0.0')
  })
  it('needs at least two values', () => {
    expect(linePoints(['10'], 100, 40)).toBe('')
  })
})

describe('tradeMarkers', () => {
  const bars = [
    { day: '2026-09-24', close: '10' },
    { day: '2026-09-25', close: '20' },
    { day: '2026-09-28', close: '30' },
  ]

  it('places each trade on the bar of its day', () => {
    const [marker] = tradeMarkers(bars, [{ day: '2026-09-25', side: 'buy', quantity: 3, price: '19' }], 100, 40)

    expect(marker).toMatchObject({ x: 50, y: 20, side: 'buy', label: 'Agent bought 3' })
  })

  it('puts a trade on a non-trading day at the next bar', () => {
    const [marker] = tradeMarkers(bars, [{ day: '2026-09-26', side: 'sell', quantity: 2, price: '21' }], 100, 40)

    expect(marker).toMatchObject({ x: 100, side: 'sell', label: 'Agent sold 2' })
  })
})

const points = [
  { at: '2026-09-28T20:00:00Z', total_value: '10000.00', benchmark_value: '10000.00' },
  { at: '2026-09-29T20:00:00Z', total_value: '10500.00', benchmark_value: '10200.00' },
]

describe('chartLines', () => {
  it('scales both lines into the same box so they are comparable', () => {
    const lines = chartLines(points, 100, 50)!

    expect(lines.portfolio).toBe('0.0,50.0 100.0,0.0')
    expect(lines.benchmark).toBe('0.0,50.0 100.0,30.0')
    expect(lines.min).toBe(10000)
    expect(lines.max).toBe(10500)
  })

  it('needs at least two points to draw', () => {
    expect(chartLines(points.slice(0, 1), 100, 50)).toBeNull()
  })

  it('keeps a flat line in the middle instead of dividing by zero', () => {
    const flat = [points[0], { ...points[0], at: '2026-09-29T20:00:00Z' }]

    expect(chartLines(flat, 100, 50)?.portfolio).toBe('0.0,25.0 100.0,25.0')
  })

  it('has no live stretch without a now point', () => {
    expect(chartLines(points, 100, 50)?.portfolioLive).toBe('')
  })

  describe('with a now point', () => {
    const now = { at: '2026-09-30T15:00:00Z', total_value: '10600.00', benchmark_value: '10400.00' }

    it('ends both lines at now with a live stretch from the last saved point', () => {
      const lines = chartLines(points, 100, 60, now)!

      expect(lines.portfolio).toBe('0.0,60.0 50.0,10.0')
      expect(lines.portfolioLive).toBe('50.0,10.0 100.0,0.0')
      expect(lines.benchmarkLive).toBe('50.0,40.0 100.0,20.0')
      expect(lines.max).toBe(10600)
    })

    it('draws from one saved point plus now', () => {
      expect(chartLines(points.slice(0, 1), 100, 60, now)?.portfolioLive).toBe('0.0,60.0 100.0,0.0')
    })

    it('needs at least one saved point', () => {
      expect(chartLines([], 100, 60, now)).toBeNull()
    })
  })
})

describe('valueMarkers', () => {
  const three = [
    { at: '2026-09-28T14:00:00Z', total_value: '10000.00', benchmark_value: '10000.00' },
    { at: '2026-09-28T15:01:00Z', total_value: '10250.00', benchmark_value: '10100.00' },
    { at: '2026-09-28T20:00:00Z', total_value: '10500.00', benchmark_value: '10200.00' },
  ]
  const buy = { side: 'buy' as const, quantity: 5, symbol: 'AAPL', price: '200.00' }
  const sell = { side: 'sell' as const, quantity: 2, symbol: 'MSFT', price: '410.50' }

  it('puts a run on the first point recorded after it started, on the agent line', () => {
    const [marker] = valueMarkers(three, [{ run_id: 'r1', at: '2026-09-28T15:00:00Z', orders: [buy] }], 100, 50)

    expect(marker).toMatchObject({ x: 50, y: 25, side: 'buy', runId: 'r1' })
  })

  it('marks a run that bought and sold as mixed', () => {
    const [marker] = valueMarkers(three, [{ run_id: 'r1', at: '2026-09-28T15:00:00Z', orders: [buy, sell] }], 100, 50)

    expect(marker.side).toBe('mixed')
  })

  it('compares times, not text, when offsets differ', () => {
    const [marker] = valueMarkers(three, [{ run_id: 'r1', at: '2026-09-28T11:00:00-04:00', orders: [sell] }], 100, 50)

    expect(marker).toMatchObject({ x: 50, side: 'sell' })
  })

  it('skips a run with no point after it yet', () => {
    expect(valueMarkers(three, [{ run_id: 'r1', at: '2026-09-28T21:00:00Z', orders: [buy] }], 100, 50)).toEqual([])
  })

  it('uses the same scale as the lines when there is a now point, but never marks the now point', () => {
    const now = { at: '2026-09-29T15:00:00Z', total_value: '11000.00', benchmark_value: '10200.00' }
    const runs = [
      { run_id: 'r1', at: '2026-09-28T15:00:00Z', orders: [buy] },
      { run_id: 'r2', at: '2026-09-28T21:00:00Z', orders: [buy] },
    ]

    expect(valueMarkers(three, runs, 90, 100, now)).toEqual([expect.objectContaining({ x: 30, y: 75, runId: 'r1' })])
  })

  it('needs at least two points', () => {
    expect(valueMarkers(three.slice(0, 1), [{ run_id: 'r1', at: '2026-09-28T13:00:00Z', orders: [buy] }], 100, 50)).toEqual([])
  })

  it('merges runs that land on the same point, keeping the first run to open', () => {
    const runs = [
      { run_id: 'r1', at: '2026-09-28T15:05:00Z', orders: [buy] },
      { run_id: 'r2', at: '2026-09-28T16:00:00Z', orders: [sell] },
    ]

    const markers = valueMarkers(three, runs, 100, 50)

    expect(markers).toHaveLength(1)
    expect(markers[0]).toMatchObject({ x: 100, runId: 'r1', side: 'mixed', orders: [buy, sell] })
  })
})

describe('nearestIndex', () => {
  it('snaps a position across the chart to the closest point', () => {
    expect(nearestIndex(0.4, 3)).toBe(1)
    expect(nearestIndex(0.9, 3)).toBe(2)
  })

  it('stays inside the chart', () => {
    expect(nearestIndex(-0.2, 3)).toBe(0)
    expect(nearestIndex(1.3, 3)).toBe(2)
  })
})

describe('readoutAt', () => {
  const now = { at: '2026-09-30T15:00:00Z', total_value: '10132.00', benchmark_value: '10100.00' }

  it('gives the values and returns since start at a saved point', () => {
    expect(readoutAt(points, now, 1, '10000.00')).toEqual({
      at: '2026-09-29T20:00:00Z',
      isNow: false,
      agentValue: '10500.00',
      benchmarkValue: '10200.00',
      agentReturn: '5.00',
      benchmarkReturn: '2.00',
    })
  })

  it('treats the last slot as now when there is a now point', () => {
    expect(readoutAt(points, now, 2, '10000.00')).toMatchObject({ isNow: true, agentReturn: '1.32', benchmarkReturn: '1.00' })
  })
})

describe('periodChange', () => {
  it('compares the first and last point of the period, now included', () => {
    const now = { at: '2026-09-30T15:00:00Z', total_value: '10600.00', benchmark_value: '10100.00' }

    expect(periodChange(points, now)).toEqual({ agent: '6.00', benchmark: '1.00' })
  })

  it('needs two points', () => {
    expect(periodChange(points.slice(0, 1), null)).toBeNull()
  })
})
