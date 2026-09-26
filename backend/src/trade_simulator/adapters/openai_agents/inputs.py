"""Turns run context into the text each agent run starts from."""

from decimal import Decimal

from trade_simulator.application.ports import DecisionContext, RefreshContext


def render_decision_input(context: DecisionContext) -> str:
    portfolio, prices = context.portfolio, context.prices
    holdings_value = sum(
        (p.quantity * prices[s] for s, p in portfolio.positions.items() if s in prices), Decimal("0")
    )
    total = portfolio.cash + holdings_value
    currency = context.profile.currency

    lines = [
        f"Time: {context.now.isoformat()}",
        f"Exchange: {context.profile.name}",
        f"Cash: {_money(portfolio.cash, currency)}",
        f"Total portfolio value: {_money(total, currency)}",
        "",
        "Holdings:",
    ]
    if not portfolio.positions:
        lines.append("- none")
    for symbol, position in sorted(portfolio.positions.items()):
        price = prices.get(symbol)
        if price is None:
            lines.append(f"- {symbol}: {position.quantity} shares, average cost {position.average_cost}, price unavailable")
            continue
        value = position.quantity * price
        lines.append(
            f"- {symbol}: {position.quantity} shares, average cost {position.average_cost}, "
            f"price {price}, value {_money(value, currency)} ({_percent(value, total)} of portfolio)"
        )

    lines += ["", "Watchlist (you may only buy these):"]
    for entry in context.watchlist.entries:
        price = prices.get(entry.symbol)
        lines.append(f"- {entry.symbol} (price {price if price is not None else 'unavailable'}): {entry.reason}")

    lines.append("")
    overview = context.market_overview
    if overview is None:
        lines.append("Latest market overview: none yet (no watchlist refresh has written one).")
    else:
        lines += [
            f"Latest market overview (from the watchlist refresh on {overview.as_of.date().isoformat()}):",
            overview.summary,
        ]

    lines += [
        "",
        f"Research budget this run: {context.limits.max_research_calls} Research Agent calls, "
        f"{context.limits.max_searches} web searches.",
    ]
    return "\n".join(lines)


def render_refresh_input(context: RefreshContext) -> str:
    lines = [f"Date: {context.now.date().isoformat()}", f"Exchange: {context.profile.name}", ""]
    if context.current_watchlist:
        lines.append("Current watchlist (you may keep, replace or drop any of these):")
        lines += [f"- {e.symbol}: {e.reason}" for e in context.current_watchlist.entries]
    else:
        lines.append("There is no watchlist yet.")
    lines += [
        "",
        f"Web search budget: {context.limits.max_searches} searches.",
        "",
        f"Allowed stocks ({context.profile.stock_pool}, {len(context.stock_pool)} symbols):",
        ", ".join(sorted(context.stock_pool)),
    ]
    return "\n".join(lines)


def _money(amount: Decimal, currency: str) -> str:
    return f"{amount:,.2f} {currency}"


def _percent(part: Decimal, whole: Decimal) -> str:
    return f"{part / whole * 100:.1f}%" if whole else "n/a"
