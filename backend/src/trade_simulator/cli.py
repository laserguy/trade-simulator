"""Command-line entry point.

    uv run trade-sim serve     # start the web app at http://127.0.0.1:8000
    uv run trade-sim refresh   # rebuild the watchlist (any time)
    uv run trade-sim run       # one decision run, like "Run now" (market hours only)
    uv run trade-sim status    # portfolio, watchlist, market status, recent runs
"""

import argparse
import asyncio
import sys
from datetime import datetime, timezone

import uvicorn
from dotenv import load_dotenv

from trade_simulator.adapters.bootstrap import build_services
from trade_simulator.adapters.config import BACKEND_DIR, load_config
from trade_simulator.adapters.web.api import WebServices, create_app
from trade_simulator.application.portfolio_setup import load_or_create_portfolio
from trade_simulator.core.decision_log import DecisionRun, RunTrigger
from trade_simulator.core.errors import TradeSimulatorError

TRACE_URL = "https://platform.openai.com/traces/trace?trace_id={}"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="trade-sim", description="AI paper-trading simulator")
    parser.add_argument("command", choices=["serve", "refresh", "run", "status"])
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args(argv)

    load_dotenv(BACKEND_DIR / ".env")
    try:
        config = load_config()
        services = build_services(config)
        if args.command == "serve":
            # Localhost only: the app holds API keys and has no login (D1).
            uvicorn.run(create_app(services, config.frontend_dist), host="127.0.0.1", port=args.port)
        elif args.command == "refresh":
            _print_run(asyncio.run(services.watchlist_refresher.refresh()))
            services.value_history.record()
        elif args.command == "run":
            _print_run(asyncio.run(services.decision_runner.run(RunTrigger.MANUAL)))
            services.value_history.record()
        else:
            _print_status(services)
    except TradeSimulatorError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    return 0


def _print_run(run: DecisionRun) -> None:
    print(f"Run {run.id} [{run.trigger.value}] {run.status.value.upper()}")
    if run.failure_reason:
        print(f"  Reason: {run.failure_reason}")
    for finding in run.findings:
        print(f"  - {finding.symbol}: {finding.summary}")
        for warning in finding.warnings:
            print(f"      WARNING: {warning}")
        for source in finding.sources:
            print(f"      {source}")
    for result in run.order_results:
        order = result.order
        outcome = (
            f"executed at {result.price} (+{result.fee} fee)"
            if result.rejection_reason is None
            else f"REJECTED: {result.rejection_reason.value}"
        )
        print(f"  {order.side.value.upper()} {order.quantity} {order.symbol}: {outcome}")
        print(f"      Reason: {order.reason}")
    cost = run.cost
    print(f"  Cost: {cost.input_tokens} input + {cost.output_tokens} output tokens, {cost.searches} searches")
    if run.trace_id:
        print(f"  Trace: {TRACE_URL.format(run.trace_id)}")


def _print_status(services: WebServices) -> None:
    now = datetime.now(timezone.utc)
    calendar = services.calendar
    market = "OPEN" if calendar.is_open(now) else f"CLOSED (opens {calendar.next_open(now):%a %d %b %H:%M %Z})"
    print(f"Market: {market}")

    portfolio = load_or_create_portfolio(services.repository, services.profile)
    currency = services.profile.currency
    print(f"Cash: {portfolio.cash:,.2f} {currency}")
    for symbol, position in sorted(portfolio.positions.items()):
        print(f"  {symbol}: {position.quantity} shares @ avg {position.average_cost:,.2f}")

    watchlist = services.repository.load_watchlist()
    if watchlist:
        print(f"Watchlist ({watchlist.refreshed_at:%Y-%m-%d}): {', '.join(sorted(watchlist.symbols))}")
    else:
        print("Watchlist: none yet (run `trade-sim refresh`)")

    print("Recent runs:")
    for run in services.repository.list_runs(limit=5):
        print(f"  {run.started_at:%Y-%m-%d %H:%M} {run.trigger.value:<12} {run.status.value}")


if __name__ == "__main__":
    raise SystemExit(main())
