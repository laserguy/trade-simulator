"""Structured outputs the agents must return, and their conversion into core objects."""

from collections.abc import Mapping
from dataclasses import replace
from typing import Literal

from pydantic import BaseModel

from trade_simulator.adapters.text_links import keep_known, merge_sources, split_links
from trade_simulator.application.ports import Quote
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


# `known_urls` are the links the tools returned in this run; any other source is dropped (D22).


def to_findings(
    findings: list[ResearchFinding], known_urls: set[str], quotes: Mapping[str, Quote] | None = None
) -> list[Finding]:
    """`quotes` are the ones the quote tool returned in this run; each finding keeps its stock's price and change."""
    converted = []
    for f in findings:
        finding = _finding(f.symbol.strip().upper(), f.summary, f.sources, known_urls, tuple(f.warnings))
        quote = (quotes or {}).get(finding.symbol)
        if quote:
            finding = replace(finding, price=quote.price, change_percent=quote.change_percent)
        converted.append(finding)
    return converted


def to_market_overview(result: WatchlistResult, known_urls: set[str]) -> Finding:
    return _finding("MARKET", result.market_overview, result.market_sources, known_urls)


def to_decision_summary(decision: TradingDecision) -> Finding:
    summary, _ = split_links(decision.summary)
    return Finding("OVERALL", summary)


def to_watchlist_entries(result: WatchlistResult, known_urls: set[str]) -> list[WatchlistEntry]:
    entries = []
    for pick in result.picks:
        reason, urls = split_links(pick.reason)
        entries.append(WatchlistEntry(pick.symbol, reason, keep_known(merge_sources(pick.sources, urls), known_urls)))
    return entries


def _finding(
    symbol: str, text: str, sources: list[str], known_urls: set[str], warnings: tuple[str, ...] = ()
) -> Finding:
    summary, urls = split_links(text)
    return Finding(symbol, summary, keep_known(merge_sources(sources, urls), known_urls), warnings)
