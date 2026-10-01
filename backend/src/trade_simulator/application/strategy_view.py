"""Use case: what the Strategy tab shows (D44): the current strategy with its changes, when a review is
possible, the current version's results so far, and every review with what it changed."""

import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone

from trade_simulator.application.portfolio_setup import load_or_create_portfolio
from trade_simulator.application.ports import MarketCalendar, MarketData, Repository
from trade_simulator.application.strategy_scorecard import build_scorecard
from trade_simulator.application.strategy_timing import ReviewTiming, review_timing
from trade_simulator.core.errors import MarketDataError
from trade_simulator.core.exchange_profile import ExchangeProfile
from trade_simulator.core.strategy import StrategySection, StrategyVersion
from trade_simulator.core.strategy_review import Scorecard, StrategyReview

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SectionView:
    section: StrategySection
    text: str
    changed: bool  # differs from the previous version
    changed_why: str  # the reason given for the change; may be empty


@dataclass(frozen=True)
class SectionChangeView:
    section: StrategySection
    old: str
    new: str
    why: str


@dataclass(frozen=True)
class ReviewEntry:
    review: StrategyReview
    reviewed_version: int | None
    written_version: int | None  # the version this review wrote, if any
    changes: tuple[SectionChangeView, ...]


@dataclass(frozen=True)
class StrategyPage:
    current: StrategyVersion | None
    sections: tuple[SectionView, ...]
    timing: ReviewTiming
    scorecard: Scorecard | None  # the current version so far
    reviews: tuple[ReviewEntry, ...]  # newest first, failed ones included


class StrategyViewer:
    def __init__(
        self,
        *,
        repository: Repository,
        market_data: MarketData,
        calendar: MarketCalendar,
        profile: ExchangeProfile,
        clock: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
    ) -> None:
        self._repository = repository
        self._market_data = market_data
        self._calendar = calendar
        self._profile = profile
        self._clock = clock

    def view(self) -> StrategyPage:
        now = self._clock()
        current = self._repository.current_strategy()
        versions = {v.number: v for v in self._repository.strategy_versions()}
        reviews = self._repository.strategy_reviews()
        runs = self._repository.runs_following(current.number) if current else []
        timing = review_timing(current=current, reviews=reviews, runs=runs, calendar=self._calendar, now=now)
        if current is None:
            return StrategyPage(None, (), timing, None, ())

        written = {v.review_id: v for v in versions.values()}
        creating_review = next((r for r in reviews if r.id == current.review_id), None)
        return StrategyPage(
            current=current,
            sections=_sections(current, versions.get(current.number - 1), creating_review),
            timing=timing,
            scorecard=self._scorecard(current, runs, now),
            reviews=tuple(_entry(r, versions, written) for r in reversed(reviews)),
        )

    def _scorecard(self, current: StrategyVersion, runs, now: datetime) -> Scorecard:
        portfolio = load_or_create_portfolio(self._repository, self._profile)
        try:
            prices = self._market_data.get_prices(sorted(portfolio.positions)) if portfolio.positions else {}
        except MarketDataError as exc:
            logger.warning("Prices unavailable for the strategy page: %s", exc)
            prices = {}
        return build_scorecard(
            version=current,
            runs=runs,
            trades=self._repository.executed_trades(),
            snapshots=self._repository.load_value_snapshots(),
            portfolio=portfolio,
            prices=prices,
            now=now,
        )


def _sections(
    current: StrategyVersion, previous: StrategyVersion | None, creating_review: StrategyReview | None
) -> tuple[SectionView, ...]:
    whys = creating_review.section_changes if creating_review else {}
    return tuple(
        SectionView(
            section,
            text,
            changed=previous is not None and previous.strategy.text(section) != text,
            changed_why=whys.get(section, ""),
        )
        for section, text in current.strategy.sections()
    )


def _entry(
    review: StrategyReview, versions: dict[int, StrategyVersion], written: dict[str, StrategyVersion]
) -> ReviewEntry:
    new = written.get(review.id)
    old = versions.get(review.reviewed_version) if review.reviewed_version else None
    changes = ()
    if new and old:
        changes = tuple(
            SectionChangeView(section, old.strategy.text(section), text, review.section_changes.get(section, ""))
            for section, text in new.strategy.sections()
            if old.strategy.text(section) != text
        )
    return ReviewEntry(review, review.reviewed_version, new.number if new else None, changes)
