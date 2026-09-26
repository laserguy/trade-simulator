import { describe, expect, it } from 'vitest'
import { chartLines, linePoints, tradeMarkers } from './chart'

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
})
