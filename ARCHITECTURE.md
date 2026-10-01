# Trade Simulator: Architecture

> A map of the code for anyone (human or AI) about to change it.
> *What* we build is in [PROBLEM_STATEMENT.md](PROBLEM_STATEMENT.md), and *why* is in [WHY.md](WHY.md).
> This file only says *where* things are. Update it when you add, move or rename a file, table, endpoint or setting.

## Layers (D17)

Everything is under `backend/src/trade_simulator/`. Dependencies point inward only: `adapters` → `application` → `core`.

| Layer | Folder | May import | Holds |
|-------|--------|-----------|-------|
| Core | `core/` | only the standard library | Portfolio, orders, trading rules, run limits, exchange profile, decision log records, model pricing, errors |
| Use cases | `application/` | `core` | One module per use case, plus `ports.py`: every interface (`Protocol`) the use cases need, and the data passed through them |
| Adapters | `adapters/` | `application`, `core`, third-party libraries | SQLite, Finnhub, Tavily, Tiingo, exchange calendar, OpenAI Agents SDK, FastAPI, config, logging |

- **Wiring:** `adapters/bootstrap.py` is the only place that knows every concrete adapter. It builds the services from config.
- **Entry points:** `cli.py` (`trade-sim serve|status|refresh|run|review`) and `adapters/web/api.py` (`create_app`).
- **Startup (`api.py` lifespan):** it builds the first watchlist if needed (D4), fills the price cache in the background (D36), and starts the scheduler loop (D3, D33). The loop checks every 10 seconds.

## Where each decision lives

