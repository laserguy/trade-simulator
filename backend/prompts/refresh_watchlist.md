# Task: build the watchlist
Instead of a research report, pick the $watchlist_max or fewer (at least 10 if possible) most
promising stocks for the watchlist. Only stocks from the $stock_pool are allowed; the full list is in
the input. Picks outside it are dropped.

Work in this order, within your limit of $refresh_max_searches web searches:
1. Market scan: start with `get_market_news` (free) for this week's events, then about 5 web searches
   for strong and weak sectors, upcoming earnings, and anything the headlines leave unclear.
2. Shortlist about 30 candidates using the free tools (`get_quotes`, `get_key_metrics`,
   `get_company_news`). These don't use web searches.
3. Deeper checks on the strongest candidates (about 15 web searches): recent news and red flags such as
   lawsuits, scandals, weak earnings, or unexplained price jumps.
4. Choose the final list. Prefer diversity across sectors and avoid stocks with unresolved red flags.

# Output
- `market_overview`: two to four plain sentences on the current market. No links, URLs or Markdown in the text.
- `market_sources`: the URLs the overview is based on.
- `picks`: each with `symbol`, a one-line plain `reason` (no links), and the `sources` (URLs) behind it.
