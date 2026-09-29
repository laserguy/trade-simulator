from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

import time

from fakes import FakeAgent, FakeCalendar, FakeMarketData, FakeUniverse, FixedClock, decision, proposal
from trade_simulator.adapters.sqlite_repository import SqliteRepository
from trade_simulator.adapters.web.api import WebServices, create_app
from trade_simulator.application.activity import ActivityFeed
from trade_simulator.application.initial_watchlist import InitialWatchlist
from trade_simulator.application.ports import DailyBar, Quote
from trade_simulator.application.price_history import PriceHistoryService
from trade_simulator.application.run_mode import RunModeSetting
from trade_simulator.application.value_history import ValueHistory
from trade_simulator.application.watchlist_view import WatchlistViewer


class FakePriceSource:
    name = "fake"
    max_requests_per_hour = 50

    def daily_bars(self, symbol, since):
        closes = {date(2026, 9, 26): "195", date(2026, 9, 27): "200", date(2026, 9, 28): "205"}
        return [
            DailyBar(day, Decimal(c), Decimal(c), Decimal(c), Decimal(c), Decimal(c), 100)
            for day, c in closes.items()
            if day >= since
        ]


class FakeQuotes:
    def get_quotes(self, symbols):
        known = {"AAPL": Quote("AAPL", Decimal("200"), Decimal("1.5"), Decimal("197"))}
        return {s: known[s] for s in symbols if s in known}
from trade_simulator.application.portfolio_view import PortfolioViewer
from trade_simulator.application.refresh_watchlist import WatchlistRefresher
from trade_simulator.application.run_decision import DecisionRunner
from trade_simulator.application.run_guard import RunGuard
from trade_simulator.application.settings import SettingsService
from trade_simulator.core.decision_log import (
    DecisionRun,
    Finding,
    RunCost,
    RunStatus,
    RunTrigger,
    Watchlist,
    WatchlistEntry,
)
from trade_simulator.core.exchange_profile import US_PROFILE
from trade_simulator.core.model_pricing import ModelCatalogue, ModelOption
from trade_simulator.core.order import Order, Side
from trade_simulator.core.trading_rules import OrderResult, OrderStatus, RejectionReason

NOW = datetime(2026, 9, 28, 15, 0, tzinfo=timezone.utc)
LUNA = ModelOption("openai", "gpt-6-luna", "GPT-6 Luna", Decimal("0.10"), Decimal("0.50"))
CATALOGUE = ModelCatalogue(date(2026, 9, 26), (LUNA,))


def build(tmp_path, calendar_open=True):
    repo = SqliteRepository(tmp_path / "sim.sqlite3")
    repo.initialize()
    guard = RunGuard()
    calendar = FakeCalendar(open_=calendar_open)
    market = FakeMarketData({"SPY": "500", "AAPL": "200"})
    agent = FakeAgent(decision(), proposal=proposal([WatchlistEntry("AAPL", "Earnings")]))
    clock = FixedClock(NOW)
    settings = SettingsService(store=repo, catalogue=CATALOGUE, default_model_id="gpt-6-luna")
    refresher = WatchlistRefresher(
        repository=repo, agent=agent, universe=FakeUniverse(), profile=US_PROFILE, guard=guard, clock=clock,
        activity=ActivityFeed(clock=clock),
    )
    activity = ActivityFeed(clock=clock)
    viewer = PortfolioViewer(repository=repo, market_data=market, profile=US_PROFILE, clock=clock)
    services = WebServices(
        profile=US_PROFILE,
        repository=repo,
        calendar=calendar,
        guard=guard,
        decision_runner=DecisionRunner(
            repository=repo, market_data=market, calendar=calendar, agent=agent,
            profile=US_PROFILE, guard=guard, clock=clock, activity=activity,
        ),
        watchlist_refresher=refresher,
        initial_watchlist=InitialWatchlist(repository=repo, settings=settings, store=repo, refresher=refresher),
        portfolio_viewer=viewer,
        watchlist_viewer=WatchlistViewer(repository=repo, quotes=FakeQuotes(), clock=clock),
        value_history=ValueHistory(repository=repo, viewer=viewer, profile=US_PROFILE, clock=clock),
        activity=activity,
        run_mode=RunModeSetting(repo),
        free_searches_per_month=1000,
        price_history=PriceHistoryService(repository=repo, source=FakePriceSource(), profile=US_PROFILE, clock=clock),
        settings=settings,
        catalogue=CATALOGUE,
        clock=clock,
    )
    return TestClient(create_app(services)), services


@pytest.fixture
def client(tmp_path):
    return build(tmp_path)[0]


def test_status_reports_market_and_run_state(client):
    body = client.get("/api/status").json()

    assert body == {
        "market_open": True,
        "next_open": None,
        "run_in_progress": False,
        "exchange": "NYSE / NASDAQ",
        "currency": "USD",
        "timezone": "America/New_York",
    }


def test_portfolio_includes_benchmark(client):
    body = client.get("/api/portfolio").json()

    assert body["cash"] == "10000.00"
    assert body["total_value"] == "10000.00"
    assert body["benchmark_symbol"] == "SPY"
    assert body["benchmark_return_percent"] == "0.00"


