"""REST API for the React UI (D16). Thin: it translates HTTP to use-case calls and results to JSON.

Runs take minutes, so "Run now" and "Refresh watchlist" start in the background and return 202;
the UI polls /api/status and /api/runs to follow progress.
"""

import asyncio
import logging
from collections.abc import Callable
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from zoneinfo import ZoneInfo

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from trade_simulator.application.activity import ActivityFeed
from trade_simulator.application.initial_watchlist import InitialWatchlist
from trade_simulator.application.portfolio_view import PortfolioSnapshot, PortfolioViewer
from trade_simulator.application.price_history import PriceHistoryService
from trade_simulator.application.ports import MarketCalendar, Repository
from trade_simulator.application.refresh_watchlist import WatchlistRefresher
from trade_simulator.application.review_strategy import StrategyReviewNotAllowedError, StrategyReviewRunner
from trade_simulator.application.strategy_view import ReviewEntry, StrategyPage, StrategyViewer
from trade_simulator.application.run_decision import DecisionRunner
from trade_simulator.application.run_cost_estimate import estimate_modes
from trade_simulator.application.run_guard import RunGuard
from trade_simulator.application.run_mode import RunModeSetting
from trade_simulator.application.schedule import Schedule
from trade_simulator.application.scheduler import Scheduler
from trade_simulator.core.errors import ConfigError
from trade_simulator.application.settings import SettingsError, SettingsService
from trade_simulator.application.value_history import ValueHistory
from trade_simulator.application.watchlist_view import WatchlistView, WatchlistViewer
from trade_simulator.adapters.text_links import merge_sources, split_links
from trade_simulator.core.decision_log import DecisionRun, Finding, RunCost, RunTrigger
from trade_simulator.core.exchange_profile import ExchangeProfile
from trade_simulator.core.model_pricing import ModelCatalogue
from trade_simulator.core.strategy import DEVIATION, StrategySection
from trade_simulator.core.strategy_review import ReviewTrigger, Scorecard
from trade_simulator.core.trading_rules import TradingRules

logger = logging.getLogger(__name__)
TRACE_URL = "https://platform.openai.com/traces/trace?trace_id={}"
TREND_DAYS = 31  # "Last month" trend line on each watchlist row (D37)
PERIOD_DAYS = {"1M": 31, "3M": 92, "1Y": 366}  # chart periods (D37)
CENTS = Decimal("0.01")


@dataclass
class WebServices:
    profile: ExchangeProfile
    repository: Repository
    calendar: MarketCalendar
    guard: RunGuard
    decision_runner: DecisionRunner
    watchlist_refresher: WatchlistRefresher
    initial_watchlist: InitialWatchlist
    portfolio_viewer: PortfolioViewer
    watchlist_viewer: WatchlistViewer
    value_history: ValueHistory
    activity: ActivityFeed
    run_mode: RunModeSetting
    free_searches_per_month: int | None  # declared by the search provider (D34)
    price_history: PriceHistoryService | None  # None when no price history provider is set up (D36)
    settings: SettingsService
    catalogue: ModelCatalogue
    strategy_reviewer: StrategyReviewRunner | None = None  # the Trading Agent's strategy reviews (D43)
    strategy_viewer: StrategyViewer | None = None  # the Strategy tab (D44)
    clock: Callable[[], datetime] = field(default=lambda: datetime.now(timezone.utc))
    scheduler_tick_seconds: float = 10.0


class ApiKeyBody(BaseModel):
    api_key: str | None


class ModelBody(BaseModel):
    model_id: str


class RunModeBody(BaseModel):
    mode: str


