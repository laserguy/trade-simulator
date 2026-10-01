import pytest

from trade_simulator.core.errors import InvalidOrderError
from trade_simulator.core.order import Order, Side
from trade_simulator.core.strategy import (
    DEVIATION,
    SECTION_WORD_LIMIT,
    Strategy,
    StrategySection,
    strategy_problems,
)


def make_strategy():
    return Strategy(
        what_i_look_for="Large companies with rising earnings estimates.",
        position_size="Start at 6%, add up to 12% after confirmation.",
        when_i_sell="Sell when the reason breaks or a holding falls 10% below cost.",
        cash_and_pace="Keep 10-25% in cash; build positions over several runs.",
        targets="Level with SPY or ahead by the next review.",
    )


def test_a_strategy_has_the_five_sections_in_a_fixed_order():
    sections = make_strategy().sections()

    assert [section for section, _ in sections] == [
        StrategySection.WHAT_I_LOOK_FOR,
        StrategySection.POSITION_SIZE,
        StrategySection.WHEN_I_SELL,
        StrategySection.CASH_AND_PACE,
        StrategySection.TARGETS,
    ]
    assert sections[0][1] == "Large companies with rising earnings estimates."


def test_section_titles_are_the_ones_the_user_sees():
    assert [section.title for section in StrategySection] == [
        "What I look for",
        "Position size",
        "When I sell",
        "Cash and pace",
        "My targets for this period",
    ]


def test_strategy_text_can_be_read_per_section():
    assert make_strategy().text(StrategySection.WHEN_I_SELL).startswith("Sell when")


def test_a_complete_strategy_within_the_word_limit_has_no_problems():
    assert strategy_problems(make_strategy()) == []


def test_an_empty_section_is_a_problem():
    strategy = Strategy(**{**make_strategy().__dict__, "when_i_sell": "  "})

    assert strategy_problems(strategy) == ["When I sell is empty"]


def test_a_section_over_the_word_limit_is_a_problem():
    strategy = Strategy(**{**make_strategy().__dict__, "targets": " ".join(["word"] * (SECTION_WORD_LIMIT + 1))})

    assert strategy_problems(strategy) == [f"My targets for this period has 61 words; the limit is {SECTION_WORD_LIMIT}"]


def test_an_order_may_name_the_section_it_follows():
    order = Order("AAPL", Side.BUY, 1, follows=StrategySection.POSITION_SIZE.value)

    assert order.follows == "position_size"


def test_an_order_may_be_marked_as_a_deviation():
    assert Order("AAPL", Side.SELL, 1, follows=DEVIATION).follows == DEVIATION


def test_orders_from_before_strategies_name_no_section():
    assert Order("AAPL", Side.BUY, 1).follows is None


def test_an_order_cannot_follow_an_unknown_section():
    with pytest.raises(InvalidOrderError):
        Order("AAPL", Side.BUY, 1, follows="gut_feeling")