| Decision | Code |
|----------|------|
| D4 watchlist, S&P 500 pool | `application/refresh_watchlist.py`, `application/initial_watchlist.py`, `adapters/sp500_universe.py` |
| D5, D24 exchange profile, capital, fee | `core/exchange_profile.py` (`US_PROFILE`), `application/portfolio_setup.py` |
| D6, D20 trading rules, the agent proposes and the code checks | `core/trading_rules.py` (`execute_orders`), `core/portfolio.py`, `core/order.py` |
| D7, D38 market data | `adapters/finnhub_market_data.py` (implements `MarketData` and `QuoteSource`) |
| D9 keys, model choice, prices | `application/settings.py`, `core/model_pricing.py`, `adapters/model_catalogue_file.py`, `backend/model_catalogue.json`, `adapters/openai_agents/models.py` |
| D10, D34 web search | `adapters/tavily_search.py` (implements `WebSearch`) |
| D11, D12 agents and their roles | `adapters/openai_agents/agent_factory.py`, `trading_agents.py`, `toolbox.py`, `schemas.py` (structured outputs), `inputs.py` (the text each agent run starts from), `state.py` (per-run state: budget, usage, findings), `backend/prompts/*.md` |
| D40 market context in research | `adapters/finnhub_market_data.py` (`market_news`), `toolbox.py` and `agent_factory.py` (`get_market_news` tool), `application/ports.py` (`MarketOverview`, `Repository.latest_market_overview`), `application/run_decision.py`, `inputs.py`, `backend/prompts/*.md` |
| D41 trading goal | `backend/prompts/trading_agent.md` (Goal section) |
| D42 agent's memory of its trades | `application/trade_memory.py` (buys behind each holding, performance line), `application/run_decision.py` (puts them in `DecisionContext`), `inputs.py` (writes them into the agent's starting text, and builds the holdings note), `agent_factory.py` (adds the note to every research request), `adapters/sqlite_repository.py` (`executed_trades`, with reasons) |
| D43 agent-written strategy (being built) | `core/strategy.py` (the five sections, versions, `DEVIATION`), `core/strategy_review.py` (review, verdicts, scorecard), `core/order.py` (`follows`: the section an order follows), `application/strategy_scorecard.py` (a version's results, computed by code), `application/strategy_timing.py` (minimums, when a review may run, the weekly slot and catch-up), `application/review_strategy.py` (the review use case: context, code check of the answer, all-or-nothing save, failed reviews logged), `adapters/openai_agents/review_input.py` (the review's starting text: scorecard, orders, version history), `schemas.py` (`StrategyReviewResult`), `agent_factory.py` (`strategy_reviewer`: the Trading Agent with no tools), `trading_agents.py` (`review_strategy`), `backend/prompts/strategy_review.md`, `adapters/sqlite_repository.py` (`strategy_versions`, `strategy_reviews`, `runs_following`), `cli.py` (`trade-sim review`) |
| D44 Strategy tab | `application/strategy_view.py` (what the tab shows: changed sections, timing, live scorecard, reviews with old → new), `adapters/web/api.py` (`/api/strategy`), `frontend/src/components/StrategyView.tsx`, helpers `strategy.ts` (review hint, result labels, verdict colours) |
| D13, D14 run limits | `core/run_budget.py` (`DECISION_RUN_LIMITS`, `REFRESH_RUN_LIMITS`), enforced in `adapters/openai_agents/toolbox.py` and `agent_factory.py` |
| D15, D19 storage, all-or-nothing saves | `adapters/sqlite_repository.py` (implements `Repository` and `SettingsStore`) |
| D19 errors, keys never logged | `core/errors.py`, `adapters/logging_setup.py` |
| D20 runs never overlap | `application/run_guard.py`, `application/run_decision.py` |
| D21 market hours | `adapters/exchange_calendar.py` (implements `MarketCalendar`) |
| D22 decision log records | `core/decision_log.py`, `application/run_cost.py`, `adapters/text_links.py`; sources checked against the links tools returned: `adapters/openai_agents/run_hooks.py` (collects them), `schemas.py` (drops the rest); price and day change per finding: `toolbox.py` (remembers the quotes in `state.py`), `schemas.py` (attaches them) |
| D23, D33 benchmark and value history | `application/portfolio_view.py`, `application/value_history.py` |
| D25 prompts and tracing | `adapters/openai_agents/prompts.py`, `trading_agents.py` |
| D27 MCP servers | `adapters/openai_agents/mcp_config.py`, `backend/mcp_servers.example.json` |
| D28 live timeline | `application/activity.py`, `adapters/openai_agents/timeline_hooks.py`, `activity_text.py`, `frontend/src/components/LiveRun.tsx` |
| D3, D35 run mode, scheduler, cost estimate | `application/run_mode.py`, `schedule.py`, `scheduler.py`, `run_cost_estimate.py`, `frontend/src/components/RunModeSection.tsx` |
| D36 price history | `application/price_history.py`, `adapters/tiingo_price_history.py` (implements `PriceHistorySource`) |
| D30 watchlist view | `application/watchlist_view.py` (watchlist with quotes and held flag) |
| D29–D32, D37 screens | `frontend/src/main.tsx` (entry), `App.tsx` (tabs, including Strategy (D44), and gear icon), `components/Home.tsx`, `RunLog.tsx`, `WatchlistView.tsx`, `PriceChart.tsx`, `SettingsView.tsx`; helpers `chart.ts` (chart points, trade markers on the watchlist and Home charts), `format.ts` (money, percentages, exchange times), `runSections.ts` (how an open Decision log run is grouped: orders with their research, the rest) and `runText.ts` (a run as plain text for the Decision log's Copy button) |

## Config (`backend/.env`, see `.env.example`)

Read by `adapters/config.py`. LLM keys are **not** here: they are stored in the `settings` table from the Settings page (D9).

| Variable | Default | Notes |
|----------|---------|-------|
| `MARKET_DATA_PROVIDER` | `finnhub` | Needs `FINNHUB_API_KEY` |
| `SEARCH_PROVIDER` | `tavily` | Needs `TAVILY_API_KEY` |
| `PRICE_HISTORY_PROVIDER` | `tiingo` | `TIINGO_API_KEY` is optional; without it charts show as not set up |

Fixed paths (under `backend/`): database `data/trade_simulator.sqlite3`, log `logs/app.log`, prompts `prompts/`, MCP config `mcp_servers.json`, model catalogue `model_catalogue.json`, and the built UI at `../frontend/dist`.

## Database tables (`adapters/sqlite_repository.py`)

Money is stored as exact decimal text. New columns on existing tables go in `_ADDED_COLUMNS`, which is applied at startup.

| Table | Holds |
|-------|-------|
| `portfolio`, `positions` | Cash (a single row), and holdings with average cost |
| `runs` | One row per run: trigger, status, failure reason, tokens, searches, model, trace ID, and the strategy version it followed (D43) |
| `findings` | Research findings per run (`symbol` can also be `OVERALL` or `MARKET`, D22), with sources, warnings, and the stock's price and day change when it was quoted in the run |
| `order_results` | Proposed orders per run, with executed price and fee, or the rejection reason, and the strategy section the order follows or `deviation` (D43) |
| `strategy_reviews` | One row per strategy review, failed ones included: trigger, decision (first / keep / change), reason, verdicts on targets and following, why each section changed, the scorecard as shown (JSON), tokens, model, trace ID (D43) |
| `strategy_versions` | Each strategy version: the five sections, start and end time (no end = current), and the review that wrote it (D43) |
| `watchlist_meta`, `watchlist_entries` | The current watchlist with a reason and sources per stock |
| `settings` | Key/value: `openai_api_key`, `anthropic_api_key`, `model_id`, `run_mode` |
| `benchmark_start` | SPY price when tracking began (D23) |
| `value_snapshots` | Portfolio value and SPY price over time (D33), and the cash held then (for the strategy scorecard, D43; empty on older points) |
| `price_history`, `price_history_sync` | Cached daily bars and when each stock was last fetched (D36) |

## API endpoints (`adapters/web/api.py`, localhost only)

| Method and path | Purpose |
|---------------|---------|
| `GET /api/status` | Market open or closed, next open, run in progress, exchange info |
| `GET /api/portfolio` | Cash, holdings, P&L, benchmark comparison |
| `GET /api/history` | Value chart points, and each run's executed trades for the chart's markers (D32) |
| `GET /api/watchlist` | Watchlist with quotes and whether each stock is held |
| `GET /api/price-history/{symbol}?period=1M\|3M\|1Y` | Chart data with the agent's trades |
| `GET /api/runs`, `GET /api/runs/{id}` | Decision log |
| `GET /api/activity` | Live timeline of the run in progress (D28) |
| `POST /api/runs` | Run now (409 if the market is closed or a run is in progress) |
| `POST /api/watchlist/refresh` | Refresh the watchlist (409 if a run is in progress) |
| `GET /api/strategy` | Strategy tab: current strategy with changed sections, review timing, the current version's scorecard so far, review history (D44) |
| `POST /api/strategy/review` | Review strategy (409 if a run is in progress or the minimum period isn't over; adds no value point) |
| `GET /api/settings`, `PUT /api/settings/keys/{openai\|anthropic}`, `PUT /api/settings/model`, `PUT /api/settings/run-mode` | Settings page |

The frontend calls these through `frontend/src/api.ts`.

## Tests (D18)

- `backend/tests/` has the same folders as `src`: `core/`, `application/`, `adapters/`.
- Fakes for use-case tests are in `tests/application/fakes.py` (`FakeMarketData`, `FakeCalendar`, `FakeAgent`, `FakeUniverse`, `FixedClock`).
- `tests/integration/` calls the real APIs, runs only with `-m integration`, and needs keys.
- Frontend tests (vitest) sit next to the code they test: `frontend/src/*.test.ts`.

## How to add or swap an external provider (D38)

1. If no interface exists yet, add one to `application/ports.py`, named after what it does and not after the provider.
2. Write the adapter in `adapters/<provider>_<what>.py`, plus tests in `tests/adapters/` with the HTTP calls mocked.
3. Add the provider and the name of its key variable to the matching `*_PROVIDER_KEYS` table in `adapters/config.py`.
4. Add a branch in the matching factory in `adapters/bootstrap.py` (`_market_data`, `_web_search`, `_price_history`).
5. Add the key to `.env.example`. Never show the provider's name in the UI (D34). For a new *kind* of tool, add a field to `AppConfig` and include its key in `AppConfig.secrets()`, so it is scrubbed from logs (D19).
6. Optionally, add an opt-in live test in `tests/integration/`.