def create_app(services: WebServices, frontend_dist: Path | None = None) -> FastAPI:
    background: set[asyncio.Task] = set()

    def start_in_background(work: Callable, record_value: bool = True) -> None:
        async def work_then_record():
            run = await work()
            if run is not None and record_value:
                # A point on the value chart after every run (D33).
                await asyncio.to_thread(services.value_history.record)
                warm_watchlist_prices()  # a refresh may have added new stocks

        task = asyncio.create_task(work_then_record())
        background.add(task)
        task.add_done_callback(_finished(background))

    schedule = Schedule(services.calendar)

    async def scheduler_loop() -> None:
        """Starts scheduled runs (D3) and records the daily close value point (D33)."""
        scheduler = Scheduler(schedule, services.run_mode, services.clock())
        while True:
            await asyncio.sleep(services.scheduler_tick_seconds)
            try:
                due = scheduler.due(services.clock())
                if due.run is not None:
                    trigger = due.run
                    start_in_background(lambda: services.decision_runner.run(trigger))
                if due.snapshot:
                    await asyncio.to_thread(services.value_history.record)
                # The weekly strategy review (D43); while another run is going it waits for a later tick.
                reviewer = services.strategy_reviewer
                if reviewer is not None and not services.guard.busy and reviewer.timing().due:
                    start_in_background(lambda: reviewer.review(ReviewTrigger.SCHEDULED), record_value=False)
            except Exception:
                logger.exception("Scheduler tick failed")

    def warm_watchlist_prices() -> None:
        watchlist = services.repository.load_watchlist()
        if watchlist is not None:
            top_up_price_history([e.symbol for e in watchlist.entries])

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        # First watchlist is built automatically once an AI key exists (D4).
        start_in_background(services.initial_watchlist.build_if_needed)
        warm_watchlist_prices()
        loop = asyncio.create_task(scheduler_loop())
        yield
        loop.cancel()

    app = FastAPI(title="Trade Simulator", lifespan=lifespan)

    @app.get("/api/status")
    def status() -> dict:
        now = services.clock()
        is_open = services.calendar.is_open(now)
        return {
            "market_open": is_open,
            "next_open": None if is_open else services.calendar.next_open(now).isoformat(),
            "run_in_progress": services.guard.busy,
            "exchange": services.profile.name,
            "currency": services.profile.currency,
            "timezone": services.profile.timezone,
        }

    @app.get("/api/portfolio")
    def portfolio() -> dict:
        return _portfolio_json(services.portfolio_viewer.snapshot())

    refreshing_prices: set[str] = set()

    def top_up_price_history(symbols: list[str]) -> None:
        """Fill the price cache in the background so pages never wait on the provider (D36)."""
        history = services.price_history
        if history is None:
            return
        wanted = [s for s in history.stale_symbols(symbols) if s not in refreshing_prices]
        if not wanted:
            return
        refreshing_prices.update(wanted)

        async def work():
            try:
                await asyncio.to_thread(history.refresh, wanted)
            finally:
                refreshing_prices.difference_update(wanted)

        task = asyncio.create_task(work())
        background.add(task)
        task.add_done_callback(background.discard)

    @app.get("/api/watchlist")
    async def watchlist() -> dict | None:
        view = await asyncio.to_thread(services.watchlist_viewer.view)
        if view is None:
            return None
        symbols = [r.symbol for r in view.rows]
        history = services.price_history
        trends = history.cached_trends(symbols, days=TREND_DAYS) if history else {}
        top_up_price_history(symbols)
        return _watchlist_json(view, trends, charts_available=history is not None)

    @app.get("/api/price-history/{symbol}")
    async def price_history(symbol: str, period: str = "3M") -> dict:
        if period not in PERIOD_DAYS:
            raise HTTPException(status_code=400, detail=f"Period must be one of {', '.join(PERIOD_DAYS)}")
        history = services.price_history
        if history is None:
            return {"available": False}
        symbol = symbol.upper()
        days = PERIOD_DAYS[period]
        bars = await asyncio.to_thread(history.history, symbol, days)
        timezone_ = ZoneInfo(services.profile.timezone)
        first_day = bars[0].day if bars else None
        trades = [
            t for t in services.repository.executed_trades(symbol)
            if first_day is not None and t.at.astimezone(timezone_).date() >= first_day
        ]
        closes = [b.adj_close for b in bars]
        return {
            "available": True,
            "symbol": symbol,
            "period": period,
            "bars": [{"day": b.day.isoformat(), "close": _money(b.adj_close)} for b in bars],
            "low": _money(min(closes)) if closes else None,
            "high": _money(max(closes)) if closes else None,
            "trades": [
                {
                    "day": t.at.astimezone(timezone_).date().isoformat(),
                    "side": t.side.value,
                    "quantity": t.quantity,
                    "price": _money(t.price),
                }
                for t in trades
            ],
        }

    @app.get("/api/history")
    def history() -> dict:
        # Value chart points, plus each run's executed trades for the chart's markers (D32).
        runs: dict[str, dict] = {}
        for t in services.repository.executed_trades():
            run = runs.setdefault(t.run_id, {"run_id": t.run_id, "at": t.at.isoformat(), "orders": []})
            run["orders"].append(
                {"side": t.side.value, "quantity": t.quantity, "symbol": t.symbol, "price": _money(t.price)}
            )
        return {
            "points": [
                {"at": p.at.isoformat(), "total_value": _money(p.total_value), "benchmark_value": _money(p.benchmark_value)}
                for p in services.value_history.points()
            ],
            "trades": list(runs.values()),
        }

    @app.get("/api/activity")
    def activity() -> dict:
        snapshot = services.activity.snapshot()
        return {
            "active": snapshot.active,
            "label": snapshot.label,
            "events": [{"at": e.at.isoformat(), "actor": e.actor, "text": e.text} for e in snapshot.events],
        }

    @app.get("/api/runs")
    def runs(limit: int = 50) -> list[dict]:
        return [_run_json(run, services.catalogue) for run in services.repository.list_runs(limit=min(limit, 200))]

    @app.get("/api/runs/{run_id}")
    def run(run_id: str) -> dict:
        found = services.repository.get_run(run_id)
        if found is None:
            raise HTTPException(status_code=404, detail="Run not found")
        return _run_json(found, services.catalogue)

    @app.post("/api/runs", status_code=202)
    async def run_now():
        now = services.clock()
        if not services.calendar.is_open(now):
            next_open = services.calendar.next_open(now)
            return JSONResponse(
                status_code=409,
                content={"detail": "Market closed", "next_open": next_open.isoformat()},
            )
        if services.guard.busy:
            return JSONResponse(status_code=409, content={"detail": "Another run is still in progress"})
        start_in_background(lambda: services.decision_runner.run(RunTrigger.MANUAL))
        return {"status": "started"}

    @app.post("/api/watchlist/refresh", status_code=202)
    async def refresh_watchlist():
        if services.guard.busy:
            return JSONResponse(status_code=409, content={"detail": "Another run is still in progress"})
        start_in_background(services.watchlist_refresher.refresh)
        return {"status": "started"}

    @app.get("/api/strategy")
    async def strategy() -> dict:
        page = await asyncio.to_thread(services.strategy_viewer.view)
        return _strategy_json(page, services.catalogue)

    @app.post("/api/strategy/review", status_code=202)
    async def review_strategy():
        if services.guard.busy:
            return JSONResponse(status_code=409, content={"detail": "Another run is still in progress"})
        timing = services.strategy_reviewer.timing()
        if not timing.can_review:
            return JSONResponse(status_code=409, content={"detail": str(StrategyReviewNotAllowedError(timing))})
        # A review is not a trade, so it adds no value point (D33).
        start_in_background(lambda: services.strategy_reviewer.review(ReviewTrigger.BUTTON), record_value=False)
        return {"status": "started"}

    @app.get("/api/settings")
    def get_settings() -> dict:
        return _settings_json(services, schedule)

    @app.put("/api/settings/keys/{provider}")
    async def put_key(provider: str, body: ApiKeyBody) -> dict:
        try:
            services.settings.set_api_key(provider, body.api_key)
        except SettingsError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        start_in_background(services.initial_watchlist.build_if_needed)
        return _settings_json(services, schedule)

    @app.put("/api/settings/model")
    def put_model(body: ModelBody) -> dict:
        try:
            services.settings.select_model(body.model_id)
        except SettingsError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return _settings_json(services, schedule)

    @app.put("/api/settings/run-mode")
    def put_run_mode(body: RunModeBody) -> dict:
        try:
            services.run_mode.set(body.mode)
        except SettingsError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return _settings_json(services, schedule)

    if frontend_dist and frontend_dist.is_dir():
        app.mount("/", StaticFiles(directory=frontend_dist, html=True), name="frontend")
    return app


