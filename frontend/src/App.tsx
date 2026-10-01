import { useCallback, useEffect, useRef, useState } from 'react'
import './App.css'
import {
  api,
  ApiError,
  type Activity,
  type Portfolio,
  type Run,
  type Settings,
  type Status,
  type StrategyPage,
  type ValueHistory,
  type Watchlist,
} from './api'
import { Home } from './components/Home'
import { LiveRun } from './components/LiveRun'
import { RunLog } from './components/RunLog'
import { SettingsView } from './components/SettingsView'
import { StrategyView } from './components/StrategyView'
import { WatchlistView } from './components/WatchlistView'
import { formatExchangeTime } from './format'

// Screens: Home, Decision log, Watchlist, Strategy as tabs (D32, D44); Settings as its own page behind the gear icon (D29).
type Page = 'home' | 'log' | 'watchlist' | 'strategy' | 'settings'
const TABS: { id: Page; label: string }[] = [
  { id: 'home', label: 'Home' },
  { id: 'log', label: 'Decision log' },
  { id: 'watchlist', label: 'Watchlist' },
  { id: 'strategy', label: 'Strategy' },
]

export default function App() {
  const [page, setPage] = useState<Page>('home')
  const [status, setStatus] = useState<Status | null>(null)
  const [portfolio, setPortfolio] = useState<Portfolio | null>(null)
  const [history, setHistory] = useState<ValueHistory>({ points: [], trades: [] })
  const [openRunId, setOpenRunId] = useState<string | null>(null)
  const [watchlist, setWatchlist] = useState<Watchlist | null>(null)
  const [runs, setRuns] = useState<Run[]>([])
  const [settings, setSettings] = useState<Settings | null>(null)
  const [strategy, setStrategy] = useState<StrategyPage | null>(null)
  const [strategyVersion, setStrategyVersion] = useState<number | null>(null) // opened from a run's tag (D44)
  const [activity, setActivity] = useState<Activity | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [offline, setOffline] = useState(false)
  const [starting, setStarting] = useState(false)
  const startingRef = useRef(false)
  const wasRunning = useRef(false)

  const loadData = useCallback(async () => {
    try {
      const [p, h, w, r, s, st] = await Promise.all([
        api.portfolio(),
        api.history(),
        api.watchlist(),
        api.runs(),
        api.settings(),
        api.strategy(),
      ])
      setPortfolio(p)
      setHistory(h)
      setWatchlist(w)
      setRuns(r)
      setSettings(s)
      setStrategy(st)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not reach the backend')
    }
  }, [])

  // Poll status every few seconds; while a run is going, also poll the live timeline (D28).
  useEffect(() => {
    let cancelled = false
    const poll = async () => {
      try {
        const s = await api.status()
        if (cancelled) return
        setStatus(s)
        setOffline(false)
        if (s.run_in_progress) setActivity(await api.activity())
        else setActivity(null)
        if (wasRunning.current && !s.run_in_progress) void loadData()
        wasRunning.current = s.run_in_progress
      } catch {
        if (!cancelled) setOffline(true)
      }
    }
    void poll()
    void loadData()
    const timer = setInterval(poll, 2000)
    return () => {
      cancelled = true
      clearInterval(timer)
    }
  }, [loadData])

  const showRunning = () => {
    wasRunning.current = true
    setStatus((s) => (s ? { ...s, run_in_progress: true } : s))
    setPage('log')
  }

  // Buttons are disabled from the click on, so a double-click can't send a second request (D20).
  const start = async (action: () => Promise<unknown>) => {
    if (startingRef.current) return
    startingRef.current = true
    setStarting(true)
    setError(null)
    try {
      await action()
      showRunning()
    } catch (e) {
      // Refused because a run is already going: that's not an error, just show the run (D20).
      const busy = e instanceof ApiError && e.status === 409 && (await api.status().catch(() => null))?.run_in_progress
      if (busy) showRunning()
      else setError(e instanceof ApiError || e instanceof Error ? e.message : 'Request failed')
    } finally {
      startingRef.current = false
      setStarting(false)
    }
  }

  const running = (status?.run_in_progress ?? false) || starting
  const marketOpen = status?.market_open ?? false
  const noModel = settings !== null && settings.selected_model_id === null
  const currency = status?.currency ?? 'USD'

  return (
    <div className="app">
      <header className="topbar">
        <div className="brand">
          <h1>Trade Simulator</h1>
          <p>AI agents trading virtual money · {status?.exchange ?? '…'}</p>
        </div>
        <span className={`pill ${running ? 'running' : marketOpen ? 'open' : ''}`}>
          <span className="dot" />
          {running
            ? 'Agent run in progress…'
            : marketOpen
              ? 'Market open'
              : status?.next_open
                ? `Market closed · opens ${formatExchangeTime(status.next_open, status.timezone)}`
                : 'Market closed'}
        </span>
        <span className="spacer" />
        <button
          className="btn"
          disabled={running || noModel}
          onClick={() => start(api.refreshWatchlist)}
          title="Rebuild the watchlist (allowed any time)"
        >
          Refresh watchlist
        </button>
        <button
          className="btn primary"
          disabled={running || !marketOpen || noModel || !watchlist}
          onClick={() => start(api.runNow)}
          title={!marketOpen ? 'Available during market hours' : !watchlist ? 'The watchlist is not ready yet' : 'Run one decision now'}
        >
          Run now
        </button>
        <button
          className={`icon-btn ${page === 'settings' ? 'active' : ''}`}
          aria-label="Settings"
          title="Settings"
          onClick={() => setPage(page === 'settings' ? 'home' : 'settings')}
        >
          <GearIcon />
        </button>
      </header>

      {noModel && page !== 'settings' && (
        <div className="banner warn">
          Add an OpenAI or Anthropic API key in <a href="#" onClick={() => setPage('settings')}>Settings</a> to run the agents.
        </div>
      )}
      {offline && <div className="banner error">Backend not reachable. Is `uv run trade-sim serve` running?</div>}
      {error && (
        <div className="banner error closable">
          <span>{error}</span>
          <button className="banner-close" aria-label="Close" title="Close" onClick={() => setError(null)}>
            ×
          </button>
        </div>
      )}

      {page === 'settings' ? (
        <>
          <div className="page-head">
            <button className="btn small" onClick={() => setPage('home')}>← Back</button>
            <h2>Settings</h2>
          </div>
          <SettingsView
            settings={settings}
            timezone={status?.timezone ?? 'America/New_York'}
            currency={currency}
            onChange={setSettings}
            onError={setError}
          />
        </>
      ) : (
        <>
          <nav className="tabs">
            {TABS.map((t) => (
              <button
                key={t.id}
                className={page === t.id ? 'active' : ''}
                onClick={() => {
                  setOpenRunId(null)
                  setStrategyVersion(null)
                  setPage(t.id)
                }}
              >
                {t.label}
              </button>
            ))}
          </nav>
          {page === 'home' && (
            <Home
              portfolio={portfolio}
              history={history}
              runs={runs}
              running={running}
              onOpenLog={(runId) => {
                setOpenRunId(runId ?? null)
                setPage('log')
              }}
            />
          )}
          {page === 'log' && (
            <>
              <LiveRun activity={activity} />
              <RunLog
                runs={runs}
                currency={currency}
                openRunId={openRunId}
                onOpenStrategy={(version) => {
                  setStrategyVersion(version)
                  setPage('strategy')
                }}
              />
            </>
          )}
          {page === 'watchlist' && <WatchlistView watchlist={watchlist} currency={currency} />}
          {page === 'strategy' && (
            <StrategyView
              page={strategy}
              currency={currency}
              timezone={status?.timezone ?? 'America/New_York'}
              disabled={running || noModel}
              onReview={() => start(api.reviewStrategy)}
              focusVersion={strategyVersion}
            />
          )}
        </>
      )}
    </div>
  )
}

function GearIcon() {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <circle cx="12" cy="12" r="3" />
      <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 1 1-4 0v-.09a1.65 1.65 0 0 0-1-1.51 1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 1 1 0-4h.09a1.65 1.65 0 0 0 1.51-1 1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 1 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 1 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z" />
    </svg>
  )
}
