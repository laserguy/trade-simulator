# Trade Simulator: Why

> Living document. It explains why each decision in [PROBLEM_STATEMENT.md](PROBLEM_STATEMENT.md) was made.
> Entries use the same decision IDs. When a decision changes, update its entry here and note what changed.

---

### D1: Minimal scope
- **Choice:** One exchange, one Trading Agent plus one Research Agent, virtual money, no login.
- **Why:** Prove the core loop (research → decide → trade → log) works before adding complexity. The project will expand step by step.
- **Alternatives considered:** A global, multi-agent SaaS from day one. Too many moving parts to build and evaluate at once.
- **Date:** 2026-09-26

### D2: US exchange first
- **Choice:** NYSE/NASDAQ.
- **Why:** The US market has the most free market data and news coverage, which makes it the easiest place to start.
- **Alternatives considered:** Tokyo and India. Both are wanted, but they are parked for later.
- **Date:** 2026-09-26

### D3: Run mode toggle, Manual by default
- **Choice:** The user can switch between Manual, Daily at open, and Every 15 minutes. Manual is the default, and "Run now" is available in every mode (while the market is open, D21).
- **Why:** Cost control. Every agent run costs money for AI and data. Manual is the cheapest default, and the user can opt into more frequent runs when they want.
- **Alternatives considered:** A single fixed schedule. Rejected because the user wants flexibility without always paying for the most frequent mode.
- **Date:** 2026-09-26

### D4: Agent-built watchlist from the S&P 500, refreshed on request
- **Choice:** The agent researches and picks 10–20 tickers from the S&P 500. The list is rebuilt only when the user clicks "Refresh watchlist".
- **Why:**
  - The user wants the agent to choose stocks based on its own research, not from a hand-picked list.
  - Limiting the pool to the S&P 500 keeps the agent away from penny stocks and pump-and-dump risk, since scam detection is parked for later.
  - Building the watchlist is the most expensive research step. Doing it only on request keeps regular runs cheap, because they only decide buy/sell/hold on the existing list.
- **Alternatives considered:** A user-picked watchlist; the full S&P 500 on every run (costly); any US stock (costly and risky); weekly or daily automatic refresh (more cost).
- **Date:** 2026-09-26

**Update (2026-09-26): first watchlist built automatically, once**
- **Choice:** When there is no watchlist and an AI key exists, the app builds the first watchlist by itself: at start-up if a key is saved, or right after the first key is saved. It happens once; a failed attempt is not retried automatically.
- **Why:**
  - The user expected tickers to be there after setting up the app. An empty watchlist blocks every decision run, so it's a dead end for a new user.
  - The trigger waits for an AI key, because the research can't run without one, and on a first start the key is only entered after the app is running.
  - "Once, no automatic retry" keeps the cost-first goal: a broken setup (for example a bad Tavily key) can't keep spending money in a loop. The button is always there to retry.
