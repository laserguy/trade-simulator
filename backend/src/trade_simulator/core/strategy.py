"""The Trading Agent's own written strategy, in five fixed sections (D43)."""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum

# What an order names instead of a section when it breaks the strategy on purpose (D43).
DEVIATION = "deviation"
SECTION_WORD_LIMIT = 60


class StrategySection(Enum):
    WHAT_I_LOOK_FOR = "what_i_look_for"
    POSITION_SIZE = "position_size"
    WHEN_I_SELL = "when_i_sell"
    CASH_AND_PACE = "cash_and_pace"
    TARGETS = "targets"

    @property
    def title(self) -> str:
        return _TITLES[self]


_TITLES = {
    StrategySection.WHAT_I_LOOK_FOR: "What I look for",
    StrategySection.POSITION_SIZE: "Position size",
    StrategySection.WHEN_I_SELL: "When I sell",
    StrategySection.CASH_AND_PACE: "Cash and pace",
    StrategySection.TARGETS: "My targets for this period",
}

# Values an order may give for the strategy part it follows.
ORDER_BASES = frozenset(section.value for section in StrategySection) | {DEVIATION}


@dataclass(frozen=True)
class Strategy:
    """Plain-words guidance the agent follows. Only the trading rules (D6) are enforced by code."""

    what_i_look_for: str
    position_size: str
    when_i_sell: str
    cash_and_pace: str
    targets: str

    def text(self, section: StrategySection) -> str:
        return getattr(self, section.value)

    def sections(self) -> list[tuple[StrategySection, str]]:
        return [(section, self.text(section)) for section in StrategySection]


def strategy_problems(strategy: Strategy, word_limit: int = SECTION_WORD_LIMIT) -> list[str]:
    """Why a written strategy can't be saved: an empty section, or one over the word limit."""
    problems = []
    for section, text in strategy.sections():
        words = len(text.split())
        if words == 0:
            problems.append(f"{section.title} is empty")
        elif words > word_limit:
            problems.append(f"{section.title} has {words} words; the limit is {word_limit}")
    return problems


@dataclass(frozen=True)
class StrategyVersion:
    number: int
    strategy: Strategy
    started_at: datetime
    ended_at: datetime | None  # None while it is the current version
    review_id: str  # the review that wrote it