def test_runs_are_listed_with_orders_findings_cost_and_trace_link(tmp_path):
    client, services = build(tmp_path)
    run = DecisionRun(
        id="r1",
        trigger=RunTrigger.MANUAL,
        started_at=NOW,
        finished_at=NOW + timedelta(seconds=40),
        status=RunStatus.COMPLETED,
        failure_reason=None,
        findings=(Finding("AAPL", "Beat earnings", ("https://n",), ("Unusual jump",)),),
        order_results=(
            OrderResult(Order("AAPL", Side.BUY, 5, "Cheap"), OrderStatus.EXECUTED, Decimal("200"), Decimal("1")),
            OrderResult(Order("MSFT", Side.BUY, 50, "All in"), OrderStatus.REJECTED,
                        rejection_reason=RejectionReason.EXCEEDS_POSITION_CAP),
        ),
        cost=RunCost(1_000_000, 200_000, 3, model="gpt-6-luna"),
        trace_id="trace_abc",
    )
    services.repository.save_run(run, None)

    [body] = client.get("/api/runs").json()

    assert body["status"] == "completed"
    assert body["orders"][0] == {
        "symbol": "AAPL", "side": "buy", "quantity": 5, "reason": "Cheap",
        "status": "executed", "price": "200", "fee": "1", "rejection_reason": None,
    }
    assert "20%" in body["orders"][1]["rejection_reason"] or "cap" in body["orders"][1]["rejection_reason"]
    assert body["findings"][0]["warnings"] == ["Unusual jump"]
    assert body["cost"]["estimated_usd"] == "0.2000"
    assert body["trace_url"].endswith("trace_abc")
    assert client.get("/api/runs/r1").json()["id"] == "r1"


def test_links_written_into_summaries_are_shown_as_sources(tmp_path):
    client, services = build(tmp_path)
    run = DecisionRun(
        id="r2", trigger=RunTrigger.REFRESH, started_at=NOW, finished_at=NOW, status=RunStatus.COMPLETED,
        failure_reason=None,
        findings=(Finding("MARKET", "Markets were mixed. Sources: [CNBC](https://www.cnbc.com/a)."),),
        order_results=(), cost=RunCost(0, 0, 0), trace_id=None,
    )
    services.repository.save_run(run, None)

    [finding] = client.get("/api/runs/r2").json()["findings"]

    assert finding["summary"] == "Markets were mixed."
    assert finding["sources"] == ["https://www.cnbc.com/a"]


def test_unknown_run_is_404(client):
    assert client.get("/api/runs/nope").status_code == 404


def test_run_now_is_refused_when_market_closed(tmp_path):
    client, _ = build(tmp_path, calendar_open=False)

    response = client.post("/api/runs")

    assert response.status_code == 409
    assert response.json()["next_open"]


def test_run_now_is_refused_while_another_run_is_active(tmp_path):
    client, services = build(tmp_path)
    services.guard.try_acquire()

    assert client.post("/api/runs").status_code == 409
    assert client.post("/api/watchlist/refresh").status_code == 409


def test_run_now_starts_a_background_run(tmp_path):
    client, services = build(tmp_path)
    services.repository.save_watchlist(Watchlist((WatchlistEntry("AAPL", "x"),), NOW))

    assert client.post("/api/runs").status_code == 202


def test_watchlist_endpoint_returns_rows(tmp_path):
    client, services = build(tmp_path)
    assert client.get("/api/watchlist").json() is None

    services.repository.save_watchlist(Watchlist((WatchlistEntry("AAPL", "Earnings", ("https://a",)),), NOW))

    body = client.get("/api/watchlist").json()
    assert body["rows"] == [
        {
            "symbol": "AAPL", "reason": "Earnings", "sources": ["https://a"],
            "price": "200.00", "change_percent": "1.50", "held_quantity": 0, "trend": [],
        }
    ]


def test_price_history_endpoint_returns_bars_range_and_agent_trades(tmp_path):
    client, services = build(tmp_path)
    services.repository.save_run(
        DecisionRun(
            id="t1", trigger=RunTrigger.MANUAL, started_at=NOW, finished_at=NOW, status=RunStatus.COMPLETED,
            failure_reason=None, findings=(),
            order_results=(OrderResult(Order("AAPL", Side.BUY, 5, "x"), OrderStatus.EXECUTED, Decimal("200"), Decimal("1")),),
            cost=RunCost(0, 0, 0), trace_id=None,
        ),
        None,
    )

    body = client.get("/api/price-history/AAPL?period=1M").json()

    assert body["available"] is True
    assert body["bars"][-1] == {"day": "2026-09-28", "close": "205.00"}
    assert (body["low"], body["high"]) == ("195.00", "205.00")
    assert body["trades"] == [{"day": "2026-09-28", "side": "buy", "quantity": 5, "price": "200.00"}]


def test_unknown_period_is_400(client):
    assert client.get("/api/price-history/AAPL?period=5Y").status_code == 400