- **Alternatives considered:** Building at start-up only (a new user would have to restart or click after saving the key); asking for confirmation first (nothing spent without a click, but an extra step the user didn't want).

### D5: Fixed $10,000 capital
- **Choice:** Always start with $10,000 of virtual money.
- **Why:** It is close to a real personal account, and a fixed amount means nothing to configure.
- **Alternatives considered:** A user-set amount; a fixed $100,000.
- **Date:** 2026-09-26

### D6: Realistic trading rules, enforced in code
- **Choice:** Whole shares only, a small fee per trade, at most 20% of the portfolio in one stock, and no shorting.
- **Why:**
  - The user preferred realism over simplicity.
  - The 20% cap forces diversification across at least 5 positions.
  - The rules live in code, not in the prompt, so the AI cannot break them.
- **Alternatives considered:** Fractional shares with no fees (simpler); no limits (risky, and harder to learn from).
- **Date:** 2026-09-26

**Update (2026-09-26): rule details**
- **$1 flat broker fee per trade:** Without a fee, the agent could trade constantly at no cost. A flat $1 is a mild, realistic friction on a $10k account. Many US brokers charge $0, so $1 is a light touch. It lives in the exchange profile (D24) so other exchanges can have their own fees. Alternatives: 0.1% of trade value; $0 (which would make the fee rule pointless).
- **20% cap measured after the buy, against total value at current prices:** This measures what the portfolio would actually look like after the trade.
- **Buys only from the watchlist, sells of anything held:** After a watchlist refresh (D4), the portfolio may hold stocks no longer on the list. The agent must still be able to exit them.
- **Sells before buys within a run:** Selling first frees cash, so a sensible "sell X, buy Y" isn't rejected just because of the order in which the agent listed it.

### D7: Free, ~15-minute delayed data plus web search
- **Choice:** Free-tier market data and web search for news.
- **Why:** A delay of about 15 minutes is fine for a simulator, and it adds no data cost.
- **Alternatives considered:** Paid real-time data (tens of dollars a month); end-of-day prices only (don't fit the 15-minute mode).
- **Date:** 2026-09-26

**Update (2026-09-26): provider chosen: Finnhub free tier, no MCP for v1**
- **Why Finnhub:** It is free with a generous limit (60 calls/min) and covers quotes, company news and fundamentals in one place.
- **Why no MCP:** Finnhub's official hosted MCP server signs in through Claude or ChatGPT (OAuth), so our own app can't easily use it. Small tools that call Finnhub's REST API with the user's key are simpler. The data layer sits behind an interface so an MCP server can be plugged in later.
- **Alternatives considered:**
  - Alpha Vantage official MCP: free, but only 25 requests/day.
  - Massive (formerly Polygon.io) official MCP: the free plan has end-of-day data only, and 15-min delayed data costs $29/month.
- **Risk to verify at build time:** Which Finnhub endpoints (for example historical price candles) are included in the free plan. **Resolved (D36):** price history is not included (403), so charts use Tiingo.

### D8: Python + OpenAI Agents SDK + localhost web UI
- **Choice:** A Python backend running the agents on the OpenAI Agents SDK, with a simple web UI.
- **Why:** Python has strong agent and finance libraries, and the user already knows the OpenAI Agents SDK.
- **Alternatives considered:** Claude Agent SDK; a TypeScript full stack; Python with a Streamlit-only UI.
- **Date:** 2026-09-26

### D9: User-selectable model and API key on a Settings page
- **Choice:** The user picks the LLM model for the agents and enters their own API key on a Settings page. The key is stored locally only.
- **Why:**
  - Model choice is the biggest cost lever. The user can use a cheap model for routine runs and a stronger one when they want better reasoning.
  - Entering the key in the app is friendlier than editing config files.
  - Storing it locally fits a single-user app with no login. The key is only ever sent to the model provider.
- **Alternatives considered:** A hard-coded model with the key in a `.env` file. Simpler, but no flexibility and not user-friendly.
- **Date:** 2026-09-26

**Update (2026-09-26): OpenAI models only** *(replaced by the "OpenAI and/or Anthropic" update below)*
- **Why:** The user is fine with OpenAI, and the OpenAI Agents SDK works with it natively, which keeps the Settings page simple.
- **Alternatives considered:** Multiple providers via LiteLLM. More choice, but more to build and test.

**Update (2026-09-26): default model `gpt-6-luna`**
- **Why:** Cost first (D3). It is the cheapest current OpenAI model ($0.10 input / $0.50 output per million tokens on OpenAI's pricing page, September 2026) and is positioned for agent work. The user can switch to a stronger model when they want deeper reasoning.
- **Alternatives considered:** `gpt-5.4-nano` / `gpt-5.6-luna` (about 2× the price); larger models (much more per run).
- **Temporary (ended in step 5):** until the Settings page, the key and model were read from `backend/.env`. LLM keys now come only from Settings (see below).

**Update (2026-09-26): OpenAI and/or Anthropic, models offered per available key, with prices**
- **Choice:** This reverses the "OpenAI only" update. The user enters keys for OpenAI, Anthropic or both. Settings offers only models from providers with a key, each with its price.
- **Why:**
  - The user wants to pick a model by cost: cheaper to save money, stronger when willing to spend more. Showing prices next to each model makes that trade-off visible (the cost-first goal).
  - Offering only models the user has a key for avoids choices that would fail at run time.
  - The OpenAI Agents SDK runs non-OpenAI models through its LiteLLM extension, so the agents, tools, MCP support and Tavily search (D10) stay the same.
  - Provider APIs list models but not prices, so the app keeps a small dated model catalogue with prices from the official pricing pages. It needs a manual update when prices change.
- **Alternatives considered:** OpenAI only (the earlier choice; less flexible); any LiteLLM provider (more to test, and no price data).
- **Where keys are kept (step 5):** Keys entered in Settings are stored in the local SQLite file, in plain text. That's acceptable because the app is single-user and local-only (D1, D16: the server listens on 127.0.0.1 only), the database file is git-ignored, and keys are shown masked in the UI and scrubbed from logs (D19). OS keychain storage would be safer but is more complex; revisit if the app ever leaves the local machine.
- **Keys only from Settings (2026-09-26):** Claude first added an environment-variable fallback on its own. The user chose Settings only: one clear place to manage LLM keys, as D9 intended, and no surprise of a system-wide key being used silently. Alternative considered: Settings with the environment as a fallback (convenient, but two sources of truth).
- **One model for both agents (v1 only):** The user chose a single model choice to keep v1 small and simple. Trade-off accepted: research is billed at the chosen model's price too. **Agent-specific models are planned** (added to "Parked for later"). To make that cheap to add, the code passes a model per agent internally; v1 simply gives both agents the same one.

### D10: Backend-configured research tools, with Tavily for web research
- **Choice:** The agents' tools are configured in the backend and are pluggable. v1 uses Tavily for web and market research, and Finnhub for market data. (Later: LLM keys for OpenAI and/or Anthropic are entered in Settings (D9); the search provider became neutral and chosen by config (D34, D38).)
- **Why:**
  - The user suggested Tavily. It is built for AI agents and returns clean, summarized search results with sources, which suits the decision log's "sources" requirement.
  - Keeping tools pluggable in the backend means research tools can be added or swapped (including MCP servers later) without touching the agent logic or the UI.
  - Tavily is not tied to one model provider, unlike OpenAI's built-in web search.
- **Cost note:** The free tier is 1,000 credits/month (basic search = 1 credit, advanced = 2). That is plenty for Manual mode and watchlist refreshes, but the 15-minute mode could use it up quickly, so search calls per run should be capped. Beyond the free tier the cost is about $0.008 per credit.
- **Alternatives considered:** OpenAI's built-in web search tool, which only works with OpenAI models and costs per call.
- **Date:** 2026-09-26

### D11: Simple anomaly warning instead of full scam detection
- **Choice:** The Research Agent flags an unusual price or volume jump that has no matching news as a warning in the decision log. Full pump-and-dump detection and social-media signals stay parked.
- **Why:**
  - The original idea asked for scam awareness. This covers the most common pump-and-dump sign using data we already have (Finnhub prices plus news), at no extra cost or tools.
  - The S&P 500-only watchlist (D4) already makes pump-and-dump schemes rare, so full detection isn't needed yet.
  - Social data is expensive (X's API) or noisy, and it's where scams spread. It's better added once the basic trade loop works.
- **Alternatives considered:** Full scam detection plus social signals in v1. More tools and cost before the core is proven.
- **Date:** 2026-09-26

**Update (2026-09-26): price only, about 8% threshold**
- **Why:** Finnhub's free quote has today's percent change but no volume, and volume history is a paid feature. A price jump of roughly 8% or more in a day with no explaining news still catches the most common pump-and-dump pattern at zero extra cost. The threshold lives in the Research Agent's prompt, so it is easy to tune.
- **Alternatives considered:** Paying for volume data (against the cost-first goal); dropping the warning (loses the free safety check).

### D12: Two agents: Trading Agent (decides) and Research Agent (researches)
- **Choice:** The Trading Agent owns the portfolio and makes the final call. The Research Agent is called by the Trading Agent, uses the research tools, and reports findings with sources.
- **Why:**
  - It matches the original idea of a trading agent that goes back and forth with research agents, at the smallest useful size.
  - Separating the roles keeps each agent's instructions focused, and the decision log shows what the research found versus what the trader decided.
  - In the OpenAI Agents SDK, the Research Agent can be exposed to the Trading Agent as a tool (agent-as-tool). The Trading Agent stays in control and can call it more than once.
- **Alternatives considered:** A single agent doing everything (simpler, but the decision log is less clear); several specialised research agents (closer to the original idea, but more cost; parked under "Multiple agents").
- **Date:** 2026-09-26

### D13: Tight research limits per run
- **Choice:** At most 3 Research Agent calls and 5 Tavily searches per decision run, enforced in code. Finnhub is not capped beyond its own rate limit.
- **Why:**
  - It keeps each run's cost predictable (both OpenAI tokens and Tavily credits), in line with the cost-first goal (D3).
  - Finnhub is free at 60 calls/min, so capping it adds no savings.
  - Enforcing the caps in code means the agent can't talk itself into extra research.
- **Cost math:** Manual or daily mode uses at most about 150 searches a month, well inside Tavily's 1,000 free credits. The 15-minute mode (about 26 runs per trading day, up to 130 searches a day) would use up the free tier in about a week. Past that, it costs about $0.008 per search, or roughly $1 a day at the cap.
- **Alternatives considered:** Moderate limits (5 calls, 10 searches); making the limits configurable on the Settings page.
- **Date:** 2026-09-26

### D14: Up to 20 searches for a watchlist refresh
- **Choice:** A "Refresh watchlist" run may use up to 20 Tavily searches, instead of the normal 5.
- **Why:**
  - Picking 10–20 stocks out of about 500 needs broader research than deciding buy/sell/hold on a known list.
  - Refreshes happen only when the user asks (D4), so a bigger budget per refresh stays cheap overall. 20 searches is about 2% of the monthly free tier, or about $0.16 once past it.
  - Free Finnhub data does the bulk filtering, so the paid-for searches go to the part that needs the web: current news and checks on each candidate.
- **Planned flow:**
  1. Market scan with about 5 searches: this week's market news, sector trends and upcoming earnings.
  2. Shortlist about 30 candidates using Finnhub data (price, fundamentals, recent news count), which uses no Tavily credits.
  3. Deeper checks on the top candidates with about 15 searches: recent news and red flags.
  4. Output 10–20 tickers, each with a one-line reason and sources.
- **Alternatives considered:** 10 searches (a watchlist based more on fundamentals); 5 searches (shallow, mostly household-name companies).
- **Date:** 2026-09-26

### D15: SQLite for storage
- **Choice:** One local SQLite database file for the portfolio, trades, watchlist, decision logs and settings.
- **Why:**
  - It needs no setup or server, which suits a local, single-user app (D1).
  - One file is easy to back up, inspect or reset (delete it to start fresh).
  - Python supports it out of the box.
- **Alternatives considered:** PostgreSQL (needs a server; overkill for one user); JSON files (fragile once there are many trades and logs).
- **Date:** 2026-09-26

### D16: FastAPI + React for the UI
- **Choice:** A FastAPI backend that exposes a REST API, plus a separate React frontend.
- **Why:**
  - The user preferred flexibility over the simplest setup.
  - React makes richer views easier later: portfolio charts, live-updating decision logs, and multi-exchange or multi-agent screens once parked items return.
  - A clean API boundary keeps agent and trading logic in Python, separate from the display.
- **Trade-off accepted:** Two codebases (Python and JavaScript) and a bit more setup.
- **Implementation choices (step 5):**
  - **Localhost only:** The API holds keys and has no login, so it must never listen on the network.
  - **Background runs plus polling:** Runs take 30 seconds to 5 minutes. Holding an HTTP request open that long is fragile, so the API returns immediately and the UI polls status every few seconds.
  - **One server in normal use:** `trade-sim serve` also serves the built UI, so the user runs one command. Vite's dev server is only for UI development.
  - **Exchange-timezone times:** Market hours are defined in the exchange's timezone (D24), so "opens 9:30 AM EDT" is unambiguous wherever the viewer is.
- **Alternatives considered:** FastAPI + HTMX (Python only, simplest); Streamlit (fastest to start, but awkward alongside a background scheduler).
- **Date:** 2026-09-26

---

## Engineering principles

### D17: Clean Code + Clean Architecture, kept lightweight
- **Choice:** Follow Uncle Bob's Clean Code and Clean Architecture, using three layers: core, use cases, and adapters. Dependencies point inward only.
- **Why:**
  - The user asked for these principles.
  - They fit decisions already made. Swapping Finnhub for an MCP server (D7) or adding tools (D10) should only touch adapters, never the trading rules.
  - Keeping the trading rules (D6) and limits (D13) in a framework-free core makes them easy to test (D18) and impossible for the AI to bypass.
- **Why lightweight:** It's a small app. Applying every pattern from the books would create more interfaces than features. Add structure when it earns its place.
- **Alternatives considered:** Full layered architecture with every pattern (too heavy for v1); no explicit structure (quick at first, but it tangles AI, database and rules together).
- **Date:** 2026-09-26

### D18: TDD for deterministic logic; fakes for AI wiring
- **Choice:** Test-first development for the core and use cases. Agent and tool wiring is tested with fake AI and tool responses. External APIs are mocked, with a few opt-in integration tests.
- **Why:**
  - The user asked for TDD.
  - Trading rules, fees, position caps and portfolio math are deterministic and high-stakes, which makes them ideal for TDD.
  - LLM output varies between runs, so you can't unit-test whether a pick was good. You can test that the system handles any AI output safely, for example that a 30%-of-portfolio buy is rejected.
  - Mocking external APIs keeps tests fast, free and repeatable.
- **Alternatives considered:** Testing after the code is written (weaker design feedback); testing real AI responses in unit tests (flaky and costly).
- **Date:** 2026-09-26

### D19: Explicit error handling and tracebacks
- **Choice:** Atomic trades, failed runs recorded in the decision log, typed exceptions with limited retries for external calls, tracebacks in a log file, and API keys never logged.
- **Why:**
  - The user asked for it.
  - The app depends on three external services (OpenAI, Finnhub, Tavily), so failures will happen. A failure must never leave the portfolio half-updated.
  - Showing failures in the decision log keeps the "see every decision" promise, including runs that didn't finish.
  - Tracebacks in a log file help debugging without cluttering the UI. Keeping keys out of logs protects the user's secrets.
- **Alternatives considered:** Letting errors bubble up (risks a corrupted portfolio and hidden failures).
- **Date:** 2026-09-26

### D38: Every external tool is swappable and invisible to the user
- **Choice:** Each external tool (market data, web search, price history, and future ones) is used only through an interface our app defines, with one adapter per provider, selected by config, never named in the UI, and tested with fakes.
- **Why:**
  - The user's point, raised twice (web search in D34, price history in D36): tools will change, for example Playwright instead of Tavily, or another data provider. Swapping one should mean adding an adapter and changing config, not editing the app.
  - It turns a pattern repeated case by case into a rule, so every future tool gets it by default and it's checked on every change (added to CLAUDE.md).
  - It follows from Clean Architecture (D17): the core and use cases depend on interfaces, adapters depend on providers.
- **Known gap (closed 2026-09-26):** Market data (Finnhub) sat behind interfaces but wasn't chosen by config. It now has `MARKET_DATA_PROVIDER` (default `finnhub`).
- **Alternatives considered:** Deciding per tool (the earlier approach; easy to forget).
- **Date:** 2026-09-26

---

## Architecture

### D20: Agent proposes, code validates, trades execute automatically; runs never overlap
- **Choice:** The Trading Agent returns proposed orders with reasoning. The core checks them against the trading rules, and valid ones execute immediately with no human approval. Runs are short bursts in every mode, and two runs never happen at the same time.
- **Why:**
  - **Automatic execution** matches the original idea of AI agents making trading decisions on their own. It's a simulation with virtual money, so no approval step is needed.
  - **Propose-then-validate** is how "rules enforced in code" (D6) actually works. The AI can suggest anything, but only valid orders reach the portfolio. It also makes testing simple (D18): feed in any proposal and assert the outcome.
  - **Short bursts** keep cost tied to the number of runs, not to time. Between runs the app is idle and costs nothing.
  - **No overlap** prevents two runs from trading on the same portfolio at once, which could break the cash or 20% limits.
- **Alternatives considered:**
  - Giving the agent a "place order" tool to call directly. More autonomous-feeling, but harder to guarantee the rules and harder to test.
  - A human approval step for each trade. Safer for real money, but unnecessary friction in a simulator.
  - Queueing overlapping runs instead of skipping them. Adds complexity; a skipped run is simply picked up by the next one.
- **Date:** 2026-09-26

**Update (2026-09-26): trades fill at the prices fetched at the start of the run**
- **Why:** The data is about 15 minutes delayed anyway (D7), so re-fetching a minute later adds little realism. Fetching again would double Finnhub calls per run and risk hitting the free 60 calls/min limit alongside the Research Agent's own calls.
- **Alternatives considered:** Re-fetching prices just before execution.

### D21: Block decision runs while the market is closed; allow watchlist refresh any time
- **Choice:** "Run now" is disabled while the market is closed, and "Refresh watchlist" is always available.
- **Why:**
  - The user's point: research done while the market is closed would be repeated at the next run anyway, so it wastes money.
  - Real brokers don't fill orders while the market is closed, so blocking keeps the simulation realistic.
  - A watchlist refresh is different. It isn't repeated automatically, and doing it outside market hours means the list is ready at the open.
  - Using the exchange calendar (holidays, early closes) avoids runs on days that look like weekdays but aren't trading days.
- **Alternatives considered:**
  - Research only, with no trades. Rejected by the user as wasted cost.
  - Trading at the last close price. Convenient for testing, but unrealistic. Testing is covered by fakes (D18) instead.
- **Date:** 2026-09-26

### D22: What each decision log entry shows
- **Choice:** Time and trigger, status, research findings with sources and warnings, proposed orders with reasons, the result of each order, and the run cost.
- **Why:**
  - Showing the agent's decisions was part of the original idea. This makes each decision fully traceable, from research to proposal to outcome.
  - Recording proposals and results separately shows when the rules stopped the AI (D20), which helps judge how good its decisions are (D18).
  - Logging failed and skipped runs keeps the log honest about runs that didn't finish (D19, D20).
  - Run cost makes the cost-first goal measurable, so the user can see what each mode actually costs.
- **Alternatives considered:** A minimal log with only trades and a reason (less insight into the AI's reasoning and into cost).
- **Date:** 2026-09-26

**Update (2026-09-26): "OVERALL" and "MARKET" findings**
- **Why:** A run where the agent decides to hold has no orders, so without its overall reasoning the log wouldn't show *why* it held. Storing it as a special finding reuses the existing log structure instead of adding a new field. A refresh stores the market overview the same way.

### D23: Compare returns against the exchange's benchmark index
- **Choice:** Show the portfolio's return next to the benchmark index's return over the same period (US: S&P 500 via SPY).
- **Why:**
  - Profit on its own can mislead. If the market rose 5% and the agent made 3%, it did worse than simply buying the index.
  - The benchmark answers the real question: is the AI adding value?
  - It costs nothing extra: one more Finnhub price per update.
- **Alternatives considered:** P&L only (can't tell skill from the market moving); risk metrics such as drawdown and win rate (useful later, but more than v1 needs).
- **Date:** 2026-09-26

### D24: Exchange profile, with nothing exchange-specific hard-coded
- **Choice:** One exchange profile holds the stock pool, trading hours, timezone, holiday calendar, currency and benchmark. v1 ships only the US profile.
- **Why:**
  - The user asked whether the benchmark would scale to other exchanges. It showed that several decisions (D4, D21, D23, and the currency) were quietly US-specific.
  - Tokyo and India are planned (D2). With profiles, adding them means adding data, not changing code.
  - It fits Clean Architecture (D17). The core works with "an exchange profile" and never knows which exchange it is.
- **Known risk for later:** Finnhub's free tier may cover non-US exchanges less well. Revisit when Tokyo and India come off the parked list.
- **Alternatives considered:** Hard-coding US values now and refactoring later. Faster at first, but US assumptions would spread through the code.
- **Date:** 2026-09-26

### D25: Prompts in files, and OpenAI dashboard tracing for every run
- **Choice:** Each agent's instructions live in a separate prompt file. Every run is traced with the SDK's built-in tracing and viewed in the OpenAI dashboard, with a "View trace" link from the decision log.
- **Why:**
  - The user wants to keep an eye on what the agents are told, which tools they call, and what they get back.
  - **Prompt files:** prompts are the agents' "code". Keeping them out of Python makes them easy to read, edit and review in version history.
  - **Built-in tracing** is on by default in the OpenAI Agents SDK and costs nothing to build. The prompts and responses already go to OpenAI, so no new party sees the data.
  - **Linking trace IDs** from the decision log connects the summary (what happened) to the detail (step by step how).
- **Alternatives considered:**
  - Storing and showing traces inside our app: everything in one place, but more to build.
  - Langfuse: a dedicated tool for watching agents, but one more service. The SDK allows adding it later without changing the agents.
- **Date:** 2026-09-26

**Update (2026-09-26): tracing with Anthropic models**
- **Choice:** With an OpenAI key present, all runs are traced to the OpenAI dashboard, including runs on Anthropic models. With only an Anthropic key, runs are not traced.
- **Why:** The SDK's tracing export only needs an OpenAI key, whichever model runs. There is nothing new to build. The decision log (D22) still records findings, orders and reasons, so an Anthropic-only user loses the step-by-step view, not the explanation.
- **Alternatives considered:** Switching to Langfuse (works for every provider, but one more service); storing traces in the app (works for all, but the most to build).

### D26: Build order: rules first, AI later
- **Choice:** Core rules → storage → market data → agents → API + UI → scheduler.
- **Why:**
  - The rules the AI must not break (D6, D20) exist and are tested before any AI is added.
  - It follows Clean Architecture (D17): build the core first, then add adapters around it.
  - Each step ends with something working and tested (D18), so problems surface early and in small pieces.
  - The costly parts (OpenAI, Tavily) come in only at step 4, once everything they depend on is proven.
- **Alternatives considered:** UI first (visible progress sooner, but it would be built on unproven rules); agents first (the exciting part, but no safe rules underneath).
- **Date:** 2026-09-26

### D27: Agents are MCP-ready through a config file
- **Choice:** MCP servers are optional and listed in `backend/mcp_servers.json`, each assigned to the Research and/or Trading Agent, with secrets as `${ENV_VAR}`. No file means built-in tools only.
- **Why:**
  - The user's original idea included MCP servers. None fit v1 today (see the D7 update), but good ones may appear, and the user asked for the code to be ready for them.
  - The OpenAI Agents SDK supports MCP servers per agent natively, so adding one is configuration, not code (D17: new tools are adapters, not rule changes).
  - Secrets as environment-variable references keep keys out of the config file and out of logs (D19).
  - Per-agent assignment keeps each agent's tool list focused, which helps the model choose tools well.
- **Known limitation:** MCP tool calls are not counted against the Tavily search limits (D13, D14), since each server has its own cost model. Revisit if a paid MCP server is added.
- **Alternatives considered:** Hard-coding specific MCP servers (needs code changes per server); wrapping every data source as MCP now (more moving parts with no v1 benefit).
- **Date:** 2026-09-26

### D28: Live agent activity in the app, as a step timeline
- **Choice:** While a run is in progress, the UI shows a live, one-line-per-step timeline of what the agents are doing.
- **Why:**
  - The user wants to watch the agents work inside the app, not only in the OpenAI dashboard or after the run finishes. This fits the original idea that the agents' decisions should be visible.
  - Step-level detail (which agent, which tool, with what input, a short result) is readable while it happens. Full prompts and raw responses would be too long to follow live, and remain available in the OpenAI dashboard trace (D25).
  - It is built from the SDK's step notifications in our own code, so it works for every provider, including Anthropic-only setups with no OpenAI tracing.
- **Alternatives considered:** Full detail with prompts and raw responses (too long to follow live); a progress indicator only (shows too little).
- **Live only, not saved:** The user chose to show the timeline only during the run. It keeps storage and the decision log simple; the finished run's findings, orders and reasons are already in the decision log (D22), and the step-by-step record is in the OpenAI dashboard trace when an OpenAI key exists (D25). Trade-off accepted: Anthropic-only runs have no step replay afterwards. Alternative considered: saving the timeline with each run for replay.
- **Top of the Decision log:** The live run sits where its result will land, so the user watches it and then reads the outcome without switching screens, and no extra screen is needed. Alternatives considered: a separate "Live" screen (one more screen, and you switch away for the result); a panel on every screen (always visible, but takes space from the other screens).
- **Date:** 2026-09-26

### D40: Research covers market-wide events, not only company news
- **Choice:** A free market news tool (general headlines, 25 newest, summaries trimmed). The Research Agent scans it first in every run, then reports how each stock is exposed to the events that matter. Market context is stored as a "MARKET" finding. The Trading Agent also gets the latest watchlist refresh overview and asks for market context first.
- **Why:**
  - The user asked whether research catches events beyond the company, for example a statement by the US president that moves a stock. It didn't: the Research Agent's tools and instructions were per stock (company-tagged news, quotes, metrics), and decision runs had no market step. A tariff or Fed decision reached a stock only if a search happened to find it.
  - **Exposure, not only headlines:** a headline helps only if it is connected to the stocks held or watched ("chip tariffs hit this company through its China sales"). Asking for exposure by sector, supply chain, regulation and where a company sells is what turns market news into a reason for a trade.
  - **A free tool rather than web searches:** there are only 5 web searches per run (D13) and a limited free monthly allowance (D34, D35). Finnhub's general news is on the free plan (checked 2026-09-27: HTTP 200, 100 headlines over about 3 days, including politics, geopolitics and legal news), and it uses one call per run, well within 60 calls/minute.
  - **Capped at 25 headlines, trimmed:** the feed mixes in lifestyle stories and would add many AI tokens per run at full size. The newest 25 are enough to spot the major events; the agent picks out what matters and can use a web search to follow up.
  - **Refresh overview passed on:** the watchlist refresh already writes a market overview, but decision runs never saw it. Passing it on, with its date so its age is clear, gives each run the broader picture at no extra cost.
  - **Stored as a "MARKET" finding:** it reuses the existing findings structure (D22), so the Decision log shows it with no new screens or tables.
- **Cost:** no web searches. About 3,100 extra input tokens per run for the headlines (measured 2026-09-27 with real data; about $0.0003 on the default model), plus slightly longer reports.
- **Alternatives considered:** Spending 1–2 of the 5 web searches on market news (uses the scarcest budget); a separate market agent (parked with "multiple agents", D39); putting the headlines straight into the Trading Agent's input (no reasoning about which stocks each event affects, and no sources); social media signals (still parked).
- **Date:** 2026-09-27

---

## UI design

Research input (2026-09-26): Alpha Arena (nof1.ai), where AI models trade $10k live, is closest to this app. It shows a value chart, trades, and each model's reasoning side by side. Robinhood and Zerodha Kite show how far minimalism goes (one number, one chart, essentials only), Composer always compares with a benchmark, and Alpaca keeps a reliable activity log. The user chose Alpha Arena as the main model and asked to see previews before anything is designed.

### D29: Settings behind a gear icon, on its own page
- **Choice:** A gear icon in the top-right corner opens a separate Settings page; Settings is not a tab.
- **Why:** The user's point: this is the familiar pattern in apps they use. Configuration is occasional and separate from the day-to-day trading views, so it shouldn't take a tab alongside them. One page also gives room for everything configurable, including the run mode (D3) in step 6.
- **Alternatives considered:** Settings as a tab (the draft; mixes configuration with content).
- **Date:** 2026-09-26

### D30: Watchlist as a table, one row per stock
- **Choice:** Keep the Watchlist tab and show it as a table: symbol, price, today's change, held or not, and the agent's reason with sources.
- **Why:** With only 10–20 stocks, rows are faster to scan and compare than cards: prices and changes line up in columns. Showing "held" links the watchlist to the portfolio at a glance.
- **Alternatives considered:** Cards (the draft; harder to compare); showing the watchlist on Home (crowds Home); merging watchlist and holdings into one list (mixes "can buy" with "owns").
- **Date:** 2026-09-26

### D31: Decision log as expandable rows, read as a story
- **Choice:** One collapsible row per run, newest first. The header gives the one-line outcome; opening it shows summary → orders and rule results → research → cost.
- **Why:**
  - The user found the draft hard to picture with no data. A preview with example data made it clear, and the user accepted this layout.
  - The header answers "what happened?" at a glance. Opening a row answers "why?" in the order a person asks it: what was decided, what actually traded, what evidence it was based on, what it cost.
  - Showing each order's rule result makes "the agent proposes, the code decides" (D20) visible, for example a buy rejected for breaking the 20% cap.
- **Alternatives considered:** Hiding research and cost behind a "details" link (tidier, but hides the evidence the user wants to see); a flat table of trades (loses the reasoning).
- **Date:** 2026-09-26

### D32: Home screen built around the agent, with a value chart
- **Choice:** Home shows the three key numbers, a value chart against the S&P 500, the agent's latest decision in its own words, and compact holdings.
- **Why:**
  - The user chose Alpha Arena as the model: this app exists to watch an AI trade, so its reasoning belongs on the first screen next to the results, not only on a separate tab.
  - One chart against the benchmark answers the main question ("is the AI beating the market?") at a glance, which Robinhood and Alpha Arena both lead with. It also extends D23 from a single number to a trend.
  - Holdings stay compact because the watchlist (D30) and Decision log (D31) hold the detail.
- **Alternatives considered:** A classic brokerage home, portfolio first with the AI on its own tab (the draft; the AI less central); no chart for v1 (less to build, but loses the main visual).
- **Date:** 2026-09-26

### D33: Record value history for the chart
- **Choice:** Save portfolio value and the SPY price after every run and once per trading day at the close.
- **Why:** A chart needs points over time, and the app only knew the current value. After every run captures the effect of each trade decision; the daily close keeps the line continuous on days with few or no runs (for example in Manual mode). Recording only these moments keeps Finnhub calls within the free tier.
- **Note:** The daily close snapshot depends on the scheduler (step 6); until then, points are recorded after runs.
- **Alternatives considered:** Recording on every page view (irregular points, extra API calls); intraday snapshots every few minutes (more data and calls than the chart needs).
- **Date:** 2026-09-26

### D34: The web search provider is invisible to the user and swappable
- **Choice:** The UI says "web searches" and "free monthly allowance", never "Tavily". The provider sits behind a neutral search interface and declares its own pricing, which cost estimates use. Its key is only required when it is the provider in use.
- **Why:**
  - The user's point: the person running the app doesn't know or care which search tool the agent uses, and the tool may change (for example to Playwright-based browsing or another API).
  - A preview had leaked "Tavily free tier" into the UI, which would become wrong the day the provider changes.
  - Having the provider declare its pricing keeps cost estimates correct for any provider, including free ones (allowance "unlimited", price 0).
  - This finishes what D10 started ("tools configured in the backend, pluggable"). Three Tavily-specific leftovers get fixed: the result type lived in the Tavily file, the config always required the Tavily key, and Tavily's pricing existed only in these docs.
- **Alternatives considered:** Showing the provider's name in Settings (transparent, but not needed by the user); showing no cost at all (hides what the 15-minute mode would cost).
- **Date:** 2026-09-26

### D35: Run mode cards show the real AI cost and the free-allowance status
- **Choice:** Each mode card shows the estimated AI cost in $ and, separately, whether its web searches fit the free monthly allowance (and when it would run out). Below the cards: the next scheduled run.
- **Why:**
  - The user was confused by an earlier preview that showed "~$16/month" for the 15-minute mode. Most of that was a search charge that doesn't happen on a free search plan: when the free allowance is used up, searches stop until the month resets, and the agents research with the free market data only.
  - The only cost actually billed today is the AI model's tokens (on the user's OpenAI or Anthropic account), so that is the one shown in $.
  - Showing the allowance status still warns that the 15-minute mode weakens research after about a week, which is the real trade-off.
  - Estimates follow the chosen model's prices (D9) and the search provider's declared allowance (D34).
- **Correction to the D13 cost math:** "about $0.008 per search after the free tier" applies only if the user upgrades to a paid search plan. On the free plan, searches stop instead of costing money.
- **Clarified along the way:** OpenAI's built-in web search is not used (D10 chose Tavily). It works only with OpenAI models, is charged per call, and can't be capped by our code. It could become a swappable option under D34 later.
- **Alternatives considered:** AI cost only (hides the research trade-off); no cost on the cards (hides the main difference between modes).
- **Date:** 2026-09-26

### D36: Tiingo for daily price history
- **Choice:** Stock charts use daily price history from Tiingo's free plan, fetched directly by the app through a swappable adapter and cached locally.
- **Why:**
  - The user wants a chart per stock on the Watchlist page. Finnhub's free plan has no price history: a test request returned 403 "You don't have access to this resource", confirming the risk noted under D7.
  - Tiingo has the most generous free plan for this (1,000 requests/day, 30+ years of daily prices). Caching plus a once-a-day top-up means 10–20 stocks use about 20 requests a day.
  - The "internal use only" licence suits a personal, local, single-user app (D1).
  - Charts drawn by the app (rather than embedded widgets) can later mark the agent's own trades.
  - MCP servers are tools for the agents, while charts are drawn by the app, so the app calls the API directly. The agents could later get price history via an MCP server (D27).
- **Alternatives considered:**
  - Massive: official MCP server and free end-of-day data, but only 5 requests/minute.
  - Alpha Vantage: official MCP server, but only 25 requests/day.
  - Financial Modeling Prep: 250 requests/day, less history on the free plan.
  - Embedded TradingView widgets: no key, but third-party scripts and no agent trade markers.
  - Recording our own prices: starts empty and has gaps.
- **Optional key:** Claude chose that a missing price-history key doesn't stop the app. Charts are an extra, while trading works without them, and the user can add the key later.
- **Abstraction (the user's requirement):** Tools can change, so the app depends on its own `PriceHistorySource` interface, not on Tiingo. The provider is chosen by config, with only its key required, the same pattern as web search (D34). The cache is our own table, so switching provider keeps the history already downloaded, and tests use a fake source.
- **Schema, full daily bar (the user's choice, see below):** It costs the same single request as close-only, and keeps volume available, which could finally allow the volume half of the anomaly check (D11) dropped for lack of free volume data. It also allows candlestick charts later. `adj_close` drives the line chart so stock splits don't look like crashes. `exchange` in the key keeps Tokyo and India separate (D24). The sync table records when each stock was last checked, so weekends and holidays don't trigger repeat requests.
- **Date:** 2026-09-26

### D37: Watchlist charts, a trend line per row plus an expandable chart
- **Choice:** A "Last month" trend line in every row; clicking a row opens a full chart (1M/3M/1Y, low/high, the agent's buys and sells marked).
- **Why:**
  - The user found the app empty before any trades and wanted to see how each stock has been moving. Price charts per stock are standard in trading apps.
  - Trend lines let all 10–20 stocks be compared at a glance without clicking. The expanded chart gives detail only when wanted, keeping the table compact (D30).
  - Marking the agent's trades on the price line shows *when* it acted relative to the price, which fits the app's purpose of watching the AI (D32).
- **Alternatives considered:** Trend lines only (no detail); an expandable chart only (no at-a-glance comparison).
- **Date:** 2026-09-26

---

## Roadmap

### D39: After v1, validate first, then multiple agents, then strategies
- **Choice:** 1) Run v1 for a few trading days. 2) Multiple trading agents competing, each with its own portfolio, model and history. 3) Agent-written strategies per agent, revisable in periodic reviews. Each is designed with the user before building.
- **Why:**
  - The user asked whether agents could write and revise their own strategies, and whether several agents with different models could compete. Both suit a simulator. They were already on the parked list, and Alpha Arena, the model for Home (D32), is exactly a model-vs-model comparison.
  - **Validate first:** no real decision run has happened yet. Multiplying agents before the single agent, the rules and the real costs are proven would multiply any problems too.
  - **Multiple agents before strategies:** multi-agent is the big structural change (portfolio, runs, value history, settings and screens all become per agent). Strategies are a medium change that belongs to each agent. Building strategies first would mean reworking them for multiple agents later.
  - **Known costs:** N agents means about N× the AI cost and web searches, sharing one free search allowance (D34, D35). Strategy reviews add some AI cost, limited by how often reviews may happen.
- **Alternatives considered:** Strategies first (smaller, but reworked later); both at once (too much change before the basics are proven); neither (the app would compare nothing).
- **Date:** 2026-09-27
