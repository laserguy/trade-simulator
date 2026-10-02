"""The agent map's numbers and coverage list, read from the code (D45)."""

import pytest

from trade_simulator.adapters import agent_map
from trade_simulator.adapters.openai_agents.agent_factory import RESEARCH_MAX_TURNS
from trade_simulator.adapters.openai_agents.trading_agents import TRADING_MAX_TURNS
from trade_simulator.core.run_budget import DECISION_RUN_LIMITS
from trade_simulator.core.trading_rules import RejectionReason


def test_fill_numbers_replaces_the_text_of_marked_elements():
    html = '<p>Up to <span class="num" data-from="A">9</span> turns, <tspan data-from="B">old</tspan>.</p>'
    filled = agent_map.fill_numbers(html, {"A": "10", "B": "12"})
    assert filled == '<p>Up to <span class="num" data-from="A">10</span> turns, <tspan data-from="B">12</tspan>.</p>'


def test_fill_numbers_leaves_unmarked_text_alone():
    html = "<p>10 turns</p>"
    assert agent_map.fill_numbers(html, {"A": "3"}) == html


def test_fill_numbers_rejects_a_name_the_code_does_not_provide():
    with pytest.raises(ValueError, match="UNKNOWN"):
        agent_map.fill_numbers('<b data-from="UNKNOWN">1</b>', {"A": "1"})


def test_current_numbers_come_from_the_code():
    numbers = agent_map.current_numbers()
    assert numbers["TRADING_MAX_TURNS"] == str(TRADING_MAX_TURNS)
    assert numbers["RESEARCH_MAX_TURNS"] == str(RESEARCH_MAX_TURNS)
    assert numbers["MAX_RESEARCH_CALLS"] == str(DECISION_RUN_LIMITS.max_research_calls)
    assert numbers["DECISION_MAX_SEARCHES"] == str(DECISION_RUN_LIMITS.max_searches)
    assert numbers["MAX_POSITION_PERCENT"] == "20"
    assert numbers["FEE_PER_TRADE"] == "1"
    assert numbers["ORDER_RULE_COUNT"] == str(len(RejectionReason))


def test_coverage_is_read_from_the_comment_at_the_top():
    html = (
        "<!-- agent-map covers\n"
        "agents: Trading Agent; Research Agent\n"
        "tools: get_quotes; web_search\n"
        "-->\n<title>x</title>"
    )
    assert agent_map.coverage_in(html) == {
        "agents": {"Trading Agent", "Research Agent"},
        "tools": {"get_quotes", "web_search"},
    }


def test_coverage_is_empty_without_the_comment():
    assert agent_map.coverage_in("<title>x</title>") == {}


def test_current_structure_lists_agents_tools_triggers_and_order_rules():
    structure = agent_map.current_structure()
    assert structure["agents"] == {
        "Trading Agent",
        "Trading Agent (strategy review)",
        "Research Agent",
        "Research Agent (watchlist refresh)",
    }
    assert {"ask_research_agent", "get_quotes", "web_search"} <= structure["tools"]
    assert structure["run triggers"] == {"manual", "daily", "every_15_min", "refresh"}
    assert structure["review triggers"] == {"button", "scheduled", "automatic"}
    assert structure["order rules"] == {reason.name for reason in RejectionReason}


def test_coverage_problems_name_what_is_missing_and_what_is_gone():
    problems = agent_map.coverage_problems(
        covered={"tools": {"get_quotes", "old_tool"}},
        current={"tools": {"get_quotes", "new_tool"}},
    )
    assert problems == ["tools: not on the page: new_tool", "tools: on the page but gone from the code: old_tool"]


def test_refresh_rewrites_the_file_only_when_a_number_changed(tmp_path):
    page = tmp_path / "agent-map.html"
    page.write_text('<b data-from="TRADING_MAX_TURNS">0</b>', encoding="utf-8")
    assert agent_map.refresh(page) is True
    assert page.read_text(encoding="utf-8") == f'<b data-from="TRADING_MAX_TURNS">{TRADING_MAX_TURNS}</b>'
    assert agent_map.refresh(page) is False
