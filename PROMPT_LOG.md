# Trade Simulator: Prompt log

> Why each line in the agent prompts (`backend/prompts/*.md`) is there, and whether it worked.
> Read the entries for a prompt before changing it. The rules for changing a prompt are in [CLAUDE.md](CLAUDE.md).
> Decisions (D#) are explained in [WHY.md](WHY.md); this file only tracks the prompt wording.

## How to use this file

- **Before changing a prompt:** read the entries for the lines you would touch. A line that looks redundant may be there because a run went wrong without it.
- **After changing a prompt:** add an entry at the bottom of "Changes" in the same step. Leave "Result" as "Not seen yet".
- **After reviewing a run:** fill in or update "Result" on the entries that run tested, and add anything new to "Open observations" with the run's date. Do not change a prompt for it yet.
- **Runs are named by their start time in UTC**, as shown in the Decision log's copied text.

## Changes

Oldest first. Entries before 2026-09-27 come from the Changelog in PROBLEM_STATEMENT.md, because the prompts were not yet under version control; their exact wording at the time is not recorded.

### 2026-09-26 · all three prompts · no links in the text
- **Line:** "Write summaries as plain sentences. Never put links, URLs or Markdown in the text; URLs go only in `sources`." (research); the matching line in the trading and refresh prompts.
- **Cause:** In the first real watchlist refresh the agent wrote Markdown links into the market overview.
- **Expected:** Plain text in summaries, links only in the sources list.
- **Result:** Worked. No links in the text of the runs on 2026-09-28 and 2026-09-30. The app also moves any stray link into sources, so this line is backed by code.

### 2026-09-27 · research_agent.md, trading_agent.md, refresh_watchlist.md · market context (D40)
- **Line:** The "Market context" section of the research prompt; "Weigh market-wide events as well as company news…" and the rule that the first research request asks for market context (trading).
- **Cause:** Research covered company news only, so rates, oil, tariffs and politics were missing from decisions.
- **Expected:** One `MARKET` finding per run, and each stock's finding says how it is exposed.
- **Result:** Worked: every decision run since has a `MARKET` finding. Side effect: the same general caveat was repeated on every stock (see 2026-09-30, research).

### 2026-09-28 · trading_agent.md · a goal instead of "prefer holding" (D41)
- **Line added:** "# Goal: Beat the S&P 500 (SPY) over time. Holding cash is also a decision, judged against this goal."
- **Line removed:** "Prefer holding over trading when evidence is weak. Every trade costs a fee, so trade with a reason."
- **Cause:** Run 2026-09-28 13:37 held all $10,000 in cash and gave avoiding the $1 fee as a reason.
- **Expected:** The agent invests when the research supports it, and treats cash as a choice to justify.
- **Result:** Worked. Run 2026-09-28 15:28 bought four positions and kept about half in cash. Watch the other direction: runs 2026-09-28 15:28, 2026-09-30 13:30 and 13:50 all bought; run 13:55 held.

### 2026-09-28 · research_agent.md · facts only, no verdict (D12)
- **Line:** "Report facts, risks and exposure only. Never say whether a stock is worth buying, selling or holding; that is the Trading Agent's call."
- **Cause:** In run 2026-09-28 13:37 the Research Agent gave buy/hold opinions.
- **Expected:** Findings state facts; the Trading Agent judges.
- **Result:** Mostly worked. In run 2026-09-30 13:55 the Research Agent wrote advice-like text ("reasons a cash allocation could preserve flexibility") after the Trading Agent asked it for a judgement.

### 2026-09-28 · trading_agent.md · name the symbols in the first request (D40)
- **Line:** "…how it affects your holdings and watchlist, naming their symbols."
- **Cause:** In run 2026-09-28 13:37 the first research request named no stocks, which wasted a research call.
- **Expected:** The first request lists the symbols, so one call covers them.
- **Result:** Worked. Every run since has findings for all holdings and watchlist stocks.

### 2026-09-28 · research_agent.md · warnings only for anomalies or missing data (D11)
- **Line:** "Use `warnings` only for an unusual price jump (see Anomaly check) or when a tool failed or had no data for that stock. Put other caveats in the summary."
- **Cause:** In run 2026-09-28 13:37 every warning was an ordinary caveat.
- **Expected:** A warning means something is wrong, so the warning count in the log is meaningful.
- **Result:** Worked. No caveat warnings since. CEG fell 5.87% in run 2026-09-30 13:55 and correctly got no warning (threshold is about 8%).

### 2026-09-30 · research_agent.md · skip exposure every stock shares
- **Line changed:** "If a stock is not exposed, you don't need to mention it." → "Skip exposure that every stock shares, such as higher rates weighing on valuations, and cite the market sources only in `MARKET`."
- **Cause:** In run 2026-09-28 15:28 nearly all 14 findings repeated "higher yields can weigh on valuations" and cited the same market article.
- **Expected:** Per-stock findings carry only what is specific to that company.
- **Result:** Partly worked. In runs 2026-09-30 13:50 and 13:55 the yield caveat and the repeated market source were gone. A new repeat took their place: "No direct link to Iran/oil was identified" on about seven stocks, because the step still says to state *whether* a stock is exposed.
- **Note:** Changed after a single run. Under the rules now in CLAUDE.md this would have waited.

### 2026-09-30 · trading_agent.md · check the reason for each holding (D42)
- **Line added:** "For each holding, check whether the reason you bought it still holds."
- **Cause:** Built with D42. The agent's starting input now lists, for each holding, when it was bought and the reason given then. Before that it had no memory of its reasons.
- **Expected:** Each run compares today's research with the original reason before holding or selling.
- **Result:** Partly worked. Run 2026-09-30 13:50 showed no review of holdings. Run 13:55 held "because research found no material thesis break", but the Trading Agent had asked the Research Agent to judge without passing on the reasons, so nothing compared the news with the actual reasons. Fixed in code the same day, not in the prompt: the app now adds the holdings and their reasons to every research request (D42 update). Run 2026-09-30 14:32, the first with that fix: worked. The findings for the holdings addressed the actual reasons (JPM's P/E and yield re-checked against the figures in the reason; ABBV's launch timing; MSFT's Copilot release confirmed; a new competitive risk found for NVDA), and the Trading Agent's summary weighed them by name. WMT was the weak one: its reason was "relative resilience in the weaker market" and the finding did not compare it with the market. The Research Agent gave no buy/sell/hold verdict; it did write assessments such as "leave the buyback rationale intact". Cost rose: 115k input tokens and all 5 web searches, against 80k and 4 two runs earlier.

### 2026-10-02 · strategy_review.md · new prompt (D43)
- **Line:** The whole file: role (the Trading Agent reviewing its own strategy, not trading), the goal and rules repeated from the trading prompt, the five sections with the word limit, the review order (targets verdict, followed verdict, keep or change, per-section reasons), "don't recompute or dispute the scorecard", "a short period is mostly noise", and the output fields.
- **Cause:** Built with D43. No run yet.
- **Expected:** First review: a complete five-section strategy within the word limit. Later reviews: verdicts that match the scorecard, a keep or change that separates "didn't work" from "wasn't followed", and no return to an approach the history shows failed without a stated reason.
- **Result:** Not seen yet.

### 2026-10-02 · trading_agent.md · follow the strategy (D43)
- **Line added:** The "# Your strategy" section: the strategy comes in the input, written by the agent in an earlier review; follow it; set `follows` to the section each order follows, or `"deviation"` with the reason; don't change the strategy here; null when there is no strategy. In "# Output": `follows` on each order, and one sentence in `summary` on how the run followed the strategy.
- **Cause:** Built with D43. The section names come from the code (`$strategy_sections`), not typed by hand. "Given to you at the start of every run" was added after the user asked whether the agent remembers the strategy: it doesn't; the app supplies it each run.
- **Expected:** Each order names a section or is marked as a deviation with a reason; the summary says how the run followed the strategy.
- **Result:** Not seen yet.

### 2026-10-02 · strategy_review.md · section names from the code (D43)
- **Line changed:** The five section names in "What a strategy is" are now `$section_<name>` placeholders. The rendered text is unchanged.
- **Cause:** The user pointed out that names typed by hand in the code, the answer format and the prompts could drift apart. A test now also checks that the answer formats allow exactly the core sections.
- **Expected:** No change in behaviour; a renamed section fails a test instead of breaking runs.
- **Result:** Not applicable.

## Open observations

Problems seen in runs that have **not** led to a prompt change. A prompt change needs the same problem in at least three runs (see CLAUDE.md). Add the run each time it recurs.

| Problem | Seen in runs | Notes |
|---------|--------------|-------|
| Research states non-exposure on many stocks ("No direct link to Iran/oil was identified") | 2026-09-30 13:50, 13:55, 14:32 | From "say whether and how it is exposed" in the research prompt. Seen in three runs, so it now qualifies for a change. Fewer in 14:32 (about five stocks). |
| Every finding opens by restating the price and day change ("Quote snapshot: $263.91, up 0.24%") | 2026-09-28 15:28, 2026-09-30 13:50, 13:55, 14:32 | The Decision log now shows these as a chip (D31), so the text duplicates it. Qualifies for a change. |
| A sentence repeated on every finding ("does not establish a material change to the thesis") | 2026-09-30 13:55 | Came from the Trading Agent's request. Gone in 14:32, after the D42 code fix. |
| The Research Agent writes about its own role or its instructions inside a finding ("I can report evidence but cannot make hold, trim, or add decisions") | 2026-09-30 13:55, 14:32 | In the `MARKET` finding both times. |
| Input tokens and searches per run are rising | 2026-09-30 13:55 (108k, 4), 14:32 (115k, 5) | Was 75k–80k. All 5 searches used in 14:32. Matters for the free search allowance in 15-minute mode (D35). |
| A finding corrects itself mid-text with a date no source gives (MU: "Oct. 30?") | 2026-09-28 15:28 | Looks like the cheapest model slipping; "never invent numbers" already covers it. |
| An order's reason comes from the watchlist entry, not from that run's research (MSFT "Copilot") | 2026-09-30 13:50 | The prompt says to base decisions on the research. |
| The Trading Agent buys on every run while cash remains | 2026-09-28 15:28, 2026-09-30 13:30, 13:50 | Held in 13:55 and 14:32 with about 23% cash. Runs minutes apart are a weak test. |
