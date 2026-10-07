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

**Update (2026-09-28): warnings are only for anomalies and missing data**
- **Why:** In the first real decision run none of the 4 warnings was an anomaly: three were caveats ("figures are approximate", "not independently verified") and one came from the missing tickers (fixed under D40). The prompt never said what a warning is, so every doubt went there. That inflated the "warnings" badge, pushed the Trading Agent (told to treat warnings seriously) away from buying, and would bury a real manipulation warning. A failed tool or missing data stays a warning, because the Trading Agent should know when a stock wasn't actually checked; other caveats go in the summary.
- **Alternatives considered:** Anomalies only (hides that a stock wasn't checked); a separate "notes" field for caveats (a schema and UI change for little gain).

### D12: Two agents: Trading Agent (decides) and Research Agent (researches)
- **Choice:** The Trading Agent owns the portfolio and makes the final call. The Research Agent is called by the Trading Agent, uses the research tools, and reports findings with sources.
- **Why:**
  - It matches the original idea of a trading agent that goes back and forth with research agents, at the smallest useful size.
  - Separating the roles keeps each agent's instructions focused, and the decision log shows what the research found versus what the trader decided.
  - In the OpenAI Agents SDK, the Research Agent can be exposed to the Trading Agent as a tool (agent-as-tool). The Trading Agent stays in control and can call it more than once.
- **Alternatives considered:** A single agent doing everything (simpler, but the decision log is less clear); several specialised research agents (closer to the original idea, but more cost; parked under "Multiple agents").
- **Date:** 2026-09-26

**Update (2026-09-28): the Research Agent never gives a buy, sell or hold verdict**
- **Why:** In the first real decision run almost every stock finding ended with a verdict such as "does not establish that shares are attractive to buy today". Fourteen of those pushed the Trading Agent towards holding before it had decided anything. The prompt said "You never decide trades" in the role but its reporting rules didn't say what to leave out, so one explicit line was added there.
- **Alternatives considered:** Also changing how the Trading Agent words its requests (not needed if the Research Agent holds the line itself); removing verdicts from findings in code (brittle text matching).

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

### D45: A visual agent map, kept in sync with the code
- **Choice:** An HTML page, `docs/agent-map.html`, published as a private link. Its numbers are filled from the code automatically; a drift check fails when the agents' structure changes without the page.
- **Why:**
  - The user built the app with Claude and still didn't know what a "turn" was or what each agent remembers. People won't read ARCHITECTURE.md; they need a picture.
  - A hand-drawn page goes out of date quietly, so the numbers are generated and the structure is checked.
  - It is a summary for people, simplified on purpose (e.g. an illustrative run). Treating it as a source could spread its simplifications into decisions, so the agent reads the code and the decision docs instead.
- **Alternatives considered:** Mermaid in ARCHITECTURE.md (written for code readers, not people); a screen in the app (a new UI to design and maintain); a one-off page (goes stale silently); a fully generated diagram (how to draw a new tool or job needs judgement, so only the numbers are generated).
- **Date:** 2026-10-03

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

**Update (2026-09-28): buttons disabled on click; "run in progress" is not an error**
- **Why:** The user double-clicked "Run now". The second request arrived while the first run was going, was refused (correctly), and left a red "Another run is still in progress" banner that stayed after the run ended. Disabling both buttons as soon as one is clicked stops the second request. When a run is already going (for example a scheduled one), the page now shows it as in progress, because nothing has gone wrong.
- **Alternatives considered:** Only clearing the banner when the run ends (the double-click still sends a pointless request); debouncing the click (less direct than disabling).

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

**Update (2026-09-28): only links a tool returned are kept as sources**
- **Why:** The agent writes its `sources` by copying links out of tool results, and nothing checked them. In the first real decision run one Finnhub link came out cut short (a 34-character ID instead of 64), and a made-up link would have got through the same way. The log exists to show real evidence, so during a run the app now remembers every link any tool returned (MCP tools included, D27), and when findings, the market overview and watchlist picks are saved, any other source is dropped. A garbled link disappears rather than being repaired; the finding keeps its other sources.
- **Alternatives considered:** Short reference tags that the code swaps for full links (fixes the copying itself, but a bigger change across every tool); leaving it (1 bad link in about 40, no effect on trades).

**Update (2026-09-30): each finding saves the stock's price and day change**
- **Why:** The Decision log shows a coloured price chip per stock (D31), which needs the numbers as data. Until now they existed only inside the agent's sentence. The app remembers the quotes the quote tool returned during the run and attaches them when findings are saved, so the numbers are the tool's, not the agent's retelling.
- **Alternatives considered:** Reading the price out of the summary text (breaks whenever the agent words it differently); asking the agent to return price fields (it can miscopy them, as it did with a link).

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

**Update (2026-09-28): the first request names the symbols**
- **Why:** In the first real decision run the first request asked how market events affect "the watchlist" but named no tickers. The Research Agent sees only the request text, so it reported "no watchlist tickers were included", and the Trading Agent spent a second of its three calls on the stocks, which also produced a second, overlapping MARKET finding. One precise prompt change fixes the cause; if duplicates still appear, they will be handled then.
- **Alternatives considered:** Having the code attach the whole watchlist to every research request (reliable, but takes away the Trading Agent's choice of which stocks to research in which call, and makes every call cover all of them).

### D41: The Trading Agent is given a goal, not a strategy
- **Choice:** The Trading Agent's prompt states one goal: beat the S&P 500 (SPY) over time, with holding cash counted as a decision judged against that goal. The line "Prefer holding over trading when evidence is weak" is removed.
- **Why:**
  - In the first real decision run (2026-09-28) the agent held all $10,000 in cash, waiting for "a clear buy-today catalyst", and gave avoiding the $1 fee as a reason. The prompt told it to prefer holding but never said what it was trying to achieve, so doing nothing always looked safest. Yet the portfolio is measured against SPY (D23), so staying in cash is also a bet.
  - **A goal, not a strategy:** how to invest (pace, caution, sizing) is for the agent to work out from its own past runs, which is the D39 roadmap's "agent-written strategies" step. "Prefer holding" was a strategy we had chosen for it.
  - **Kept minimal:** two sentences, because extra guidance can backfire. Rash trades are still limited by the code-enforced rules (D6), "base decisions on the research" and "do not buy on a manipulation warning".
- **Alternatives considered:** Adding a "build positions gradually" rule (a strategy; left to the agent); a minimum invested amount (would force buys on days when caution is right); leaving the prompt as it was until more runs had been collected (the bias would likely have shown up in every run).
- **Date:** 2026-09-28

### D42: The Trading Agent is told why it holds each stock and how it is doing
- **Choice:** At the start of every decision run the agent's input includes, for each holding, its gain or loss on cost and each buy behind the current position with the reason given then; plus one line with the portfolio's return and SPY's since tracking began. A lookup tool for deeper history is a second phase, decided after a few runs.
- **Why:**
  - The agent started every run with no memory: it saw what it held but not why it bought it, and not whether it was beating SPY, which is its goal (D41). It could not ask "is my reason for owning this still true?".
  - **Always included, not behind a tool:** this is needed on every run and is only a few lines. Behind a tool, the cheapest model would sometimes not ask and decide blind, and each call costs an extra model turn.
  - **Exact:** the app reads the trades and reasons from the database (`order_results`); no model recalls or summarises them.
  - **Facts, not a strategy (D41):** the agent gets its own record and one line asking it to check its reasons. What to do about it stays the agent's call.
  - **The user asked for a tool** the agent can choose to use. That fits the larger, occasional data (closed positions, rejected orders), so it is kept as phase 2 and built only if phase 1 is not enough.
- **Cost:** a few lines per holding on every run, well under a tenth of a cent on the default model. One more price lookup per run (SPY).
- **Alternatives considered:** Tool only (the agent may not call it); carrying over earlier research findings (much more text per run; the reason is the part that matters); no memory (the state before this).
- **Date:** 2026-09-30

**Update (2026-09-30): the Research Agent gets the reasons too**
- **Choice:** The app adds the holdings and the reason each was bought to every research request in a decision run, ending with: report the facts that bear on these reasons; the Trading Agent judges.
- **Why:**
  - The Research Agent sees only the request the Trading Agent writes. In run 2026-09-30 13:55 the Trading Agent asked whether any thesis had broken without saying what the theses were. The Research Agent noted they "were not provided" and still wrote "no material change to the thesis" on all 15 stocks, and the Trading Agent held on that answer.
  - **Done by the app, not by a prompt line:** it then happens on every request, and the reasons are exact. Asking the Trading Agent to pass them on would depend on the cheapest model complying (see PROMPT_LOG.md).
  - **Facts only (D12):** the closing sentence keeps the judgement with the Trading Agent.
- **Alternatives considered:** A prompt line telling the Trading Agent to include the reasons (unreliable); leaving the Research Agent without them (it cannot check a reason it was never given).

### D43: The Trading Agent writes and revises its own strategy, in a separate review
- **Choice:** The Trading Agent owns its strategy. It writes and revises it in a **strategy review**, a step separate from the trading run, with its own prompt file and the same model; trading runs follow the current version. The code computes each version's results and the agent judges them. No evaluator agent and no internet search for strategies for now. Being designed one decision at a time; not built.
- **Why:**
  - **The agent that follows the strategy should write it.** It explains each trade against the strategy, so it is accountable for both. If another agent wrote it, a bad result could be blamed on the strategy or on how it was followed, with no way to tell which. This also matches D41: how to invest is for the agent to develop.
  - **Fits multiple agents later (D39):** each competing agent should be judged on its own thinking, strategy included. A separate strategist would need one copy per agent on the same model, or the comparison gets muddied.
  - **A separate review, not inside every trading run:** each version then runs unchanged for a stretch, so its results can be judged; a strategy changed every run can't be. It also keeps the trading run short (D20).
  - **Self-grading bias is limited by facts:** return against SPY, trades won and lost, fees and cash held are computed by the code, so the agent can't tell itself a better story. An evaluator agent on the same model would share the agent's blind spots; on another model it adds cost and another thing to debug; and with only weeks of data no one can judge well. The user can see every version and its results.
  - **No strategy search:** the model already knows the standard strategies (momentum, value, mean reversion, sector rotation) from training; searching would mostly return the same ideas, often from hype articles. It would use the free search allowance (D34, D35) and bend D12, since strategy articles are advice, not facts. What the model can't know is its own record, which the app supplies.
- **Alternatives considered:** A separate strategy agent (splits accountability; muddies the multi-agent comparison); revising the strategy inside each trading run (nothing could be judged); an evaluator agent now (parked: if added, it only writes a critique the Trading Agent reads, triggered by self-defence in about three reviews); internet search for strategies (parked: revisit if strategies look thin or repetitive).
- **Date:** 2026-10-01

**Update (2026-10-01): when reviews happen**
- **Choice:** The first strategy comes from a "Review strategy" button (or automatically if a trading run finds none). Each version then runs at least 10 trading days and 5 trading runs before any review; after that, a weekly scheduled review (Friday after the close) or the button. A review may keep the strategy. No override; both minimums are code settings.
- **Why:**
  - A strategy needs time to show results; reviewing it again and again adds noise and cost, not information (the user's point).
  - **Both minimums:** days alone don't work across run modes (Manual may run once a week, 15-minute mode about 26 times a day), so a version needs both time and real decisions to judge.
  - **Schedule and button:** the schedule keeps reviews regular so versions get comparable stretches; the button covers the first strategy.
  - **No override:** a sharp market move is when an impulsive rewrite is most tempting.
- **Alternatives considered:** Schedule only (no way to write the first strategy on demand); button only (irregular reviews); a day minimum alone or a run minimum alone; an emergency override.

**Update (2026-10-01): what a strategy contains**
- **Choice:** Plain words in five fixed sections: *What I look for*, *Position size*, *When I sell*, *Cash and pace*, *How I'll know it's working*. About 60 words per section (a code setting). Guidance only; D6 stays the only enforced rules.
- **Why:**
  - **Comparable versions:** a change reads section by section ("sizing went from 15% to 8% because…"), not as two essays.
  - **Traceable trades:** a trading run can name the section each order follows.
  - **The test is set before the results:** "How I'll know it's working" is checked at the next review against the code's numbers, so the agent can't move the goalposts afterwards. This limits self-grading bias.
  - **Word limit:** keeps the strategy specific and cheap to include in every trading run.
- **Alternatives considered:** Free text (vague, hard to compare); numbers enforced by code (turns the strategy into rules, mixes with D6, and limits the agent to the fields we thought of).

**Update (2026-10-01): what the review is given, and where history is stored**
- **Choice:** The goal, rules, portfolio, watchlist and latest market overview; for an existing version also the current strategy, a code-computed scorecard for its period, every order with its reason, and all previous versions (the previous one in full, older ones compact) with the reasons for each change or keep. No research findings or Research Agent calls. Stored in two new tables, `strategy_versions` and `strategy_reviews`, with each trading run recording the version it followed.
- **Why:**
  - **All previous versions, with their reasons** (the user's point): the agent sees what it already tried, why it dropped it, and whether the replacement did better, so it doesn't go round in circles. "Keep" decisions teach as much as changes.
  - **Cost stays small:** about 500 words per version, at most one review every two weeks.
  - **Exact:** the scorecard is computed by code and the reasons are read from the database, as in D42.
  - **No research:** the review is about its own record; the reasons on each order already capture what mattered, and no web searches are used.
  - **Scorecard saved, not recomputed:** the history shows exactly what the agent saw when it decided, even if a calculation changes later.
  - **Version on each run:** lets the code count the runs per version (the 5-run minimum) and build each version's scorecard.
- **Alternatives considered:** Only the last two versions (loses older lessons); every version in full (grows faster for little gain); letting the review call the Research Agent (costs searches, off the point); recomputing scorecards on demand (history could drift from what the agent saw).

**Update (2026-10-01): what the review returns**
- **Choice:** A verdict on the last prediction, whether the strategy was followed, keep or change, a reason, and if changed the full new version with one sentence per changed section. Checked by code before saving; on failure nothing is saved and the review is logged as failed.
- **Why:**
  - **"Was it followed?"** separates a bad strategy from one that wasn't followed, which the self-grading concern needs.
  - **Verdict first,** against the scorecard, so the agent judges the old version before defending or replacing it.
  - **Per-section reasons** keep the version history readable.
  - **Check, and nothing saved on failure:** a bad answer never replaces a working strategy.
- **Alternatives considered:** Only keep/change plus a reason (can't tell a bad strategy from one not followed); saving output that fails the check, or retrying until it passes (could replace a working strategy; retries add cost).

**Update (2026-10-01): how trading runs use the strategy**
- **Choice:** The app adds the current strategy to every trading run's input. Each order names the section it follows, or is marked "deviation" with a reason; deviations are allowed and reviewed. The run summary says how the run followed the strategy.
- **Why:**
  - **Supplied by the app, not a prompt line:** always present and exact, as in D42.
  - **Section per order:** makes "was it followed" checkable at review time.
  - **Deviations allowed but marked:** real news can justify breaking the strategy. Forbidding deviations would push the agent to hide them in vague reasons; marking makes them visible and reviewable.
- **Alternatives considered:** Forbidding deviations or blocking them in code (turns the strategy into rules; breaks get hidden rather than reported); no section per order (following can't be checked); the strategy in the prompt file (it changes every version, so it belongs in the input).

**Update (2026-10-01): limits**
- **Choice:** One AI call with no tools; never overlaps a trading run or refresh; allowed any time; a failed review doesn't count and isn't retried automatically; a missed scheduled review gets one catch-up at start-up.
- **Why:**
  - **One call, no tools:** the review is about its own record, so it stays cheap (about a cent or less on the default model) and uses no web searches.
  - **No overlap:** the strategy and portfolio stay consistent while a review reads them.
  - **Any time:** the scheduled slot is after the close anyway.
  - **Failed reviews don't count:** a technical failure shouldn't block the next real review or lock in a strategy.
  - **One catch-up:** matches how the scheduler already handles a missed run.
- **Alternatives considered:** Research during reviews (costs searches, off the point); reviews only while the market is closed (blocks the button for no gain); automatic retries (cost, and the same failure again); skipping a missed review until next week (the strategy goes unreviewed past its period).

**Update (2026-10-01): details fixed while building the scorecard and timing**
- **Choice:** The weekly slot is the week's last close plus 15 minutes; every sell counts as a closed trade; value points (D33) also record the cash held.
- **Why:**
  - **Last close + 15 minutes:** "Friday after the close" needs an exact time. The delay lets the day's closing value be recorded first, so the scorecard includes the day; using the week's last close handles Friday holidays.
  - **Every sell:** each sell locks in a gain or loss, including "take half off"; counting only full exits would hide them.
  - **Cash on value points:** average cash needs the cash held over time, which wasn't recorded. Older points have none; if none in the period, today's share is used.
- **Alternatives considered:** Exactly at the close (the closing value might not be recorded yet); only full exits as closed trades (hides partial sells); rebuilding cash from the trade history (more code for the same number).

**Update (2026-10-02): a failed first strategy, and section names from the code**
- **Choice:** If the review a trading run starts to write the first strategy fails, the run trades without one and the next run tries again. The section names in the prompts are filled in from the code, each section is shown with its name in the input, and a test checks that the answer formats allow exactly the core sections.
- **Why:**
  - **Trade without one:** this only happens before any strategy exists. One bad answer shouldn't stall trading; the failed review is logged on the Strategy tab. Once v1 exists there is always a strategy (a later failed review keeps the current one).
  - **Names from the code:** the user noticed the names were typed by hand in the code, the answer format and the prompts, which could drift apart. Placeholders and a test make a rename fail a test instead of breaking runs. The prompt wording stays in the prompt files (D25).
  - **No memory:** the user asked whether the agent remembers its strategy. It doesn't; the app supplies it in every run's input, and the prompt now says so.
- **Alternatives considered:** Skipping the trading run until a strategy exists (a broken model setup would stop trading entirely); keeping the hand-typed names (silent drift).

**Update (2026-10-01): "targets" instead of "prediction"**
- **Choice:** Section 5 is renamed *My targets for this period* (was *How I'll know it's working*); the review's verdict on it is **met / partly met / missed** (was came true / partly / didn't).
- **Why:** The user asked what "prediction came true" meant; "targets" says the same thing more plainly. The targets are still set before the results exist, so the strategy is judged against what it promised. The verdict is the agent's judgement against the code's scorecard, not a code check (the targets are plain words); the user sees both in the history.
- **Alternatives considered:** Keeping "prediction" (unclear); numeric targets checked by code (would turn section 5 into a form, as with the rejected code-enforced numbers).

**Update (2026-10-07): what happened after the trades, and the holds**
- **Choice:** The review's scorecard adds each order's move up to the review against SPY over the same days (for sells, the move since selling), the move of each watchlist stock not bought, and one line per trading day (counts, and that day's last run summary). Computed by code, saved with the scorecard, not shown on screen for now.
- **Why:**
  - **Outcomes, not just results:** the scorecard showed the gain on each sale, but not whether selling was early, or whether the stocks it passed on did better. Without that the agent can't tell a bad buying rule from a bad selling rule.
  - **Holds were invisible:** only orders reached the review, so a sell rule that should have fired but didn't couldn't be caught in "was it followed?".
  - **Code, not the agent:** it is arithmetic on stored prices; code is exact, free and can't be argued with (same reason as the scorecard).
  - **Up to the review, with the days shown:** simple and always available; showing the days and SPY's move stops a one-day-old order looking like a verdict.
  - **One line per day, not per run:** in 15-minute mode a week has about 130 runs, mostly identical holds; per day keeps it to about ten lines in any mode. The day's last summary is the agent's latest view of its holdings. Runs that traded are already covered by the orders and their reasons.
  - **Failed runs left out:** they come from tool or connection problems, not decisions, and would push the strategy to react to limits that may change.
  - **Saved, not recomputed:** "now" prices are only true on the review day, and history may be corrected later.
  - **Review only:** trading runs are unchanged; the facts reach trading through the strategy the review writes.
- **Alternatives considered:** The agent working this out from raw prices (costly, error-prone, open to self-serving reading); a fixed span such as 5 days after each order (recent orders get no number); every run's summary (thousands of words in 15-minute mode); recomputing on demand (drifts from what the agent saw); showing it on the Strategy tab now (needs a layout agreed first; can follow later).
- **Date:** 2026-10-07

---

## UI design

Research input (2026-09-26): Alpha Arena (nof1.ai), where AI models trade $10k live, is closest to this app. It shows a value chart, trades, and each model's reasoning side by side. Robinhood and Zerodha Kite show how far minimalism goes (one number, one chart, essentials only), Composer always compares with a benchmark, and Alpaca keeps a reliable activity log. The user chose Alpha Arena as the main model and asked to see previews before anything is designed.

### D29: Settings behind a gear icon, on its own page
- **Choice:** A gear icon in the top-right corner opens a separate Settings page; Settings is not a tab.
- **Why:** The user's point: this is the familiar pattern in apps they use. Configuration is occasional and separate from the day-to-day trading views, so it shouldn't take a tab alongside them. One page also gives room for everything configurable, including the run mode (D3) in step 6.
- **Alternatives considered:** Settings as a tab (the draft; mixes configuration with content).
- **Date:** 2026-09-26

**Update (2026-09-29): a read-only "Trading rules" card**
- **Why:** The user asked how a person would remember rules that live only in the code, such as "buy only watchlist stocks, sell anything you hold". The app never showed them; they appeared only in the docs or when an order was rejected. A short card at the bottom of Settings lists them in plain words. The fee and the per-stock cap come from the same rules object the trade checks use, so the numbers can't drift from the code.
- **Alternatives considered:** Docs only (easy to forget they exist); a card on Home (the rules rarely change, so they don't belong on the daily view); an info icon next to "Run now" (hidden and awkward for a list).

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

**Update (2026-09-28): a Copy button per run**
- **Why:** The user wants to paste runs to an AI for analysis. Selecting text by hand misses the full source URLs (only site names are shown) and is awkward across collapsed sections. Plain text works in any chat and is still readable for a person.
- **Alternatives considered:** Copying JSON (complete but noisy to read); one "Copy all runs" button (too long to paste; one run is the usual unit of analysis).

**Update (2026-09-30): research sits with the order it explains; the rest is one line each**
- **Choice:** An open run reads: decision summary → each order with its result, reason and the research on that stock → market overview → other stocks researched, one line each, opened by a click → cost.
- **Why:**
  - The first real run listed 15 findings as full paragraphs. Four explained the trades; the rest were stocks the agent looked at and left alone. The user had to hunt for the evidence behind each trade.
  - Putting the research under its order answers "why this trade?" in one place.
  - Nothing is removed: the other findings are one click away, a finding with a warning starts open, and Copy still gives the full run for AI analysis.
- **Alternatives considered:** Hiding all research behind one "details" link (rejected before, and still: it hides the evidence for the trades); keeping the flat list (complete, but the trades' evidence is buried).

**Update (2026-09-30): colour with one meaning, and price chips**
- **Choice:** Green = up or buy, red = down or sell, as on Home. A chip with price and day change on every stock (grey under 0.05%, explained on hover), a coloured edge on each order, a tinted box for the market overview, and the other stocks sorted from biggest fall to biggest rise.
- **Why:**
  - The user found the log too much plain text to read. Agreed from a preview of the Sep 28 run.
  - The chips let the user scan the stocks the agent left alone by colour, without reading; sorting puts the biggest movers at the two ends.
  - Hover keeps the chip short. Trade-off accepted: no explanation on a touch screen.
- **Alternatives considered:** Highlighting words inside the findings (busy, and the app would have to guess which words matter); writing "today" on every chip (repeats on every line).

**Update (2026-10-02): strategy version and section tags (D43)**
- **Choice:** Each trading run's header shows its strategy version, linking to the Strategy tab; each order shows the section it followed (grey) or "Deviation" (amber). Copy includes both.
- **Why:** The user asked whether, weeks later, they could see which strategy a run followed. The version is already stored on each run. The section tags show at a glance whether each order followed the strategy, which is what the review's "was it followed?" verdict judges, so the user can check it.
- **Alternatives considered:** No version on runs (the user would work it out from dates); sections only on the Strategy tab (the order and its basis would be in two places).

### D32: Home screen built around the agent, with a value chart
- **Choice:** Home shows the three key numbers, a value chart against the S&P 500, the agent's latest decision in its own words, and compact holdings.
- **Why:**
  - The user chose Alpha Arena as the model: this app exists to watch an AI trade, so its reasoning belongs on the first screen next to the results, not only on a separate tab.
  - One chart against the benchmark answers the main question ("is the AI beating the market?") at a glance, which Robinhood and Alpha Arena both lead with. It also extends D23 from a single number to a trend.
  - Holdings stay compact because the watchlist (D30) and Decision log (D31) hold the detail.
- **Trade markers (2026-09-30):** Each run that traded gets a dot on the agent's line (green bought, red sold, half and half both), on the value point recorded right after that run (D33). Hover lists the trades and a click opens the run in the Decision log.
  - The user found the chart didn't show when the agent acted: a flat line then a drop gave no clue that the drop followed a set of buys.
  - It matches the Watchlist charts' buy/sell markers (D37), so both charts read the same way.
  - Trades come with `/api/history` instead of from the loaded runs, which stop at the latest 50, so older markers still show.
  - Alternatives considered: markers on every run, trading or not (noise, since most runs may hold); vertical lines across the chart (clutter the benchmark line); a separate trades strip under the chart (more space for the same information).
- **Live "now" point (2026-10-07):** The chart ends with a point for the current moment, taken from the same prices as the three numbers. It is shown but not saved; saved points still come only from D33.
  - The user saw the chart with SPY's line ending above the agent's while the boxes said the agent was ahead. Both were correct, but for different moments: the chart stopped at the last run (Oct 6), and the numbers were live (Oct 7).
  - Showing the same moment in both removes the cause. A note like "Graph as of last run" would only explain the gap.
  - The last stretch is lighter and dashed because it will move as prices change; the rest is saved history. (SPY's line is already dashed, so lighter is what sets its live stretch apart.)
  - Alternatives considered: a note under the chart (a workaround, the two still disagree); saving a point on every page view (rejected in D33: irregular points and extra price calls).
- **Period buttons and hover (2026-10-07):**
  - The chart gets a point after every run, about 500 a year in Daily mode and 6,700 in Every-15-minutes mode. Drawn all at once, the lines blur and the trade markers pile up.
  - Buttons match the Watchlist charts (D37), so both charts work the same way. 1M is the default because it shows recent decisions with enough history to judge them.
  - One point per day beyond 1W keeps a year at about 250 points. 1W keeps every run so each decision's effect is visible.
  - Hover gives exact numbers without crowding the chart, and shows who was ahead at any moment, the question that started this change.
  - The three numbers stay "since start" because that is the main score. The period line answers "how did this month go" without replacing it.
  - Even spacing is kept: spacing by real time would make nights and weekends long empty stretches.
  - Alternatives considered: always showing everything, thinned (recent days squashed); a fixed last-month window (full history never visible); every run in every period (unreadable in 15-minute mode); one point per day everywhere (loses each run's effect); numbers that follow the period (the since-start score disappears).
- **Alternatives considered:** A classic brokerage home, portfolio first with the AI on its own tab (the draft; the AI less central); no chart for v1 (less to build, but loses the main visual).
- **Date:** 2026-09-26 (trade markers added 2026-09-30, live "now" point 2026-10-07, period buttons and hover 2026-10-07)

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

### D44: The strategy gets its own tab
- **Choice:** A fourth tab, **Strategy**, holding the current strategy, the "Review strategy" button with when the next review becomes possible, and the history of versions and reviews. Layout agreed from a preview before building.
- **Why:** The strategy is something you read and return to, with a history behind it, like the Watchlist, so it needs a fixed place. Links from other screens can still point to it.
- **Alternatives considered:** A section on Home (makes Home long; the history doesn't fit); reviews in the Decision log only (the current strategy would have no fixed place to read it).
- **Date:** 2026-10-01

**Update (2026-10-01): layout agreed from a preview**
- **Choice:** Review bar (version, button, when a review is possible, progress bars for the minimums) → four numbers for the current version → the five sections with changes tagged and targets in a tinted box → review history as expandable rows with Targets and Followed tags.
- **Why:**
  - **Review bar** answers "when can it review?" without the user counting days and runs.
  - **Four numbers** answer "is it working?", including whether the strategy is being followed.
  - **Tagged changes** with a line on why keep versions comparable at a glance.
  - **History rows** follow the Decision log pattern the user already knows (D31), with room for the reasons.
- **Alternatives considered:** No progress bars (the user would work out the minimums); history as a table (too little room for reasons).

**Update (2026-10-02): reviews stay off the Decision log**
- **Choice:** Strategy reviews are not Decision log rows; a review in progress still shows its live timeline there (D28). A run's version tag opens this tab at that version.
- **Why:** The Decision log stays about trading, and the review history already has a full home here. The version tag on each run answers "which strategy was this run following?" weeks later (the user's question).
- **Alternatives considered:** Reviews as Decision log rows (the same history in two places).

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

**Update (2026-10-01): strategies before multiple agents**
- **Choice:** Agent-written strategies (D43) are step 2, multiple agents step 3. Replaces the "multiple agents before strategies" order above.
- **Why:** The user wanted to work on strategies next. The rework is small: the strategy is stored in its own table, and going multi-agent later adds an agent column to it, as every other table will need. It also shows whether a written strategy improves the agent before paying for N agents. The cost: the screens showing strategy versions will need a per-agent pass later.
- **Alternatives considered:** Keeping the original order (multiple agents first).
