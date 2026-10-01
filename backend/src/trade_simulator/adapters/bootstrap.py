"""Composition root: the only place that knows every concrete adapter and wires them into the use cases."""

from trade_simulator.adapters.config import DEFAULT_MODEL, AppConfig
from trade_simulator.adapters.exchange_calendar import ExchangeCalendar
from trade_simulator.adapters.finnhub_market_data import FinnhubMarketData
from trade_simulator.adapters.logging_setup import configure_logging
from trade_simulator.adapters.model_catalogue_file import load_model_catalogue
from trade_simulator.adapters.openai_agents.mcp_config import load_mcp_servers
from trade_simulator.adapters.openai_agents.prompts import PromptLibrary
from trade_simulator.adapters.openai_agents.toolbox import ResearchToolbox
from trade_simulator.adapters.openai_agents.trading_agents import OpenAITradingAgents
from trade_simulator.adapters.sp500_universe import Sp500Universe
from trade_simulator.adapters.sqlite_repository import SqliteRepository
from trade_simulator.adapters.tavily_search import TavilySearch
from trade_simulator.adapters.tiingo_price_history import TiingoPriceHistory
from trade_simulator.application.price_history import PriceHistoryService
from trade_simulator.adapters.web.api import WebServices
from trade_simulator.application.activity import ActivityFeed
from trade_simulator.application.initial_watchlist import InitialWatchlist
from trade_simulator.application.portfolio_view import PortfolioViewer
from trade_simulator.application.refresh_watchlist import WatchlistRefresher
from trade_simulator.application.review_strategy import StrategyReviewRunner
from trade_simulator.application.strategy_view import StrategyViewer
from trade_simulator.application.run_decision import DecisionRunner
from trade_simulator.application.run_guard import RunGuard
from trade_simulator.application.ports import WebSearch
from trade_simulator.application.run_mode import RunModeSetting
from trade_simulator.application.settings import SettingsService
from trade_simulator.core.errors import ConfigError
from trade_simulator.application.value_history import ValueHistory
from trade_simulator.application.watchlist_view import WatchlistViewer
from trade_simulator.core.exchange_profile import US_PROFILE, ExchangeProfile


def build_services(config: AppConfig, profile: ExchangeProfile = US_PROFILE) -> WebServices:
    config.database_path.parent.mkdir(parents=True, exist_ok=True)
    repository = SqliteRepository(config.database_path)
    repository.initialize()

    catalogue = load_model_catalogue(config.model_catalogue_path)
    settings = SettingsService(store=repository, catalogue=catalogue, default_model_id=DEFAULT_MODEL)
    configure_logging(config.log_path, lambda: config.secrets() + settings.secrets())

    market_data = _market_data(config)
    calendar = ExchangeCalendar(profile)
    activity = ActivityFeed()  # live timeline of the run in progress (D28)
    search = _web_search(config)
    agents = OpenAITradingAgents(
        activity=activity,
        model_selection=settings.current_selection,
        toolbox=ResearchToolbox(market_data, search),
        prompts=PromptLibrary(config.prompts_dir),
        profile=profile,
        mcp_servers=load_mcp_servers(config.mcp_config_path),
    )
    guard = RunGuard()  # shared: decision runs and refreshes never overlap (D20)
    refresher = WatchlistRefresher(
        repository=repository, agent=agents, universe=Sp500Universe(), profile=profile, guard=guard,
        activity=activity,
    )
    portfolio_viewer = PortfolioViewer(repository=repository, market_data=market_data, profile=profile)

    return WebServices(
        profile=profile,
        repository=repository,
        calendar=calendar,
        guard=guard,
        decision_runner=DecisionRunner(
            repository=repository, market_data=market_data, calendar=calendar,
            agent=agents, profile=profile, guard=guard, activity=activity,
        ),
        watchlist_refresher=refresher,
        initial_watchlist=InitialWatchlist(
            repository=repository, settings=settings, store=repository, refresher=refresher
        ),
        portfolio_viewer=portfolio_viewer,
        watchlist_viewer=WatchlistViewer(repository=repository, quotes=market_data),
        value_history=ValueHistory(repository=repository, viewer=portfolio_viewer, profile=profile),
        activity=activity,
        run_mode=RunModeSetting(repository),
        free_searches_per_month=search.free_searches_per_month,
        price_history=_price_history(config, repository, profile),
        settings=settings,
        catalogue=catalogue,
        strategy_reviewer=StrategyReviewRunner(
            repository=repository, market_data=market_data, calendar=calendar,
            agent=agents, profile=profile, guard=guard, activity=activity,
        ),
        strategy_viewer=StrategyViewer(repository=repository, market_data=market_data, calendar=calendar, profile=profile),
    )


# One factory per external tool (D38). To add a provider: write its adapter, add it here and to
# the matching *_PROVIDER_KEYS table in config.py.


def _market_data(config: AppConfig) -> FinnhubMarketData:
    if config.market_data_provider == "finnhub":
        return FinnhubMarketData(api_key=config.market_data_api_key)
    raise ConfigError(f"Unknown market data provider '{config.market_data_provider}'")


def _web_search(config: AppConfig) -> WebSearch:
    if config.search_provider == "tavily":
        return TavilySearch(config.search_api_key)
    raise ConfigError(f"Unknown search provider '{config.search_provider}'")


def _price_history(config: AppConfig, repository, profile: ExchangeProfile) -> PriceHistoryService | None:
    if config.price_history_api_key is None:
        return None  # not set up: the app runs, charts show as unavailable
    if config.price_history_provider == "tiingo":
        source = TiingoPriceHistory(config.price_history_api_key)
    else:
        raise ConfigError(f"Unknown price history provider '{config.price_history_provider}'")
    return PriceHistoryService(repository=repository, source=source, profile=profile)