def _finished(background: set) -> Callable[[asyncio.Task], None]:
    def callback(task: asyncio.Task) -> None:
        background.discard(task)
        if not task.cancelled() and task.exception():
            # Normal failures are logged as runs by the use cases; this catches refusals that raced the checks.
            logger.warning("Background run did not start: %s", task.exception())

    return callback


def _money(value: Decimal | None) -> str | None:
    return None if value is None else str(value.quantize(CENTS))


def _portfolio_json(snapshot: PortfolioSnapshot) -> dict:
    return {
        "currency": snapshot.currency,
        "cash": _money(snapshot.cash),
        "total_value": _money(snapshot.total_value),
        "starting_capital": _money(snapshot.starting_capital),
        "return_percent": _money(snapshot.return_percent),
        "benchmark_symbol": snapshot.benchmark_symbol,
        "benchmark_return_percent": _money(snapshot.benchmark_return_percent),
        "tracking_since": snapshot.tracking_since.isoformat() if snapshot.tracking_since else None,
        "positions": [
            {
                "symbol": p.symbol,
                "quantity": p.quantity,
                "average_cost": _money(p.average_cost),
                "price": _money(p.price),
                "market_value": _money(p.market_value),
                "unrealized_pnl": _money(p.unrealized_pnl),
                "weight_percent": _money(p.weight_percent),
            }
            for p in snapshot.positions
        ],
    }


