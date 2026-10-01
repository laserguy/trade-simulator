from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from fakes import MARKET_DOWN, FakeMarketData, FixedClock, WeekdayCalendar
from trade_simulator.adapters.sqlite_repository import SqliteRepository
from trade_simulator.application.strategy_view import StrategyViewer
from trade_simulator.core.decision_log import RunCost, RunStatus
from trade_simulator.core.exchange_profile import US_PROFILE
from trade_simulator.core.portfolio import Portfolio, Position
from trade_simulator.core.strategy import Strategy, StrategySection, StrategyVersion
from trade_simulator.core.strategy_review import ReviewDecision, ReviewTrigger, StrategyReview

V1_START = datetime(2026, 9, 14, 14, 0, tzinfo=timezone.utc)
V2_START = V1_START + timedelta(days=14)
NOW = V2_START + timedelta(days=3)
V1 = Strategy("Earnings momentum.", "Start at 6%.", "Sell when the reason breaks.", "Keep 10-25% cash.", "Level with SPY.")
V2 = Strategy("Earnings momentum.", "Start at 4%.", "Sell when the reason breaks.", "Keep 15-25% cash.", "Ahead of SPY.")


@pytest.fixture
def repo(tmp_path):
    repository = SqliteRepository(tmp_path / "sim.sqlite3")
    repository.initialize()
    return repository


def make_viewer(repo, market=None):
    return StrategyViewer(
        repository=repo,
        market_data=market or FakeMarketData({"AAPL": "110"}),
        calendar=WeekdayCalendar(),
        profile=US_PROFILE,
        clock=FixedClock(NOW),
    )


def review(review_id, started_at, decision, reviewed=None, status=RunStatus.COMPLETED, **extra):
    return StrategyReview(
        id=review_id, trigger=ReviewTrigger.BUTTON, started_at=started_at, finished_at=started_at, status=status,
        failure_reason=None if status is RunStatus.COMPLETED else "Answer missed a section",
        reviewed_version=reviewed, decision=decision, reason="Because.", cost=RunCost(800, 100, 0, "gpt-6-luna"),
        trace_id="t", **extra,
    )


def with_two_versions(repo):
    repo.save_strategy_review(review("r1", V1_START, ReviewDecision.FIRST), StrategyVersion(1, V1, V1_START, None, "r1"))
    repo.save_strategy_review(
        review("r2", V1_START + timedelta(days=13), None, reviewed=1, status=RunStatus.FAILED), None
    )
    change = review(
        "r3", V2_START, ReviewDecision.CHANGE, reviewed=1,
        section_changes={StrategySection.POSITION_SIZE: "Two buys fell together."},
    )
    repo.save_strategy_review(change, StrategyVersion(2, V2, V2_START, None, "r3"))


def test_without_a_strategy_the_page_offers_the_first_one(repo):
    page = make_viewer(repo).view()

    assert (page.current, page.sections, page.scorecard, page.reviews) == (None, (), None, ())
    assert page.timing.first is True


def test_current_sections_are_marked_when_they_changed_from_the_previous_version(repo):
    with_two_versions(repo)

    page = make_viewer(repo).view()

    assert page.current.number == 2
    changed = {s.section: s.changed_why for s in page.sections if s.changed}
    # Cash and targets changed without a stated reason; position size has one.
    assert changed == {
        StrategySection.POSITION_SIZE: "Two buys fell together.",
        StrategySection.CASH_AND_PACE: "",
        StrategySection.TARGETS: "",
    }


def test_reviews_are_newest_first_with_failed_ones_and_each_change_old_to_new(repo):
    with_two_versions(repo)

    page = make_viewer(repo).view()

    assert [entry.review.id for entry in page.reviews] == ["r3", "r2", "r1"]
    change = page.reviews[0]
    assert (change.reviewed_version, change.written_version) == (1, 2)
    position = next(c for c in change.changes if c.section is StrategySection.POSITION_SIZE)
    assert (position.old, position.new, position.why) == ("Start at 6%.", "Start at 4%.", "Two buys fell together.")
    assert [c.section for c in change.changes] == [
        StrategySection.POSITION_SIZE, StrategySection.CASH_AND_PACE, StrategySection.TARGETS
    ]
    assert page.reviews[1].changes == ()  # the failed review changed nothing
    assert page.reviews[2].written_version == 1


def test_the_live_scorecard_covers_the_current_version(repo):
    with_two_versions(repo)
    repo.save_portfolio(Portfolio(Decimal("9000"), {"AAPL": Position("AAPL", 10, Decimal("100"))}))

    page = make_viewer(repo).view()

    assert page.scorecard.period_start == V2_START
    assert page.scorecard.holdings[0].gain_percent == Decimal("10")


def test_the_page_still_loads_when_prices_are_unavailable(repo):
    with_two_versions(repo)
    repo.save_portfolio(Portfolio(Decimal("9000"), {"AAPL": Position("AAPL", 10, Decimal("100"))}))

    page = make_viewer(repo, FakeMarketData(error=MARKET_DOWN)).view()

    assert page.scorecard.holdings == ()
