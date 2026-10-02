"""Keeps the agent map (docs/agent-map.html, D45) in step with the code.

The page is for people only and is never a source for decisions. Its numbers sit in elements marked
data-from="NAME" and are filled from the constants below; its comment at the top lists the agents,
tools, triggers and order rules it covers, which the doc drift check compares with the code.
"""

import re
from collections.abc import Mapping
from decimal import Decimal
from pathlib import Path

from trade_simulator.adapters.config import BACKEND_DIR
from trade_simulator.adapters.openai_agents import agent_factory
from trade_simulator.adapters.openai_agents.agent_factory import RESEARCH_MAX_TURNS
from trade_simulator.adapters.openai_agents.toolbox import ResearchToolbox
from trade_simulator.adapters.openai_agents.trading_agents import (
    REFRESH_MAX_TURNS,
    REVIEW_MAX_TURNS,
    TRADING_MAX_TURNS,
)
from trade_simulator.application.strategy_timing import SCHEDULED_REVIEW_DELAY
from trade_simulator.core.decision_log import MAX_WATCHLIST_SIZE, RunTrigger
from trade_simulator.core.exchange_profile import US_PROFILE
from trade_simulator.core.run_budget import DECISION_RUN_LIMITS, REFRESH_RUN_LIMITS
from trade_simulator.core.strategy_review import STRATEGY_REVIEW_MINIMUMS, ReviewTrigger
from trade_simulator.core.trading_rules import RejectionReason, TradingRules

AGENT_MAP_PATH = BACKEND_DIR.parent / "docs" / "agent-map.html"

_MARKED = re.compile(
    r'(?P<open><(?P<tag>[\w:-]+)\b[^>]*?\sdata-from="(?P<name>[A-Z0-9_]+)"[^>]*>)(?P<text>[^<]*)(?P<close></(?P=tag)>)'
)
_COVERAGE = re.compile(r"<!-- agent-map covers\n(?P<body>.*?)-->", re.DOTALL)


def current_numbers() -> dict[str, str]:
    """Every number the page shows, by the name its data-from uses."""
    rules = TradingRules.for_exchange(US_PROFILE)
    return {
        "TRADING_MAX_TURNS": str(TRADING_MAX_TURNS),
        "RESEARCH_MAX_TURNS": str(RESEARCH_MAX_TURNS),
        "REFRESH_MAX_TURNS": str(REFRESH_MAX_TURNS),
        "REVIEW_MAX_TURNS": str(REVIEW_MAX_TURNS),
        "MAX_RESEARCH_CALLS": str(DECISION_RUN_LIMITS.max_research_calls),
        "DECISION_MAX_SEARCHES": str(DECISION_RUN_LIMITS.max_searches),
        "REFRESH_MAX_SEARCHES": str(REFRESH_RUN_LIMITS.max_searches),
        "MAX_WATCHLIST_SIZE": str(MAX_WATCHLIST_SIZE),
        "MAX_POSITION_PERCENT": _plain(rules.max_position_fraction * 100),
        "FEE_PER_TRADE": _plain(rules.fee_per_trade),
        "ORDER_RULE_COUNT": str(len(RejectionReason)),
        "REVIEW_MIN_DAYS": str(STRATEGY_REVIEW_MINIMUMS.trading_days),
        "REVIEW_MIN_RUNS": str(STRATEGY_REVIEW_MINIMUMS.trading_runs),
        "REVIEW_DELAY_MINUTES": str(int(SCHEDULED_REVIEW_DELAY.total_seconds() // 60)),
        "MAX_SYMBOLS_PER_CALL": str(ResearchToolbox.MAX_SYMBOLS_PER_CALL),
    }


def fill_numbers(html: str, numbers: Mapping[str, str]) -> str:
    def replace(match: re.Match) -> str:
        name = match["name"]
        if name not in numbers:
            raise ValueError(f'The agent map uses data-from="{name}", which the code does not provide')
        return match["open"] + numbers[name] + match["close"]

    return _MARKED.sub(replace, html)


def current_structure() -> dict[str, set[str]]:
    """What the page must cover: a change to any of these means the drawing may be out of date."""
    factory = Path(agent_factory.__file__).read_text(encoding="utf-8")
    return {
        "agents": set(re.findall(r'name="([^"]+)"', factory)),
        "tools": set(re.findall(r"@function_tool\s+async def (\w+)", factory)),
        "run triggers": {trigger.value for trigger in RunTrigger},
        "review triggers": {trigger.value for trigger in ReviewTrigger},
        "order rules": {reason.name for reason in RejectionReason},
    }


def coverage_in(html: str) -> dict[str, set[str]]:
    match = _COVERAGE.search(html)
    if match is None:
        return {}
    coverage = {}
    for line in match["body"].strip().splitlines():
        kind, _, names = line.partition(":")
        coverage[kind.strip()] = {name.strip() for name in names.split(";") if name.strip()}
    return coverage


def coverage_problems(covered: Mapping[str, set[str]], current: Mapping[str, set[str]]) -> list[str]:
    problems = []
    for kind in sorted(set(covered) | set(current)):
        on_page, in_code = covered.get(kind, set()), current.get(kind, set())
        if missing := in_code - on_page:
            problems.append(f"{kind}: not on the page: {', '.join(sorted(missing))}")
        if gone := on_page - in_code:
            problems.append(f"{kind}: on the page but gone from the code: {', '.join(sorted(gone))}")
    return problems


def refresh(path: Path = AGENT_MAP_PATH) -> bool:
    """Fill the page's numbers from the code. Returns whether the file changed."""
    html = path.read_bytes().decode("utf-8")  # bytes, so line endings are kept as they are
    filled = fill_numbers(html, current_numbers())
    if filled == html:
        return False
    path.write_bytes(filled.encode("utf-8"))
    return True


def _plain(value: Decimal) -> str:
    return format(value.normalize(), "f")
