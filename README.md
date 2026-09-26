# Trade Simulator

A local, single-user **paper-trading web app** in which an AI **Trading Agent**, helped by a **Research Agent**, trades US stocks with $10,000 of virtual money and shows the reasoning behind every decision.

## 📚 Documentation
| | |
|---|---|
| [🎯 Problem statement](PROBLEM_STATEMENT.md) | What is built: every decision (D1, D2, …), current status, changelog |
| [🧠 Why](WHY.md) | Why each decision was made, with the alternatives considered (same IDs) |
| [⚙️ Architecture](ARCHITECTURE.md) | Where things are in the code: layers, decision → file map, config, tables, endpoints, how to add a provider |

---

## Description

- **What it does:** the agents pick a watchlist of 10–20 S&P 500 stocks, research them using market data, market-wide news and web search, and propose buy/sell/hold orders. The code checks every order against fixed trading rules and executes the valid ones automatically. Every run is saved to a decision log with its findings, sources, orders, results and cost.
- **What problem it solves:** it lets you see how an LLM trades, and what it costs to run, with no real money at risk. The trading rules are enforced in code, not left to the agent.
- **Use case:** let it run for a few trading days (manually, daily at the open, or every 15 minutes), then compare its return with the S&P 500 and read why it made each trade.

**Rules the agent cannot override** (`core/trading_rules.py`): whole shares only, a $1 fee per trade, at most 20% of portfolio value in one stock, no shorting, buys only from the watchlist, sells processed before buys, and cash never below zero.

## Quick start

```bash
cd backend
cp .env.example .env          # add FINNHUB_API_KEY and TAVILY_API_KEY (TIINGO_API_KEY optional)
uv sync
cd ../frontend && npm install && npm run build
cd ../backend && uv run trade-sim serve
```

Open http://127.0.0.1:8000, click the gear icon, and enter an OpenAI and/or Anthropic key. The first watchlist is then built automatically. **Run now** is enabled while the US market is open.

Or use the command line:

```bash
uv run trade-sim status    # market open/closed, cash, holdings, watchlist, recent runs
uv run trade-sim refresh   # rebuild the watchlist (any time)
uv run trade-sim run       # one decision run (market hours only)
```

## Technologies used

| Area | Stack |
|------|-------|
| Backend | Python 3.12+, FastAPI, Uvicorn, `uv` |
| Agents | OpenAI Agents SDK (Anthropic models through its LiteLLM extension), tracing in the OpenAI dashboard, optional MCP servers |
| Frontend | React 19, TypeScript, Vite, vitest, oxlint |
| Storage | SQLite (one local file, one transaction per run) |
| Market data and research | Finnhub (quotes, company and market news), Tavily (web search), Tiingo (daily price history), `exchange-calendars` (NYSE hours and holidays) |

Every external data provider sits behind an interface the app owns and is chosen in `backend/.env`, so it can be swapped without touching the rest of the code (D38).

## Quick installation

**Prerequisites:** Python 3.12+ with [uv](https://docs.astral.sh/uv/), Node.js with npm, and free API keys from [Finnhub](https://finnhub.io) and [Tavily](https://tavily.com) (plus [Tiingo](https://www.tiingo.com) for the stock charts). You also need an OpenAI or Anthropic key, entered in the app.

1. `cd backend && uv sync`, then copy `.env.example` to `.env` and fill in the data-provider keys.
2. `cd frontend && npm install && npm run build`.
3. `cd backend && uv run trade-sim serve`.

LLM keys are **never** read from `.env` or the environment. They are stored in the local SQLite file from the Settings page. The server listens on `127.0.0.1` only, because it holds those keys and has no login.

For frontend development, run `npm run dev` in `frontend/` (Vite on :5173, proxying `/api` to :8000) alongside `trade-sim serve`.

## Architecture (summary)

The backend follows Clean Architecture with three layers under `backend/src/trade_simulator/`, and dependencies point inward only. **`core/`** holds the portfolio, trading rules, run limits and exchange profile, using only the standard library. **`application/`** has one module per use case, and `ports.py` defines every interface they need. **`adapters/`** implements those interfaces: SQLite, Finnhub, Tavily, Tiingo, the agents, and the FastAPI app. `adapters/bootstrap.py` is the only place that wires in concrete classes.

A run works like this: **the agent proposes, the code checks.** The Trading Agent returns orders with reasons and never touches the portfolio. `core` validates each order at the prices fetched at the start of the run, and the run and resulting portfolio are saved in one transaction. Runs never overlap, and research is capped per run (3 Research Agent calls and 5 web searches; 20 searches for a watchlist refresh). See [ARCHITECTURE.md](ARCHITECTURE.md) for the full map.

## Project structure

```
.
├── PROBLEM_STATEMENT.md, WHY.md, ARCHITECTURE.md   # source of truth for decisions and code map
├── backend/
│   ├── src/trade_simulator/
│   │   ├── core/           # domain: portfolio, orders, trading rules, run budget, exchange profile
│   │   ├── application/    # use cases + ports.py (interfaces)
│   │   ├── adapters/       # SQLite, Finnhub, Tavily, Tiingo, calendar, openai_agents/, web/api.py, bootstrap.py
│   │   └── cli.py          # trade-sim serve | status | refresh | run
│   ├── prompts/            # agent prompts as Markdown (trading, research, watchlist refresh)
│   ├── tests/              # mirrors src: core/, application/, adapters/, integration/ (opt-in)
│   ├── model_catalogue.json        # models and prices shown in Settings
│   ├── mcp_servers.example.json    # optional MCP servers for the agents
│   └── .env.example
└── frontend/src/
    ├── App.tsx, api.ts, chart.ts, format.ts
    └── components/         # Home, RunLog, LiveRun, WatchlistView, PriceChart, SettingsView, RunModeSection
```

Runtime files are git-ignored: the database is `backend/data/trade_simulator.sqlite3` (delete it to start fresh), and the log is `backend/logs/app.log`, with API keys scrubbed.

## Testing

```bash
cd backend && uv run pytest                    # unit tests; external APIs and the AI are faked
cd backend && uv run pytest -m integration     # opt-in, calls the real APIs (needs keys, costs a little)
cd frontend && npm test                        # vitest
```

`backend/tests/test_docs_in_sync.py` fails when the code and the docs disagree, for example when a source file, table, endpoint or config variable is missing from ARCHITECTURE.md, or a decision has no WHY entry.