def test_watchlist_rows_carry_a_cached_trend_line(tmp_path):
    client, services = build(tmp_path)
    services.repository.save_watchlist(Watchlist((WatchlistEntry("AAPL", "Earnings"),), NOW))
    services.price_history.history("AAPL", days=31)

    body = client.get("/api/watchlist").json()

    assert body["charts_available"] is True
    assert body["rows"][0]["trend"] == ["195.00", "200.00", "205.00"]


def test_charts_report_unavailable_when_price_history_is_not_configured(tmp_path):
    client, services = build(tmp_path)
    services.price_history = None
    services.repository.save_watchlist(Watchlist((WatchlistEntry("AAPL", "Earnings"),), NOW))

    assert client.get("/api/watchlist").json()["charts_available"] is False
    assert client.get("/api/price-history/AAPL?period=1M").json() == {"available": False}


def test_history_endpoint_returns_value_points(tmp_path):
    client, services = build(tmp_path)
    services.value_history.record()

    assert client.get("/api/history").json() == [
        {"at": NOW.isoformat(), "total_value": "10000.00", "benchmark_value": "10000.00"}
    ]


def test_activity_endpoint_returns_the_live_timeline(tmp_path):
    client, services = build(tmp_path)
    services.activity.begin("Decision run")
    services.activity.add("Trading Agent", "Started")

    body = client.get("/api/activity").json()

    assert body["active"] is True
    assert body["label"] == "Decision run"
    assert body["events"] == [{"at": NOW.isoformat(), "actor": "Trading Agent", "text": "Started"}]


def test_a_finished_run_adds_a_point_to_the_value_history(tmp_path):
    client, services = build(tmp_path)
    services.repository.save_watchlist(Watchlist((WatchlistEntry("AAPL", "x"),), NOW))

    with client:
        client.post("/api/runs")
        deadline = time.monotonic() + 3
        while time.monotonic() < deadline and not services.value_history.points():
            time.sleep(0.05)

    assert len(services.value_history.points()) == 1


def wait_for_watchlist(services, seconds=3.0):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline and services.repository.load_watchlist() is None:
        time.sleep(0.05)
    return services.repository.load_watchlist()


def test_saving_the_first_ai_key_builds_the_first_watchlist(tmp_path):
    client, services = build(tmp_path)

    with client:  # keeps the app's event loop alive for the background build
        client.put("/api/settings/keys/openai", json={"api_key": "sk-test-1"})
        watchlist = wait_for_watchlist(services)

    assert watchlist.symbols == {"AAPL"}


def test_starting_with_a_saved_key_and_no_watchlist_builds_it(tmp_path):
    client, services = build(tmp_path)
    services.settings.set_api_key("openai", "sk-test-1")

    with client:
        watchlist = wait_for_watchlist(services)

    assert watchlist.symbols == {"AAPL"}


def test_run_mode_defaults_to_manual_with_no_scheduled_run(client):
    body = client.get("/api/settings").json()

    assert body["run_mode"] == "manual"
    assert body["next_scheduled_run"] is None
    assert body["run_mode_estimates"] is None  # no AI key yet, so no model to price


def test_settings_show_the_enforced_trading_rules(client):
    rules = client.get("/api/settings").json()["trading_rules"]

    assert rules == {"fee_per_trade": "1.00", "max_position_percent": "20"}


def test_choosing_a_run_mode_shows_next_run_and_estimates(client):
    client.put("/api/settings/keys/openai", json={"api_key": "sk-test-1"})

    body = client.put("/api/settings/run-mode", json={"mode": "daily"}).json()

    assert body["run_mode"] == "daily"
    assert body["next_scheduled_run"] is not None
    estimates = body["run_mode_estimates"]
    assert estimates["basis"] == "rough"
    daily = next(m for m in estimates["modes"] if m["mode"] == "daily")
    assert daily == {
        "mode": "daily", "runs_per_month": 21, "ai_cost_per_run": "0.003", "ai_cost_per_month": "0.063",
        "searches_per_month": 105, "within_free_allowance": True, "allowance_lasts_trading_days": None,
    }
    assert "tavily" not in str(body).lower()


def test_unknown_run_mode_is_400(client):
    assert client.put("/api/settings/run-mode", json={"mode": "hourly"}).status_code == 400


def test_settings_flow_keys_and_model(client):
    assert client.get("/api/settings").json()["models"] == []

    assert client.put("/api/settings/keys/openai", json={"api_key": "sk-test-4321"}).status_code == 200
    body = client.get("/api/settings").json()

    openai = next(p for p in body["providers"] if p["provider"] == "openai")
    assert openai == {"provider": "openai", "has_key": True, "masked_key": "…4321"}
    assert body["models"][0]["model_id"] == "gpt-6-luna"
    assert body["models"][0]["input_usd_per_million"] == "0.10"
    assert body["selected_model_id"] == "gpt-6-luna"
    assert body["catalogue_as_of"] == "2026-09-26"
    assert "sk-test-4321" not in str(body)

    assert client.put("/api/settings/model", json={"model_id": "gpt-6-luna"}).status_code == 200
    assert client.put("/api/settings/model", json={"model_id": "claude-x"}).status_code == 400
    assert client.put("/api/settings/keys/gemini", json={"api_key": "k"}).status_code == 400
