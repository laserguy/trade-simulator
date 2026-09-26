import { Fragment, useState } from 'react'
import type { Watchlist } from '../api'
import { linePoints } from '../chart'
import { formatDateTime, formatMoney, formatPercent, signClass } from '../format'
import { PriceChart } from './PriceChart'

// Watchlist (D30) with a "Last month" trend line per row and a chart per stock on click (D37).

export function WatchlistView({ watchlist, currency }: { watchlist: Watchlist | null; currency: string }) {
  const [open, setOpen] = useState<string | null>(null)

  if (!watchlist) {
    return (
      <div className="card">
        <div className="empty">
          No watchlist yet. It's built automatically once an AI key is saved in Settings, or use “Refresh watchlist”.
        </div>
      </div>
    )
  }
  return (
    <div className="card">
      <div className="card-head">
        <h2>{watchlist.rows.length} stocks the agent may buy</h2>
        <span className="muted small">
          {watchlist.charts_available ? 'Click a row for its chart · ' : ''}Refreshed {formatDateTime(watchlist.refreshed_at)}
        </span>
      </div>
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Stock</th>
              <th className="r">Price</th>
              <th className="r">Today</th>
              {watchlist.charts_available && <th>Last month</th>}
              <th className="r">Held</th>
              <th>Why the agent picked it</th>
            </tr>
          </thead>
          <tbody>
            {watchlist.rows.map((row) => {
              const isOpen = open === row.symbol
              return (
                <Fragment key={row.symbol}>
                  <tr
                    className={watchlist.charts_available ? `clickable ${isOpen ? 'open' : ''}` : ''}
                    onClick={() => watchlist.charts_available && setOpen(isOpen ? null : row.symbol)}
                  >
                    <td>
                      <strong>{row.symbol}</strong>
                      {watchlist.charts_available && <span className="muted"> {isOpen ? '▾' : '▸'}</span>}
                    </td>
                    <td className="r num">{formatMoney(row.price, currency)}</td>
                    <td className={`r num ${signClass(row.change_percent)}`}>{formatPercent(row.change_percent)}</td>
                    {watchlist.charts_available && (
                      <td>
                        <TrendLine values={row.trend} />
                      </td>
                    )}
                    <td className="r num">{row.held_quantity > 0 ? row.held_quantity : '—'}</td>
                    <td>
                      {row.reason}
                      {row.sources.length > 0 && (
                        <div className="sources">
                          {row.sources.slice(0, 3).map((s, i) => (
                            <a key={i} href={s} target="_blank" rel="noreferrer" onClick={(e) => e.stopPropagation()}>
                              source {i + 1}
                            </a>
                          ))}
                        </div>
                      )}
                    </td>
                  </tr>
                  {isOpen && (
                    <tr className="chart-row">
                      <td colSpan={6}>
                        <PriceChart symbol={row.symbol} currency={currency} />
                      </td>
                    </tr>
                  )}
                </Fragment>
              )
            })}
          </tbody>
        </table>
      </div>
    </div>
  )
}

function TrendLine({ values }: { values: string[] }) {
  if (values.length < 2) return <span className="muted small">loading…</span>
  const rising = Number(values[values.length - 1]) >= Number(values[0])
  return (
    <svg width="96" height="24" viewBox="0 0 96 24" aria-label={rising ? 'Up over the last month' : 'Down over the last month'}>
      <polyline className={`trend ${rising ? 'rising' : 'falling'}`} points={linePoints(values, 96, 22)} transform="translate(0,1)" />
    </svg>
  )
}
