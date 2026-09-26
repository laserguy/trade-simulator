from datetime import datetime, timedelta, timezone

from fakes import FixedClock
from trade_simulator.application.activity import ActivityFeed

NOW = datetime(2026, 9, 28, 14, 45, tzinfo=timezone.utc)


def test_feed_is_idle_until_a_run_begins():
    snapshot = ActivityFeed(clock=FixedClock(NOW)).snapshot()

    assert snapshot.active is False
    assert snapshot.events == ()


def test_events_are_collected_while_a_run_is_active():
    clock = FixedClock(NOW)
    feed = ActivityFeed(clock=clock)

    feed.begin("Decision run")
    feed.add("Trading Agent", "Started")
    clock.now = NOW + timedelta(seconds=3)
    feed.add("Research Agent", "Checking prices: NVDA")

    snapshot = feed.snapshot()
    assert snapshot.active is True
    assert snapshot.label == "Decision run"
    assert [(e.actor, e.text) for e in snapshot.events] == [
        ("Trading Agent", "Started"),
        ("Research Agent", "Checking prices: NVDA"),
    ]
    assert snapshot.events[1].at == NOW + timedelta(seconds=3)


def test_live_only_a_new_run_starts_with_an_empty_timeline():
    feed = ActivityFeed(clock=FixedClock(NOW))
    feed.begin("Decision run")
    feed.add("Trading Agent", "Started")
    feed.end()

    feed.begin("Watchlist refresh")

    assert feed.snapshot().events == ()


def test_events_outside_a_run_are_ignored():
    feed = ActivityFeed(clock=FixedClock(NOW))

    feed.add("Trading Agent", "stray")

    assert feed.snapshot().events == ()
