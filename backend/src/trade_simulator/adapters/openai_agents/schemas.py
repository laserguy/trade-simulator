"""Structured outputs the agents must return, and their conversion into core objects."""

from collections.abc import Mapping
from dataclasses import replace
from typing import Literal

from pydantic import BaseModel

from trade_simulator.adapters.text_links import keep_known, merge_sources, split_links
from trade_simulator.application.ports import AgentUsage, Quote, ReviewProposal
from trade_simulator.core.decision_log import Finding, WatchlistEntry
from trade_simulator.core.errors import InvalidOrderError
from trade_simulator.core.order import Order, Side
from trade_simulator.core.strategy import Strategy, StrategySection
from trade_simulator.core.strategy_review import Followed, ReviewDecision, TargetsVerdict


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


SectionName = Literal["what_i_look_for", "position_size", "when_i_sell", "cash_and_pace", "targets"]


class StrategyText(BaseModel):
    what_i_look_for: str
    position_size: str
    when_i_sell: str
    cash_and_pace: str
    targets: str


class SectionChange(BaseModel):
    section: SectionName
    why: str


class StrategyReviewResult(BaseModel):
    targets_verdict: Literal["met", "partly_met", "missed"] | None
    targets_note: str
    followed: Literal["yes", "partly", "no"] | None
    followed_note: str
    decision: Literal["keep", "change"]
    reason: str
    new_strategy: StrategyText | None
    section_changes: list[SectionChange]


def to_review_proposal(result: StrategyReviewResult, usage: AgentUsage | None, trace_id: str | None) -> ReviewProposal:
    """Converts the answer as given; the review use case checks it before anything is saved (D43)."""
    new_strategy = None
    if result.new_strategy is not None:
        new_strategy = Strategy(**{name: _plain(text) for name, text in result.new_strategy.model_dump().items()})
    return ReviewProposal(
        decision=ReviewDecision(result.decision),
        reason=_plain(result.reason),
        new_strategy=new_strategy,
        section_changes={StrategySection(c.section): _plain(c.why) for c in result.section_changes},
        targets_verdict=TargetsVerdict(result.targets_verdict) if result.targets_verdict else None,
        targets_note=_plain(result.targets_note),
        followed=Followed(result.followed) if result.followed else None,
        followed_note=_plain(result.followed_note),
        usage=usage,
        trace_id=trace_id,
    )


def _plain(text: str) -> str:
    return split_links(text)[0]


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
