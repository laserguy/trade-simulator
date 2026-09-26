"""Structured outputs the agents must return, and their conversion into core objects."""

from typing import Literal

from pydantic import BaseModel

from trade_simulator.adapters.text_links import merge_sources, split_links
from trade_simulator.core.decision_log import Finding, WatchlistEntry
from trade_simulator.core.errors import InvalidOrderError
from trade_simulator.core.order import Order, Side


class ResearchFinding(BaseModel):
    symbol: str
    summary: str
    sources: list[str]
    warnings: list[str]


class ResearchReport(BaseModel):
    findings: list[ResearchFinding]


class ProposedOrder(BaseModel):
    symbol: str
    side: Literal["buy", "sell"]
    quantity: int
    reason: str


class TradingDecision(BaseModel):
    orders: list[ProposedOrder]
    summary: str


class WatchlistPick(BaseModel):
    symbol: str
    reason: str
    sources: list[str]


class WatchlistResult(BaseModel):
    market_overview: str
    market_sources: list[str]
    picks: list[WatchlistPick]


def to_orders(decision: TradingDecision) -> tuple[list[Order], list[Finding]]:
    """Valid proposals become Orders; malformed ones are ignored and reported as warnings."""
    orders, warnings = [], []
    for proposed in decision.orders:
        reason, _ = split_links(proposed.reason)
        try:
            orders.append(Order(proposed.symbol, Side(proposed.side), proposed.quantity, reason))
        except InvalidOrderError as exc:
            warnings.append(
                Finding(
                    symbol=proposed.symbol.upper(),
                    summary="Proposed order ignored",
                    warnings=(f"Ignored invalid order: {exc}",),
                )
            )
    return orders, warnings


def to_findings(findings: list[ResearchFinding]) -> list[Finding]:
    return [_finding(f.symbol.strip().upper(), f.summary, f.sources, tuple(f.warnings)) for f in findings]


def to_market_overview(result: WatchlistResult) -> Finding:
    return _finding("MARKET", result.market_overview, result.market_sources)


def to_decision_summary(decision: TradingDecision) -> Finding:
    return _finding("OVERALL", decision.summary, [])


def to_watchlist_entries(result: WatchlistResult) -> list[WatchlistEntry]:
    entries = []
    for pick in result.picks:
        reason, urls = split_links(pick.reason)
        entries.append(WatchlistEntry(pick.symbol, reason, merge_sources(pick.sources, urls)))
    return entries


def _finding(symbol: str, text: str, sources: list[str], warnings: tuple[str, ...] = ()) -> Finding:
    summary, urls = split_links(text)
    return Finding(symbol, summary, merge_sources(sources, urls), warnings)