def _watchlist_json(view: WatchlistView, trends: dict[str, list[Decimal]], charts_available: bool) -> dict:
    return {
        "refreshed_at": view.refreshed_at.isoformat(),
        "charts_available": charts_available,
        "rows": [
            {
                "symbol": r.symbol,
                "reason": split_links(r.reason)[0],
                "sources": list(merge_sources(r.sources, split_links(r.reason)[1])),
                "price": _money(r.price),
                "change_percent": _money(r.change_percent),
                "held_quantity": r.held_quantity,
                "trend": [_money(close) for close in trends.get(r.symbol, [])],
            }
            for r in view.rows
        ],
    }


def _run_json(run: DecisionRun, catalogue: ModelCatalogue) -> dict:
    return {
        "id": run.id,
        "trigger": run.trigger.value,
        "status": run.status.value,
        "started_at": run.started_at.isoformat(),
        "finished_at": run.finished_at.isoformat() if run.finished_at else None,
        "failure_reason": run.failure_reason,
        "findings": [_finding_json(f) for f in run.findings],
        "orders": [
            {
                "symbol": r.order.symbol,
                "side": r.order.side.value,
                "quantity": r.order.quantity,
                "reason": r.order.reason,
                "status": r.status.value,
                "price": None if r.price is None else str(r.price),
                "fee": None if r.fee is None else str(r.fee),
                "rejection_reason": r.rejection_reason.value if r.rejection_reason else None,
                "follows": r.order.follows,
                "follows_label": _follows_label(r.order.follows),
            }
            for r in run.order_results
        ],
        "cost": _cost_json(run.cost, catalogue),
        "trace_url": TRACE_URL.format(run.trace_id) if run.trace_id else None,
        "strategy_version": run.strategy_version,
    }


def _follows_label(follows: str | None) -> str | None:
    """The strategy section an order followed, as the user sees it (D31, D43)."""
    if follows is None:
        return None
    return "Deviation" if follows == DEVIATION else StrategySection(follows).title


def _cost_json(cost: RunCost, catalogue: ModelCatalogue) -> dict:
    option = catalogue.find(cost.model) if cost.model else None
    estimate = option.estimate_cost(cost.input_tokens, cost.output_tokens) if option else None
    return {
        "input_tokens": cost.input_tokens,
        "output_tokens": cost.output_tokens,
        "searches": cost.searches,
        "model": cost.model,
        "estimated_usd": None if estimate is None else str(estimate.quantize(Decimal("0.0001"))),
    }


def _strategy_json(page: StrategyPage, catalogue: ModelCatalogue) -> dict:
    """The Strategy tab (D44)."""
    timing, current = page.timing, page.current
    return {
        "current": None if current is None else {
            "number": current.number,
            "started_at": current.started_at.isoformat(),
            "sections": [
                {"key": s.section.value, "title": s.section.title, "text": s.text, "changed": s.changed,
                 "changed_why": s.changed_why}
                for s in page.sections
            ],
        },
        "timing": {
            "first": timing.first,
            "can_review": timing.can_review,
            "trading_days": timing.trading_days,
            "trading_runs": timing.trading_runs,
            "min_trading_days": timing.minimums.trading_days,
            "min_trading_runs": timing.minimums.trading_runs,
            "days_met_at": timing.days_met_at.isoformat() if timing.days_met_at else None,
            "next_scheduled": timing.next_scheduled.isoformat() if timing.next_scheduled else None,
        },
        "scorecard": _scorecard_json(page.scorecard),
        "reviews": [_review_json(entry, catalogue) for entry in page.reviews],
    }


