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
    ]
    performance = context.performance
    if performance is not None:
        lines.append(
            f"Performance since {performance.since.date().isoformat()}: "
            f"portfolio {performance.portfolio_percent:+.2f}%, "
            f"{performance.benchmark_symbol} {performance.benchmark_percent:+.2f}%"
        )
    lines += ["", "Holdings:"]
    if not portfolio.positions:
        lines.append("- none")
    for symbol, position in sorted(portfolio.positions.items()):
        price = prices.get(symbol)
        if price is None:
            lines.append(f"- {symbol}: {position.quantity} shares, average cost {position.average_cost}, price unavailable")
        else:
            value = position.quantity * price
            # "+ 0" turns a rounded -0.0 into 0.0, so a flat position doesn't read as a loss.
            gain = round((price - position.average_cost) / position.average_cost * 100, 1) + 0
            lines.append(
                f"- {symbol}: {position.quantity} shares, average cost {position.average_cost}, "
                f"price {price}, value {_money(value, currency)} ({_percent(value, total)} of portfolio), "
                f"{gain:+.1f}% on cost"
            )
        for buy in context.holding_buys.get(symbol, ()):
            lines.append(
                f"  Bought {buy.quantity} on {buy.at.date().isoformat()} at {buy.price}. "
                f'Your reason then: "{buy.reason}"'
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


def render_research_note(context: DecisionContext) -> str:
    """The holdings and why each was bought, added to every research request of the run (D42).
    Empty when no holding has a recorded buy."""
    lines = [
        f'- {symbol} (bought {buy.at.date().isoformat()}): "{buy.reason}"'
        for symbol in sorted(context.portfolio.positions)
        for buy in context.holding_buys.get(symbol, ())
    ]
    if not lines:
        return ""
    return "\n".join(
        [
            "Current holdings and the reason each was bought:",
            *lines,
            "Report the facts that bear on these reasons. The Trading Agent judges whether they still hold.",
        ]
    )


def with_research_note(request: str, note: str) -> str:
    return f"{request}\n\n{note}" if note else request


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
