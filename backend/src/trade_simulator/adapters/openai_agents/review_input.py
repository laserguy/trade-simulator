"""The text a strategy review starts from (D43): portfolio, market, the current strategy, its scorecard,
its orders, and every earlier version with the reasons it was kept or changed."""

from decimal import Decimal

from trade_simulator.application.ports import ReviewContext, ReviewedOrder
from trade_simulator.core.decision_log import Watchlist
from trade_simulator.core.portfolio import Portfolio
from trade_simulator.core.strategy import StrategySection, StrategyVersion
from trade_simulator.core.strategy_review import ReviewDecision, Scorecard, StrategyReview
from trade_simulator.core.trading_rules import OrderStatus


def render_review_input(context: ReviewContext) -> str:
    currency = context.profile.currency
    lines = [f"Time: {context.now.isoformat()}", f"Exchange: {context.profile.name}"]
    lines += _portfolio(context.portfolio, context.prices, currency)
    lines += _watchlist(context.watchlist)
    lines += _market(context)
    current = context.current
    if current is None:
        return "\n".join([*lines, "", "There is no strategy yet: write the first one."])

    lines += ["", f"Current strategy: v{current.number}, in use since {current.started_at.date().isoformat()}"]
    lines += _sections(current, indent="")
    lines += _scorecard(current, context.scorecard, currency)
    lines += _orders(context.orders)
    lines += _history(context)
    return "\n".join(lines)


def _portfolio(portfolio: Portfolio, prices, currency: str) -> list[str]:
    priced = {s: p for s, p in portfolio.positions.items() if s in prices}
    total = portfolio.cash + sum((p.quantity * prices[s] for s, p in priced.items()), Decimal(0))
    lines = [f"Cash: {_money(portfolio.cash, currency)}", f"Total portfolio value: {_money(total, currency)}", "", "Holdings:"]
    if not portfolio.positions:
        lines.append("- none")
    for symbol, position in sorted(portfolio.positions.items()):
        price = prices.get(symbol)
        if price is None:
            lines.append(f"- {symbol}: {position.quantity} shares, average cost {position.average_cost}, price unavailable")
            continue
        gain = (price - position.average_cost) / position.average_cost * 100
        lines.append(
            f"- {symbol}: {position.quantity} shares, average cost {position.average_cost}, price {price}, "
            f"{gain:+.1f}% on cost"
        )
    return lines


def _watchlist(watchlist: Watchlist | None) -> list[str]:
    if watchlist is None:
        return ["", "Watchlist: none yet."]
    return ["", "Watchlist (the only stocks you may buy):", *(f"- {e.symbol}: {e.reason}" for e in watchlist.entries)]


def _market(context: ReviewContext) -> list[str]:
    overview = context.market_overview
    if overview is None:
        return ["", "Latest market overview: none yet."]
    return ["", f"Latest market overview (from {overview.as_of.date().isoformat()}):", overview.summary]


def _sections(version: StrategyVersion, indent: str) -> list[str]:
    return [f"{indent}- {section.title}: {text}" for section, text in version.strategy.sections()]


def _scorecard(version: StrategyVersion, card: Scorecard | None, currency: str) -> list[str]:
    if card is None:
        return []
    closed = ", ".join(f"{t.symbol} {_signed_money(t.gain, currency)}" for t in card.closed_trades) or "none"
    holdings = ", ".join(f"{h.symbol} {h.gain_percent:+.1f}% on cost" for h in card.holdings) or "none"
    return [
        "",
        f"Scorecard for v{version.number} ({card.period_start.date().isoformat()} to "
        f"{card.period_end.date().isoformat()}, computed by the system):",
        f"- Return: portfolio {card.portfolio_percent:+.2f}%, SPY {card.benchmark_percent:+.2f}%",
        f"- Trading runs: {card.trading_runs}; trades: {card.trades}; fees: {_money(card.fees, currency)}",
        f"- Closed trades: {closed}",
        f"- Holdings: {holdings}",
        f"- Average cash: {card.average_cash_percent:.1f}% of the portfolio",
        f"- Orders naming a section: {card.followed_orders}; deviations: {card.deviations}",
    ]


def _orders(orders: tuple[ReviewedOrder, ...]) -> list[str]:
    lines = ["", "Orders in this period, with your reason at the time:"]
    if not orders:
        lines.append("- none")
    for reviewed in orders:
        result, order = reviewed.result, reviewed.result.order
        basis = _basis(order.follows)
        outcome = (
            f"executed at {result.price}"
            if result.status is OrderStatus.EXECUTED
            else f"rejected, {result.rejection_reason.value}"
        )
        lines.append(
            f"- {reviewed.at.date().isoformat()} {order.side.value.upper()} {order.quantity} {order.symbol} "
            f'({basis}): {outcome}. Reason: "{order.reason}"'
        )
    return lines


def _history(context: ReviewContext) -> list[str]:
    """Earlier versions, newest first: the previous one in full, older ones compact; each with its reviews."""
    current = context.current
    lines = ["", "History (newest first):"]
    keeps_of_current = _reviews_of(context.reviews, current.number)
    if keeps_of_current:
        lines.append(f"v{current.number} (current):")
        lines += [_review_line(review) for review in reversed(keeps_of_current)]
    earlier = [v for v in context.versions if v.number < current.number]
    if not earlier:
        lines.append("- none: this is the first version.")
    for version in reversed(earlier):
        lines.append(
            f"v{version.number} ({version.started_at.date().isoformat()} to "
            f"{version.ended_at.date().isoformat() if version.ended_at else '?'}):"
        )
        if version.number == current.number - 1:
            lines += _sections(version, indent="  ")
        for review in reversed(_reviews_of(context.reviews, version.number)):
            lines.append(_review_line(review))
            lines += _change_lines(review)
    return lines


def _reviews_of(reviews: tuple[StrategyReview, ...], number: int) -> list[StrategyReview]:
    return [r for r in reviews if r.reviewed_version == number and r.decision is not ReviewDecision.FIRST]


def _review_line(review: StrategyReview) -> str:
    verb = "Kept" if review.decision is ReviewDecision.KEEP else "Changed"
    targets = _verdict(review.targets_verdict.value if review.targets_verdict else None, review.targets_note)
    details = f"targets {targets}" if targets else ""
    if review.decision is ReviewDecision.CHANGE and review.followed:
        details += f"; followed: {review.followed.value}"
    return f"  {verb} on {review.started_at.date().isoformat()} ({details}): {review.reason}"


def _change_lines(review: StrategyReview) -> list[str]:
    if review.decision is not ReviewDecision.CHANGE:
        return []
    lines = [f"    {section.title} changed: {why}" for section, why in review.section_changes.items()]
    card = review.scorecard
    if card:
        lines.append(
            f"    Its scorecard: portfolio {card.portfolio_percent:+.2f}%, SPY {card.benchmark_percent:+.2f}%, "
            f"{card.trades} trades, {card.average_cash_percent:.1f}% average cash"
        )
    return lines


def _verdict(value: str | None, note: str) -> str:
    if value is None:
        return ""
    words = value.replace("_", " ")
    return f"{words}: {note}" if note else words


def _basis(follows: str | None) -> str:
    if follows is None:
        return "no section named"
    try:
        return StrategySection(follows).title
    except ValueError:
        return follows  # "deviation"


def _money(amount: Decimal, currency: str) -> str:
    return f"{amount:,.2f} {currency}"


def _signed_money(amount: Decimal, currency: str) -> str:
    return f"{amount:+,.2f} {currency}"