def _scorecard_json(card: Scorecard | None) -> dict | None:
    if card is None:
        return None
    return {
        "period_start": card.period_start.isoformat(),
        "period_end": card.period_end.isoformat(),
        "portfolio_percent": _money(card.portfolio_percent),
        "benchmark_percent": _money(card.benchmark_percent),
        "trading_runs": card.trading_runs,
        "trades": card.trades,
        "fees": _money(card.fees),
        "closed_trades": [{"symbol": t.symbol, "gain": _money(t.gain)} for t in card.closed_trades],
        "holdings": [{"symbol": h.symbol, "gain_percent": _money(h.gain_percent)} for h in card.holdings],
        "average_cash_percent": _money(card.average_cash_percent),
        "followed_orders": card.followed_orders,
        "deviations": card.deviations,
    }


def _review_json(entry: ReviewEntry, catalogue: ModelCatalogue) -> dict:
    review = entry.review
    return {
        "id": review.id,
        "trigger": review.trigger.value,
        "started_at": review.started_at.isoformat(),
        "status": review.status.value,
        "failure_reason": review.failure_reason,
        "decision": review.decision.value if review.decision else None,
        "reviewed_version": entry.reviewed_version,
        "written_version": entry.written_version,
        "reason": review.reason,
        "targets_verdict": review.targets_verdict.value if review.targets_verdict else None,
        "targets_note": review.targets_note,
        "followed": review.followed.value if review.followed else None,
        "followed_note": review.followed_note,
        "changes": [
            {"key": c.section.value, "title": c.section.title, "old": c.old, "new": c.new, "why": c.why}
            for c in entry.changes
        ],
        "scorecard": _scorecard_json(review.scorecard),
        "cost": _cost_json(review.cost, catalogue),
        "trace_url": TRACE_URL.format(review.trace_id) if review.trace_id else None,
    }


def _finding_json(finding: Finding) -> dict:
    # Also cleans runs saved before links were kept out of the text.
    summary, urls = split_links(finding.summary)
    return {
        "symbol": finding.symbol,
        "summary": summary,
        "sources": list(merge_sources(finding.sources, urls)),
        "warnings": list(finding.warnings),
        "price": None if finding.price is None else str(finding.price),
        "change_percent": None if finding.change_percent is None else str(finding.change_percent),
    }


def _settings_json(services: WebServices, schedule: Schedule) -> dict:
    view = services.settings.view()
    mode = services.run_mode.get()
    next_run = schedule.next_run(mode, services.clock())
    return {
        "run_mode": mode.value,
        "next_scheduled_run": next_run.isoformat() if next_run else None,
        "run_mode_estimates": _estimates_json(services),
        "trading_rules": _trading_rules_json(services.profile),
        **_keys_and_models_json(view),
    }


def _trading_rules_json(profile: ExchangeProfile) -> dict:
    """The values the trade checks use (D6), so the Settings card can't drift from the code (D29)."""
    rules = TradingRules.for_exchange(profile)
    return {
        "fee_per_trade": _money(rules.fee_per_trade),
        "max_position_percent": format((rules.max_position_fraction * 100).normalize(), "f"),
    }


def _estimates_json(services: WebServices) -> dict | None:
    try:
        model = services.settings.current_selection().option
    except ConfigError:
        return None  # no AI key yet: nothing to price
    estimates = estimate_modes(
        model, services.repository.list_runs(limit=100), services.profile, services.free_searches_per_month
    )
    return {
        "basis": estimates.basis,
        "modes": [
            {
                "mode": e.mode.value,
                "runs_per_month": e.runs_per_month,
                "ai_cost_per_run": _usd(e.ai_cost_per_run),
                "ai_cost_per_month": _usd(e.ai_cost_per_month),
                "searches_per_month": e.searches_per_month,
                "within_free_allowance": e.within_free_allowance,
                "allowance_lasts_trading_days": e.allowance_lasts_trading_days,
            }
            for e in estimates.modes
        ],
    }


def _usd(value: Decimal | None) -> str | None:
    return None if value is None else str(value.quantize(Decimal("0.001")))


def _keys_and_models_json(view) -> dict:
    return {
        "providers": [
            {"provider": p.provider, "has_key": p.has_key, "masked_key": p.masked_key}
            for p in view.providers
        ],
        "models": [
            {
                "provider": m.provider,
                "model_id": m.model_id,
                "label": m.label,
                "input_usd_per_million": str(m.input_usd_per_million),
                "output_usd_per_million": str(m.output_usd_per_million),
                "note": m.note,
            }
            for m in view.models
        ],
        "selected_model_id": view.selected_model_id,
        "catalogue_as_of": view.catalogue_as_of,
    }
